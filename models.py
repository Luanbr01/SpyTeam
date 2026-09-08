from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from database import Base

class Aluno(Base):
    __tablename__ = "alunos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    nivel = Column(String) 

# 1. O Catálogo (Os seus "Botões Pré-programados")
class TreinoBase(Base):
    __tablename__ = "treinos_base"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, index=True)      # Nome que vai aparecer no botão (Ex: "Tiro 10x400m")
    modalidade = Column(String)              # Corrida, Natação
    descricao = Column(String)               # Detalhes do treino
    ritmo_alvo = Column(String, nullable=True)

# 2. O Envio / Agenda (A relação entre o treino e o aluno)
class TreinoAgendado(Base):
    __tablename__ = "treinos_agendados"

    id = Column(Integer, primary_key=True, index=True)
    aluno_id = Column(Integer, ForeignKey("alunos.id"))
    treino_base_id = Column(Integer, ForeignKey("treinos_base.id"))
    data_planejada = Column(String)          # Dia que o aluno vai executar
    concluido = Column(Boolean, default=False) # Para o professor receber o feedback depois
    
    aluno = relationship("Aluno")
    treino_base = relationship("TreinoBase")