from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import engine, SessionLocal
import models
import schemas

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
@app.get("/")
def painel_professor():
    return FileResponse("index.html")

# Função que gerencia a abertura e fechamento da conexão com o banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
# Rota que recebe o envio do professor e salva no banco
@app.post("/api/treinos")
def agendar_treino(treino: schemas.TreinoAgendadoCreate, db: Session = Depends(get_db)):
    novo_treino = models.TreinoAgendado(
        aluno_id=treino.aluno_id,
        treino_base_id=treino.treino_base_id,
        data_planejada=treino.data_planejada
    )
    db.add(novo_treino)
    db.commit()
    db.refresh(novo_treino)
    return novo_treino

@app.post("/api/alunos")
def criar_aluno(aluno: schemas.AlunoCreate, db: Session = Depends(get_db)):
    novo_aluno = models.Aluno(nome=aluno.nome, nivel=aluno.nivel)
    db.add(novo_aluno)
    db.commit()
    db.refresh(novo_aluno)
    return novo_aluno

@app.get("/api/alunos")
def listar_alunos(db: Session = Depends(get_db)):
    return db.query(models.Aluno).all()

@app.get("/api/treinos-base")
def listar_treinos_base(db: Session = Depends(get_db)):
    return db.query(models.TreinoBase).all()

@app.get("/api/treinos")
def listar_treinos_agendados(db: Session = Depends(get_db)):
    return db.query(models.TreinoAgendado).all()

@app.post("/api/treinos/em-massa")
def enviar_treino_em_massa(dados: schemas.TreinoEmMassaCreate, db: Session = Depends(get_db)):
    # 1. Busca todos os alunos cadastrados no banco
    alunos = db.query(models.Aluno).all()
    
    if not alunos:
        return {"mensagem": "Nenhum aluno cadastrado para receber o treino."}
    
    treinos_criados = []

    # 2. Para cada aluno encontrado, gera um agendamento com o mesmo treino base
    for aluno in alunos:
        novo_agendamento = models.TreinoAgendado(
            aluno_id=aluno.id,
            treino_base_id=dados.treino_base_id,
            data_planejada=dados.data_planejada
        )
        db.add(novo_agendamento)
        treinos_criados.append(novo_agendamento)

    # 3. Salva tudo de uma vez no banco de dados SQLite
    db.commit()
    
    return {
        "mensagem": f"Treino enviado com sucesso para {len(treinos_criados)} alunos!",
        "total_enviados": len(treinos_criados)
    }

@app.get("/api/alunos/{aluno_id}/treinos")
def listar_treinos_do_aluno(aluno_id: int, db: Session = Depends(get_db)):
    # Filtra a tabela de agendamentos buscando apenas as linhas com o ID do aluno
    treinos = db.query(models.TreinoAgendado).filter(models.TreinoAgendado.aluno_id == aluno_id).all()
    
    if not treinos:
        return {"mensagem": "Nenhum treino encontrado para este aluno."}
        
    return treinos

from fastapi import HTTPException

@app.patch("/api/treinos/{treino_id}/concluir")
def concluir_treino(treino_id: int, db: Session = Depends(get_db)):
    # 1. Busca o agendamento específico no banco de dados
    treino = db.query(models.TreinoAgendado).filter(models.TreinoAgendado.id == treino_id).first()
    
    # 2. Retorna um erro amigável se o treino não existir
    if not treino:
        raise HTTPException(status_code=404, detail="Treino não encontrado.")
    
    # 3. Altera o status para verdadeiro e salva a atualização
    treino.concluido = True
    db.commit()
    db.refresh(treino)
    
    return {"mensagem": "Treino marcado como concluído!", "treino": treino}