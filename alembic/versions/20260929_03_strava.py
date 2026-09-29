"""Credenciais Strava privadas por usuário; não altera treinos existentes."""
from alembic import op
import sqlalchemy as sa

revision = "20260929_03"
down_revision = "20260925_02"
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("strava_conexoes"):
        return  # Compatível com a criação inicial de tabelas do projeto.
    op.create_table(
        "strava_conexoes",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("atleta_id", sa.String(32), unique=True),
        sa.Column("access_token", sa.String()),
        sa.Column("refresh_token", sa.String()),
        sa.Column("expires_at", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scopes", sa.String(), nullable=False, server_default=""),
        sa.Column("state_hash", sa.String(64)),
        sa.Column("session_hash", sa.String(64)),
        sa.Column("state_expires", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_sync", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("strava_conexoes")
