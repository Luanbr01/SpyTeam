"""Provas divulgadas pelo professor."""
from alembic import op
import sqlalchemy as sa

revision = '20260929_04'
down_revision = '20260929_03'
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table('provas'):
        return
    op.create_table('provas',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nome', sa.String(160), nullable=False),
        sa.Column('data', sa.String(10), nullable=False),
        sa.Column('modalidade', sa.String(30), nullable=False),
        sa.Column('opcoes_json', sa.String(), nullable=False),
        sa.Column('link_inscricao', sa.String(2048)),
        sa.Column('criado_em', sa.Integer(), nullable=False),
        sa.Column('atualizado_em', sa.Integer(), nullable=False))
    op.create_index('ix_provas_data', 'provas', ['data'])


def downgrade():
    op.drop_index('ix_provas_data', table_name='provas')
    op.drop_table('provas')
