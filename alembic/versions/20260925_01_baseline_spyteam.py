"""baseline do schema atual do SPY TEAM

Revision ID: 20260925_01
Revises:
Create Date: 2026-09-25

Esta revisão representa o schema já existente no momento em que o projeto
passou a usar Alembic. Em bancos existentes, o bootstrap seguro marca esta
revisão sem recriar tabelas. Em bancos novos, ela cria o schema completo.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260925_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alunos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(), nullable=False),
        sa.Column("nivel", sa.String(), nullable=False),
        sa.Column("modalidade", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alunos_id", "alunos", ["id"], unique=False)
    op.create_index("ix_alunos_nome", "alunos", ["nome"], unique=False)

    op.create_table(
        "treinos_base",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("modalidade", sa.String(), nullable=False),
        sa.Column("descricao", sa.String(), nullable=False),
        sa.Column("ritmo_alvo", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_treinos_base_id", "treinos_base", ["id"], unique=False)
    op.create_index("ix_treinos_base_titulo", "treinos_base", ["titulo"], unique=False)

    op.create_table(
        "auditoria_logins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("usuario_informado", sa.String(), nullable=False),
        sa.Column("sucesso", sa.Boolean(), nullable=False),
        sa.Column("motivo", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("criado_em", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for nome, coluna in [
        ("ix_auditoria_logins_id", "id"),
        ("ix_auditoria_logins_usuario_id", "usuario_id"),
        ("ix_auditoria_logins_usuario_informado", "usuario_informado"),
        ("ix_auditoria_logins_sucesso", "sucesso"),
        ("ix_auditoria_logins_ip", "ip"),
        ("ix_auditoria_logins_criado_em", "criado_em"),
    ]:
        op.create_index(nome, "auditoria_logins", [coluna], unique=False)

    op.create_table(
        "eventos_rate_limit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("chave_hash", sa.String(), nullable=False),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("bloqueado", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for nome, coluna in [
        ("ix_eventos_rate_limit_id", "id"),
        ("ix_eventos_rate_limit_tipo", "tipo"),
        ("ix_eventos_rate_limit_chave_hash", "chave_hash"),
        ("ix_eventos_rate_limit_ip", "ip"),
        ("ix_eventos_rate_limit_bloqueado", "bloqueado"),
        ("ix_eventos_rate_limit_criado_em", "criado_em"),
    ]:
        op.create_index(nome, "eventos_rate_limit", [coluna], unique=False)

    op.create_table(
        "auditoria_administrativa",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("professor_id", sa.Integer(), nullable=True),
        sa.Column("professor_usuario", sa.String(), nullable=False),
        sa.Column("acao", sa.String(), nullable=False),
        sa.Column("entidade", sa.String(), nullable=False),
        sa.Column("entidade_id", sa.Integer(), nullable=True),
        sa.Column("descricao", sa.String(), nullable=False),
        sa.Column("dados_json", sa.String(), nullable=True),
        sa.Column("ip", sa.String(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("criado_em", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for nome, coluna in [
        ("ix_auditoria_administrativa_id", "id"),
        ("ix_auditoria_administrativa_professor_id", "professor_id"),
        ("ix_auditoria_administrativa_acao", "acao"),
        ("ix_auditoria_administrativa_entidade", "entidade"),
        ("ix_auditoria_administrativa_ip", "ip"),
        ("ix_auditoria_administrativa_criado_em", "criado_em"),
    ]:
        op.create_index(nome, "auditoria_administrativa", [coluna], unique=False)

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column("p256dh", sa.String(), nullable=False),
        sa.Column("auth", sa.String(), nullable=False),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("criado_em", sa.Integer(), nullable=False),
        sa.Column("atualizado_em", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_push_subscriptions_id", "push_subscriptions", ["id"], unique=False)
    op.create_index("ix_push_subscriptions_usuario_id", "push_subscriptions", ["usuario_id"], unique=False)
    op.create_index("ix_push_subscriptions_endpoint", "push_subscriptions", ["endpoint"], unique=True)
    op.create_index("ix_push_subscriptions_ativo", "push_subscriptions", ["ativo"], unique=False)
    op.create_index("ix_push_subscriptions_criado_em", "push_subscriptions", ["criado_em"], unique=False)
    op.create_index("ix_push_subscriptions_atualizado_em", "push_subscriptions", ["atualizado_em"], unique=False)

    op.create_table(
        "preferencias_notificacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("novo_treino", sa.Boolean(), nullable=False),
        sa.Column("lembrete_treino", sa.Boolean(), nullable=False),
        sa.Column("treino_pendente", sa.Boolean(), nullable=False),
        sa.Column("horario_lembrete", sa.String(), nullable=False),
        sa.Column("horario_pendente", sa.String(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False),
        sa.Column("atualizado_em", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_preferencias_notificacao_id", "preferencias_notificacao", ["id"], unique=False)
    op.create_index("ix_preferencias_notificacao_usuario_id", "preferencias_notificacao", ["usuario_id"], unique=True)
    op.create_index("ix_preferencias_notificacao_atualizado_em", "preferencias_notificacao", ["atualizado_em"], unique=False)

    op.create_table(
        "notificacoes_treino_enviadas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("treino_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("data_referencia", sa.String(), nullable=False),
        sa.Column("criado_em", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "usuario_id",
            "treino_id",
            "tipo",
            "data_referencia",
            name="uq_notificacao_treino_envio",
        ),
    )
    for nome, coluna in [
        ("ix_notificacoes_treino_enviadas_id", "id"),
        ("ix_notificacoes_treino_enviadas_usuario_id", "usuario_id"),
        ("ix_notificacoes_treino_enviadas_treino_id", "treino_id"),
        ("ix_notificacoes_treino_enviadas_tipo", "tipo"),
        ("ix_notificacoes_treino_enviadas_data_referencia", "data_referencia"),
        ("ix_notificacoes_treino_enviadas_criado_em", "criado_em"),
    ]:
        op.create_index(nome, "notificacoes_treino_enviadas", [coluna], unique=False)

    op.create_table(
        "aluno_modalidades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aluno_id", sa.Integer(), nullable=False),
        sa.Column("modalidade", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aluno_id", "modalidade", name="uq_aluno_modalidade"),
    )
    op.create_index("ix_aluno_modalidades_id", "aluno_modalidades", ["id"], unique=False)
    op.create_index("ix_aluno_modalidades_aluno_id", "aluno_modalidades", ["aluno_id"], unique=False)
    op.create_index("ix_aluno_modalidades_modalidade", "aluno_modalidades", ["modalidade"], unique=False)

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario", sa.String(), nullable=False),
        sa.Column("senha_hash", sa.String(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("aluno_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("nome", sa.String(), nullable=True),
        sa.Column("email_verificado", sa.Boolean(), nullable=False),
        sa.Column("foto_perfil", sa.String(), nullable=True),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("aluno_id"),
    )
    op.create_index("ix_usuarios_id", "usuarios", ["id"], unique=False)
    op.create_index("ix_usuarios_usuario", "usuarios", ["usuario"], unique=True)
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=False)

    op.create_table(
        "verificacoes_email",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expira_em", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.Integer(), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_verificacoes_email_id", "verificacoes_email", ["id"], unique=False)
    op.create_index("ix_verificacoes_email_usuario_id", "verificacoes_email", ["usuario_id"], unique=False)
    op.create_index("ix_verificacoes_email_email", "verificacoes_email", ["email"], unique=False)
    op.create_index("ix_verificacoes_email_token_hash", "verificacoes_email", ["token_hash"], unique=True)

    op.create_table(
        "recuperacoes_senha",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expira_em", sa.Integer(), nullable=False),
        sa.Column("criado_em", sa.Integer(), nullable=False),
        sa.Column("usado", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recuperacoes_senha_id", "recuperacoes_senha", ["id"], unique=False)
    op.create_index("ix_recuperacoes_senha_usuario_id", "recuperacoes_senha", ["usuario_id"], unique=False)
    op.create_index("ix_recuperacoes_senha_token_hash", "recuperacoes_senha", ["token_hash"], unique=True)

    op.create_table(
        "treinos_agendados",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("aluno_id", sa.Integer(), nullable=False),
        sa.Column("treino_base_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(), nullable=False),
        sa.Column("modalidade", sa.String(), nullable=False),
        sa.Column("descricao", sa.String(), nullable=False),
        sa.Column("ritmo_alvo", sa.String(), nullable=True),
        sa.Column("data_planejada", sa.String(), nullable=False),
        sa.Column("concluido", sa.Boolean(), nullable=False),
        sa.Column("concluido_em", sa.Integer(), nullable=True),
        sa.Column("feedback_nota", sa.Integer(), nullable=True),
        sa.Column("feedback_comentario", sa.String(), nullable=True),
        sa.Column("feedback_dificuldade", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["aluno_id"], ["alunos.id"]),
        sa.ForeignKeyConstraint(["treino_base_id"], ["treinos_base.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_treinos_agendados_id", "treinos_agendados", ["id"], unique=False)
    op.create_index("ix_treinos_agendados_concluido_em", "treinos_agendados", ["concluido_em"], unique=False)




def downgrade() -> None:
    op.drop_index("ix_treinos_agendados_concluido_em", table_name="treinos_agendados")
    op.drop_index("ix_treinos_agendados_id", table_name="treinos_agendados")
    op.drop_table("treinos_agendados")

    op.drop_index("ix_recuperacoes_senha_token_hash", table_name="recuperacoes_senha")
    op.drop_index("ix_recuperacoes_senha_usuario_id", table_name="recuperacoes_senha")
    op.drop_index("ix_recuperacoes_senha_id", table_name="recuperacoes_senha")
    op.drop_table("recuperacoes_senha")

    op.drop_index("ix_verificacoes_email_token_hash", table_name="verificacoes_email")
    op.drop_index("ix_verificacoes_email_email", table_name="verificacoes_email")
    op.drop_index("ix_verificacoes_email_usuario_id", table_name="verificacoes_email")
    op.drop_index("ix_verificacoes_email_id", table_name="verificacoes_email")
    op.drop_table("verificacoes_email")

    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_index("ix_usuarios_usuario", table_name="usuarios")
    op.drop_index("ix_usuarios_id", table_name="usuarios")
    op.drop_table("usuarios")

    op.drop_index("ix_aluno_modalidades_modalidade", table_name="aluno_modalidades")
    op.drop_index("ix_aluno_modalidades_aluno_id", table_name="aluno_modalidades")
    op.drop_index("ix_aluno_modalidades_id", table_name="aluno_modalidades")
    op.drop_table("aluno_modalidades")

    for nome in [
        "ix_notificacoes_treino_enviadas_criado_em",
        "ix_notificacoes_treino_enviadas_data_referencia",
        "ix_notificacoes_treino_enviadas_tipo",
        "ix_notificacoes_treino_enviadas_treino_id",
        "ix_notificacoes_treino_enviadas_usuario_id",
        "ix_notificacoes_treino_enviadas_id",
    ]:
        op.drop_index(nome, table_name="notificacoes_treino_enviadas")
    op.drop_table("notificacoes_treino_enviadas")

    for nome in [
        "ix_preferencias_notificacao_atualizado_em",
        "ix_preferencias_notificacao_usuario_id",
        "ix_preferencias_notificacao_id",
    ]:
        op.drop_index(nome, table_name="preferencias_notificacao")
    op.drop_table("preferencias_notificacao")

    for nome in [
        "ix_push_subscriptions_atualizado_em",
        "ix_push_subscriptions_criado_em",
        "ix_push_subscriptions_ativo",
        "ix_push_subscriptions_endpoint",
        "ix_push_subscriptions_usuario_id",
        "ix_push_subscriptions_id",
    ]:
        op.drop_index(nome, table_name="push_subscriptions")
    op.drop_table("push_subscriptions")

    for nome in [
        "ix_auditoria_administrativa_criado_em",
        "ix_auditoria_administrativa_ip",
        "ix_auditoria_administrativa_entidade",
        "ix_auditoria_administrativa_acao",
        "ix_auditoria_administrativa_professor_id",
        "ix_auditoria_administrativa_id",
    ]:
        op.drop_index(nome, table_name="auditoria_administrativa")
    op.drop_table("auditoria_administrativa")

    for nome in [
        "ix_eventos_rate_limit_criado_em",
        "ix_eventos_rate_limit_bloqueado",
        "ix_eventos_rate_limit_ip",
        "ix_eventos_rate_limit_chave_hash",
        "ix_eventos_rate_limit_tipo",
        "ix_eventos_rate_limit_id",
    ]:
        op.drop_index(nome, table_name="eventos_rate_limit")
    op.drop_table("eventos_rate_limit")

    for nome in [
        "ix_auditoria_logins_criado_em",
        "ix_auditoria_logins_ip",
        "ix_auditoria_logins_sucesso",
        "ix_auditoria_logins_usuario_informado",
        "ix_auditoria_logins_usuario_id",
        "ix_auditoria_logins_id",
    ]:
        op.drop_index(nome, table_name="auditoria_logins")
    op.drop_table("auditoria_logins")

    op.drop_index("ix_treinos_base_titulo", table_name="treinos_base")
    op.drop_index("ix_treinos_base_id", table_name="treinos_base")
    op.drop_table("treinos_base")

    op.drop_index("ix_alunos_nome", table_name="alunos")
    op.drop_index("ix_alunos_id", table_name="alunos")
    op.drop_table("alunos")
