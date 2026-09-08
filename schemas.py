from pydantic import BaseModel

class TreinoAgendadoCreate(BaseModel):
    aluno_id: int
    treino_base_id: int
    data_planejada: str

class AlunoCreate(BaseModel):
    nome: str
    nivel: str

class TreinoBaseCreate(BaseModel):
    titulo: str
    modalidade: str
    descricao: str
    ritmo_alvo: str | None = None

class TreinoEmMassaCreate(BaseModel):
        treino_base_id: int
        data_planejada: str