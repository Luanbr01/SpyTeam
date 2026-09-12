# ============================================================
# SCHEMAS.PY
# Dados recebidos pela API
# ============================================================

from pydantic import BaseModel, Field


# ============================================================
# LOGIN
# ============================================================

class Login(BaseModel):

    # Nome de usuário
    usuario: str = Field(
        min_length=1,
        max_length=100
    )

    # Senha
    senha: str = Field(
        min_length=1,
        max_length=200
    )


# ============================================================
# CADASTRO DO ALUNO
# ============================================================

class AlunoCreate(BaseModel):

    # Nome
    nome: str = Field(
        min_length=1,
        max_length=120
    )

    # Nível
    nivel: str = Field(
        min_length=1,
        max_length=50
    )

    modalidade: str = Field(
    min_length=1,
    max_length=50
    )

    # Usuário para login
    usuario: str = Field(
        min_length=3,
        max_length=100
    )

    # Senha para login
    senha: str = Field(
        min_length=4,
        max_length=200
    )


# ============================================================
# AGENDAR TREINO
# ============================================================

class TreinoAgendadoCreate(BaseModel):

    aluno_id: int

    treino_base_id: int

    data_planejada: str


# ============================================================
# TREINO BASE
# ============================================================

class TreinoBaseCreate(BaseModel):

    titulo: str = Field(
        min_length=1,
        max_length=150
    )

    modalidade: str = Field(
        min_length=1,
        max_length=80
    )

    descricao: str = Field(
        min_length=1,
        max_length=1000
    )

    ritmo_alvo: str | None = Field(
        default=None,
        max_length=100
    )


# ============================================================
# TREINO PARA TODOS
# ============================================================

class TreinoEmMassaCreate(BaseModel):

    treino_base_id: int

    data_planejada: str

class FeedbackTreinoCreate(BaseModel):
    nota: int
    dificuldade: str
    comentario: str | None = None

# ============================================================
# FEEDBACK DO TREINO
# ============================================================

# ============================================================
# PLANEJAMENTO SEMANAL
# ============================================================

class TreinoDiaSemana(BaseModel):

    # Dia da semana
    # 0 = segunda
    # 1 = terça
    # 2 = quarta
    # 3 = quinta
    # 4 = sexta
    # 5 = sábado
    # 6 = domingo

    dia: int

    # ID do treino base
    treino_base_id: int

