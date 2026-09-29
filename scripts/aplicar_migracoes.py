"""Bootstrap seguro + aplicação das migrações Alembic do SPY TEAM.

Comportamento:
- banco vazio: executa ``alembic upgrade head`` e cria o schema;
- banco antigo já no schema atual, mas ainda sem ``alembic_version``:
  valida todas as tabelas/colunas e apenas marca a baseline;
- banco já versionado: executa somente as revisões pendentes.

O script nunca apaga dados e nunca usa ``drop_all``.
"""
from __future__ import annotations

from pathlib import Path
import sys

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import engine  # noqa: E402
from app.models import Base  # noqa: E402

BASELINE_REVISION = "20260925_01"


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def _revisao_atual() -> str | None:
    with engine.connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def _validar_schema_existente() -> None:
    """Garante que é seguro marcar um banco pré-Alembic como baseline."""
    inspetor = inspect(engine)
    tabelas_existentes = set(inspetor.get_table_names())
    # Tabelas posteriores à baseline são criadas pelas revisões seguintes.
    tabelas_esperadas = set(Base.metadata.tables.keys()) - {"strava_conexoes"}

    faltando = sorted(tabelas_esperadas - tabelas_existentes)
    if faltando:
        raise RuntimeError(
            "Banco pré-Alembic detectado, mas o schema não corresponde à versão "
            "atual. Tabelas ausentes: " + ", ".join(faltando)
        )

    problemas: list[str] = []
    for nome_tabela, tabela in Base.metadata.tables.items():
        if nome_tabela not in tabelas_esperadas:
            continue
        colunas_existentes = {
            col["name"] for col in inspetor.get_columns(nome_tabela)
        }
        colunas_esperadas = {col.name for col in tabela.columns}
        ausentes = sorted(colunas_esperadas - colunas_existentes)
        if ausentes:
            problemas.append(f"{nome_tabela}: {', '.join(ausentes)}")

    if problemas:
        raise RuntimeError(
            "Banco pré-Alembic detectado com colunas ausentes. "
            "A baseline NÃO foi marcada para evitar esconder divergências: "
            + " | ".join(problemas)
        )


def main() -> int:
    cfg = _config()
    scripts = ScriptDirectory.from_config(cfg)
    head = scripts.get_current_head()

    inspetor = inspect(engine)
    tabelas = set(inspetor.get_table_names())
    tem_alembic = "alembic_version" in tabelas
    tabelas_app = set(Base.metadata.tables.keys())
    existentes_app = tabelas & tabelas_app

    print(f"[Alembic] Head do código: {head}")

    if not tem_alembic:
        if not existentes_app:
            print("[Alembic] Banco vazio. Criando schema pela baseline...")
            command.upgrade(cfg, "head")
        else:
            print(
                "[Alembic] Banco existente sem controle de versão. "
                "Validando schema antes do primeiro stamp..."
            )
            _validar_schema_existente()
            command.stamp(cfg, BASELINE_REVISION)
            print(
                f"[Alembic] Schema existente marcado na baseline "
                f"{BASELINE_REVISION}; nenhum dado foi recriado."
            )
            command.upgrade(cfg, "head")
    else:
        atual = _revisao_atual()
        print(f"[Alembic] Revisão atual do banco: {atual}")
        command.upgrade(cfg, "head")

    final = _revisao_atual()
    if final != head:
        raise RuntimeError(
            f"Migração incompleta: banco={final!r}, código={head!r}."
        )

    print(f"[Alembic] Banco atualizado com sucesso: {final}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
