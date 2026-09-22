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

    email = Column(
        String,
        nullable=True,
        index=True
    )

    # Incrementado quando a senha muda. Tokens de sessão antigos
    # deixam de ser aceitos imediatamente.
    session_version = Column(
        Integer,
        default=0,
        nullable=False
    )

    aluno = relationship(
        "Aluno"
    )


# ============================================================
# RECUPERAÇÃO DE SENHA
# ============================================================

class RecuperacaoSenha(Base):

    __tablename__ = "recuperacoes_senha"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=False,
        index=True
    )

    token_hash = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    expira_em = Column(
        Integer,
        nullable=False
    )

    criado_em = Column(
        Integer,
        nullable=False
    )

    usado = Column(
        Boolean,
        default=False,
        nullable=False
    )

    usuario = relationship(
        "Usuario"
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

    # ========================================================
    # SNAPSHOT DO TREINO BASE
    # ========================================================
    # Guarda como o treino era no momento do agendamento.
    # Assim, editar o treino base no futuro não altera os treinos que já foram enviados aos alunos.

    titulo = Column(
        String,
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

# ============================================================
# AUDITORIA DE LOGIN
# ============================================================

class AuditoriaLogin(Base):

    __tablename__ = "auditoria_logins"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Mantemos apenas o ID, sem FK, para preservar o histórico mesmo
    # se uma conta de aluno for excluída posteriormente.
    usuario_id = Column(
        Integer,
        nullable=True,
        index=True
    )

    usuario_informado = Column(
        String,
        nullable=False,
        index=True
    )

    sucesso = Column(
        Boolean,
        nullable=False,
        index=True
    )

    motivo = Column(
        String,
        nullable=False
    )

    ip = Column(
        String,
        nullable=False,
        index=True
    )

    user_agent = Column(
        String,
        nullable=True
    )

    criado_em = Column(
        Integer,
        nullable=False,
        index=True
    )


# ============================================================
# EVENTOS OPERACIONAIS DE RATE LIMIT
# ============================================================

class EventoRateLimit(Base):

    __tablename__ = "eventos_rate_limit"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    tipo = Column(
        String,
        nullable=False,
        index=True
    )

    # Para recuperação, o e-mail não é salvo nesta tabela: somente
    # SHA-256 do identificador normalizado.
    chave_hash = Column(
        String,
        nullable=False,
        index=True
    )

    ip = Column(
        String,
        nullable=False,
        index=True
    )

    bloqueado = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    criado_em = Column(
        Integer,
        nullable=False,
        index=True
    )


# ============================================================
# HISTÓRICO DE ALTERAÇÕES ADMINISTRATIVAS
# ============================================================

class AuditoriaAdministrativa(Base):

    __tablename__ = "auditoria_administrativa"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    # Sem FK de propósito: o histórico não deve desaparecer ou bloquear
    # exclusões futuras caso uma conta administrativa seja substituída.
    professor_id = Column(
        Integer,
        nullable=True,
        index=True
    )

    professor_usuario = Column(
        String,
        nullable=False
    )

    acao = Column(
        String,
        nullable=False,
        index=True
    )

    entidade = Column(
        String,
        nullable=False,
        index=True
    )

    entidade_id = Column(
        Integer,
        nullable=True
    )

    descricao = Column(
        String,
        nullable=False
    )

    dados_json = Column(
        String,
        nullable=True
    )

    ip = Column(
        String,
        nullable=False,
        index=True
    )

    user_agent = Column(
        String,
        nullable=True
    )

    criado_em = Column(
        Integer,
        nullable=False,
        index=True
    )
