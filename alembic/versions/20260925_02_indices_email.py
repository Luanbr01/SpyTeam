"""garantir índices de e-mail e verificação

Revision ID: 20260925_02
Revises: 20260925_01
Create Date: 2026-09-25

Esta revisão é propositalmente idempotente para a transição de bancos que já
possuíam estes índices antes da adoção do Alembic.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "20260925_02"
down_revision: Union[str, Sequence[str], None] = "20260925_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_email_nocase
            ON usuarios (lower(email))
            WHERE email IS NOT NULL AND btrim(email) <> ''
            """
        )
    else:
        op.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_usuarios_email_nocase
            ON usuarios(email COLLATE NOCASE)
            WHERE email IS NOT NULL AND email <> ''
            """
        )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_verificacoes_email_usuario_ativo
        ON verificacoes_email(usuario_id, usado, criado_em)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_verificacoes_email_usuario_ativo")
    op.execute("DROP INDEX IF EXISTS ux_usuarios_email_nocase")
