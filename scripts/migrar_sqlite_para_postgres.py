#!/usr/bin/env python3
"""
Migra os dados do SQLite do SPY TEAM para PostgreSQL preservando IDs.

Fluxo recomendado no Railway:
1. Criar serviço PostgreSQL.
2. No serviço SpyTeam, criar POSTGRES_MIGRATION_URL=${{Postgres.DATABASE_URL}}.
3. Ainda SEM DATABASE_URL, fazer backup do SQLite e executar este script.
4. Conferir a contagem de registros.
5. Só então criar DATABASE_URL=${{Postgres.DATABASE_URL}} e redeployar.

O script NÃO apaga o SQLite de origem.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine

# Permite executar o script a partir da raiz do projeto.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app import models  # noqa: E402


DEFAULT_SOURCE = os.getenv("DATABASE_PATH") or "/data/assessoria.db"
DEFAULT_TARGET_ENV = "POSTGRES_MIGRATION_URL"


def normalizar_postgres_url(url: str) -> str:
    valor = str(url or "").strip()
    if valor.startswith("postgres://"):
        return "postgresql+psycopg://" + valor[len("postgres://"):]
    if valor.startswith("postgresql://"):
        return "postgresql+psycopg://" + valor[len("postgresql://"):]
    return valor


def criar_source_engine(caminho: str) -> Engine:
    origem = os.path.abspath(caminho)
    if not os.path.isfile(origem):
        raise RuntimeError(f"SQLite de origem não encontrado: {origem}")
    return create_engine(f"sqlite:///{origem}")


def criar_target_engine(url: str) -> Engine:
    normalizada = normalizar_postgres_url(url)
    if not normalizada.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "O destino precisa ser PostgreSQL. "
            "Use a variável POSTGRES_MIGRATION_URL apontando para "
            "${{Postgres.DATABASE_URL}}."
        )
    return create_engine(normalizada, pool_pre_ping=True)


def garantir_destino_vazio(engine: Engine) -> None:
    inspetor = inspect(engine)
    tabelas = set(inspetor.get_table_names())

    ocupadas: list[tuple[str, int]] = []
    with engine.connect() as conexao:
        for tabela in models.Base.metadata.sorted_tables:
            if tabela.name not in tabelas:
                continue
            qtd = conexao.execute(
                text(f'SELECT COUNT(*) FROM "{tabela.name}"')
            ).scalar_one()
            if qtd:
                ocupadas.append((tabela.name, int(qtd)))

    if ocupadas:
        detalhes = ", ".join(f"{nome}={qtd}" for nome, qtd in ocupadas)
        raise RuntimeError(
            "O PostgreSQL de destino já possui dados. Migração cancelada para "
            f"evitar duplicação/sobrescrita. Tabelas ocupadas: {detalhes}"
        )


def detectar_emails_duplicados(source_engine: Engine) -> None:
    inspetor = inspect(source_engine)
    if "usuarios" not in inspetor.get_table_names():
        return

    with source_engine.connect() as conexao:
        duplicados = conexao.execute(text("""
            SELECT lower(trim(email)) AS email_normalizado, COUNT(*) AS quantidade
            FROM usuarios
            WHERE email IS NOT NULL AND trim(email) <> ''
            GROUP BY lower(trim(email))
            HAVING COUNT(*) > 1
            LIMIT 10
        """)).fetchall()

    if duplicados:
        resumo = ", ".join(f"{email} ({qtd})" for email, qtd in duplicados)
        raise RuntimeError(
            "Existem e-mails duplicados ignorando maiúsculas/minúsculas no SQLite. "
            f"Corrija antes da migração: {resumo}"
        )


def copiar_tabelas(source_engine: Engine, target_engine: Engine) -> dict[str, int]:
    origem_meta = MetaData()
    origem_meta.reflect(bind=source_engine)

    tabelas_origem = set(origem_meta.tables)
    contagens: dict[str, int] = {}

    # A ordem de Base.metadata.sorted_tables respeita FKs declaradas nos models.
    # BEGIN IMMEDIATE congela as escritas no SQLite durante os poucos segundos
    # da cópia, garantindo que todas as tabelas pertençam ao mesmo snapshot.
    with source_engine.connect() as origem:
        origem.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            with target_engine.begin() as destino:
                for tabela_destino in models.Base.metadata.sorted_tables:
                    nome = tabela_destino.name
                    if nome not in tabelas_origem:
                        contagens[nome] = 0
                        continue

                    tabela_origem = origem_meta.tables[nome]
                    colunas_destino = {coluna.name for coluna in tabela_destino.columns}
                    colunas_origem = [
                        coluna.name
                        for coluna in tabela_origem.columns
                        if coluna.name in colunas_destino
                    ]

                    if not colunas_origem:
                        contagens[nome] = 0
                        continue

                    resultado = origem.execute(select(tabela_origem)).mappings()
                    lote: list[dict] = []
                    total = 0

                    for registro in resultado:
                        dados = {chave: registro[chave] for chave in colunas_origem}

                        # Compatibilidade caso a origem seja de uma versão anterior.
                        if nome == "usuarios":
                            dados.setdefault("session_version", 0)
                            if "email_verificado" not in dados:
                                email = str(dados.get("email") or "").strip()
                                dados["email_verificado"] = bool(email)

                        lote.append(dados)

                        if len(lote) >= 500:
                            destino.execute(tabela_destino.insert(), lote)
                            total += len(lote)
                            lote.clear()

                    if lote:
                        destino.execute(tabela_destino.insert(), lote)
                        total += len(lote)

                    contagens[nome] = total
                    print(f"[migracao] {nome}: {total} registro(s)")
        finally:
            origem.rollback()

    return contagens


def ajustar_sequences_postgres(engine: Engine) -> None:
    with engine.begin() as conexao:
        for tabela in models.Base.metadata.sorted_tables:
            if "id" not in tabela.c:
                continue

            max_id = conexao.execute(
                select(func.max(tabela.c.id))
            ).scalar()

            sequence = conexao.execute(
                text("SELECT pg_get_serial_sequence(:tabela, 'id')"),
                {"tabela": tabela.name},
            ).scalar()

            if not sequence:
                continue

            if max_id is None:
                conexao.execute(
                    text("SELECT setval(to_regclass(:seq), 1, false)"),
                    {"seq": sequence},
                )
            else:
                conexao.execute(
                    text("SELECT setval(to_regclass(:seq), :valor, true)"),
                    {"seq": sequence, "valor": int(max_id)},
                )


def criar_indices_postgres(engine: Engine) -> None:
    with engine.begin() as conexao:
        conexao.exec_driver_sql("""
            CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_email_nocase
            ON usuarios (lower(email))
            WHERE email IS NOT NULL AND btrim(email) <> ''
        """)
        conexao.exec_driver_sql("""
            CREATE INDEX IF NOT EXISTS ix_verificacoes_email_usuario_ativo
            ON verificacoes_email(usuario_id, usado, criado_em)
        """)


def verificar_contagens(
    source_engine: Engine,
    target_engine: Engine,
    esperadas: dict[str, int],
) -> None:
    erros: list[str] = []

    with target_engine.connect() as destino:
        for nome, esperado in esperadas.items():
            if nome not in models.Base.metadata.tables:
                continue
            obtido = destino.execute(
                text(f'SELECT COUNT(*) FROM "{nome}"')
            ).scalar_one()
            if int(obtido) != int(esperado):
                erros.append(f"{nome}: SQLite={esperado}, PostgreSQL={obtido}")

    if erros:
        raise RuntimeError(
            "A verificação final encontrou diferenças:\n- " + "\n- ".join(erros)
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migra o SQLite do SPY TEAM para PostgreSQL."
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"Arquivo SQLite de origem (padrão: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--target-env",
        default=DEFAULT_TARGET_ENV,
        help=f"Variável com a URL PostgreSQL (padrão: {DEFAULT_TARGET_ENV})",
    )
    args = parser.parse_args()

    target_url = os.getenv(args.target_env)
    if not target_url:
        raise RuntimeError(
            f"Variável {args.target_env} não configurada. "
            "No Railway, defina-a como referência a ${{Postgres.DATABASE_URL}}."
        )

    print("[migracao] Origem SQLite:", os.path.abspath(args.source))
    print("[migracao] Destino: PostgreSQL")

    source_engine = criar_source_engine(args.source)
    target_engine = criar_target_engine(target_url)

    # Confirma conexão antes de qualquer alteração.
    with target_engine.connect() as conexao:
        conexao.execute(text("SELECT 1"))
    print("[migracao] Conexão PostgreSQL: OK")

    detectar_emails_duplicados(source_engine)

    # Cria a estrutura atual do SPY TEAM no PostgreSQL.
    models.Base.metadata.create_all(bind=target_engine)
    garantir_destino_vazio(target_engine)

    contagens = copiar_tabelas(source_engine, target_engine)
    ajustar_sequences_postgres(target_engine)
    criar_indices_postgres(target_engine)
    verificar_contagens(source_engine, target_engine, contagens)

    print("\n[migracao] MIGRAÇÃO CONCLUÍDA COM SUCESSO.")
    print("[migracao] O SQLite original NÃO foi apagado.")
    print("[migracao] Agora configure DATABASE_URL para o PostgreSQL e faça o redeploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
