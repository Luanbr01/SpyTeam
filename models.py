# ============================================================
# MODELS.PY
# Modelos do banco de dados do SpyTeam
# ============================================================

from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Boolean
)

from sqlalchemy.orm import relationship

from database import Base


# ============================================================
# ALUNO
# ============================================================

class Aluno(Base):

    __tablename__ = "alunos"

    # ID do aluno
    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Nome
    nome = Column(
        String,
        index=True,
        nullable=False
    )

    # Nível
    nivel = Column(
        String,
        nullable=False
    )


# ============================================================
# USUÁRIO
# ============================================================
#
# Essa tabela representa quem pode fazer login.
#
# tipo pode ser:
#
# professor
# aluno
#
# Quando for professor:
# aluno_id = NULL
#
# Quando for aluno:
# aluno_id = ID do aluno
#
# ============================================================

class Usuario(Base):

    __tablename__ = "usuarios"

    # ID
    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Usuário de login
    usuario = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    # Senha protegida
    senha_hash = Column(
        String,
        nullable=False
    )

    # Tipo da conta
    tipo = Column(
        String,
        nullable=False
    )

    # Relação com o aluno
    #
    # Para professor permanece NULL.
    aluno_id = Column(
        Integer,
        ForeignKey("alunos.id"),
        unique=True,
        nullable=True
    )

    # Relação entre Usuario e Aluno
    aluno = relationship(
        "Aluno"
    )


# ============================================================
# TREINO BASE
# ============================================================

class TreinoBase(Base):

    __tablename__ = "treinos_base"

    # ID
    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Nome do treino
    titulo = Column(
        String,
        index=True,
        nullable=False
    )

    # Modalidade
    modalidade = Column(
        String,
        nullable=False
    )

    # Descrição
    descricao = Column(
        String,
        nullable=False
    )

    # Ritmo alvo
    ritmo_alvo = Column(
        String,
        nullable=True
    )


# ============================================================
# TREINO AGENDADO
# ============================================================

class TreinoAgendado(Base):

    __tablename__ = "treinos_agendados"

    # ID do treino agendado
    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Qual aluno receberá esse treino
    aluno_id = Column(
        Integer,
        ForeignKey("alunos.id"),
        nullable=False
    )

    # Qual treino base foi utilizado
    treino_base_id = Column(
        Integer,
        ForeignKey("treinos_base.id"),
        nullable=False
    )

    # Data planejada
    data_planejada = Column(
        String,
        nullable=False
    )

    # Indica se foi concluído
    concluido = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # Relação com aluno
    aluno = relationship(
        "Aluno"
    )

    # Relação com treino base
    treino_base = relationship(
        "TreinoBase"
    )