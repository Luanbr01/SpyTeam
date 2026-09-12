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

from .database import Base


# ============================================================
# ALUNO
# ============================================================

class Aluno(Base):

    __tablename__ = "alunos"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    nome = Column(
        String,
        index=True,
        nullable=False
    )

    nivel = Column(
        String,
        nullable=False
    )

    modalidade = Column(
        String,
        nullable=True
    )


# ============================================================
# USUÁRIO
# ============================================================

class Usuario(Base):

    __tablename__ = "usuarios"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    usuario = Column(
        String,
        unique=True,
        index=True,
        nullable=False
    )

    senha_hash = Column(
        String,
        nullable=False
    )

    tipo = Column(
        String,
        nullable=False
    )

    aluno_id = Column(
        Integer,
        ForeignKey("alunos.id"),
        unique=True,
        nullable=True
    )

    aluno = relationship(
        "Aluno"
    )


# ============================================================
# TREINO BASE
# ============================================================

class TreinoBase(Base):

    __tablename__ = "treinos_base"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    titulo = Column(
        String,
        index=True,
        nullable=False
    )

    modalidade = Column(
        String,
        nullable=False
    )

    descricao = Column(
        String,
        nullable=False
    )

    ritmo_alvo = Column(
        String,
        nullable=True
    )


# ============================================================
# TREINO AGENDADO
# ============================================================

class TreinoAgendado(Base):

    __tablename__ = "treinos_agendados"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    aluno_id = Column(
        Integer,
        ForeignKey("alunos.id"),
        nullable=False
    )

    treino_base_id = Column(
        Integer,
        ForeignKey("treinos_base.id"),
        nullable=False
    )

    data_planejada = Column(
        String,
        nullable=False
    )

    # ========================================================
    # STATUS
    # ========================================================

    concluido = Column(
        Boolean,
        default=False,
        nullable=False
    )

    # ========================================================
    # FEEDBACK DO ALUNO
    # ========================================================

    feedback_nota = Column(
        Integer,
        nullable=True
    )

    feedback_comentario = Column(
        String,
        nullable=True
    )

    feedback_dificuldade = Column(
        String,
        nullable=True
    )

    # ========================================================
    # RELACIONAMENTOS
    # ========================================================

    aluno = relationship(
        "Aluno"
    )

    treino_base = relationship(
        "TreinoBase"
    )