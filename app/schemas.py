# ============================================================
# SCHEMAS.PY
# Dados recebidos pela API
# ============================================================

from pydantic import BaseModel, Field
from typing import Optional

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
# E-MAIL DO ALUNO
# ============================================================

class CadastroEmailAluno(BaseModel):

    email: str = Field(
        min_length=5,
        max_length=254
    )

    confirmar_email: str = Field(
        min_length=5,
        max_length=254
    )


# ============================================================
# RECUPERAÇÃO DE SENHA
# ============================================================

class SolicitarRecuperacaoSenha(BaseModel):

    email: str = Field(
        min_length=5,
        max_length=254
    )


class RedefinirSenha(BaseModel):

    token: str = Field(
        min_length=20,
        max_length=300
    )

    nova_senha: str = Field(
        min_length=4,
        max_length=200
    )

    confirmar_senha: str = Field(
        min_length=4,
        max_length=200
    )


# ============================================================
# ALTERAR SENHA DO ALUNO
# ============================================================

class AlterarSenhaAluno(BaseModel):

    senha_atual: str = Field(
        min_length=1,
        max_length=200
    )

    nova_senha: str = Field(
        min_length=4,
        max_length=200
    )

    confirmar_senha: str = Field(
        min_length=4,
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

    modalidades: list[str] = Field(
        min_length=1,
        max_length=3
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
# ATUALIZAR MODALIDADES DO ALUNO
# ============================================================

class AlunoModalidadesUpdate(BaseModel):

    modalidades: list[str] = Field(
        min_length=1,
        max_length=3
    )


# ============================================================
# AGENDAR TREINO
# ============================================================

class TreinoAgendadoCreate(BaseModel):

    aluno_id: int

    treino_base_id: int

    data_planejada: str


class ReagendarTreinoCreate(BaseModel):
    data_planejada: str = Field(min_length=10, max_length=10)


class DuplicarSemanaCreate(BaseModel):
    origem_segunda: str = Field(min_length=10, max_length=10)
    destino_segunda: str = Field(min_length=10, max_length=10)


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



# ============================================================
# PWA / WEB PUSH
# ============================================================

class PushSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=10, max_length=1000)
    auth: str = Field(min_length=5, max_length=500)


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=20, max_length=4000)
    keys: PushSubscriptionKeys


class PushSubscriptionRemove(BaseModel):
    endpoint: str = Field(min_length=20, max_length=4000)

class PushPreferenciasUpdate(BaseModel):
    novo_treino: bool = True
    lembrete_treino: bool = True
    treino_pendente: bool = True
    horario_lembrete: str = "07:00"
    horario_pendente: str = "19:00"
    timezone: str = "America/Sao_Paulo"

