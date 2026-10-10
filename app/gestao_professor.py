"""Leitura do planejamento e rascunhos; salvar/carregar nunca agenda treinos."""
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from . import models

MODALIDADES = ('Corrida', 'Natação', 'Musculação')

class ItemRascunho(BaseModel):
    dia: int = Field(ge=0, le=4)
    treino_base_id: int = Field(gt=0)

class RascunhoInput(BaseModel):
    itens: list[ItemRascunho] = Field(max_length=15)
    versao: int = Field(ge=0)


def segunda_valida(valor):
    try:
        dia = date.fromisoformat(valor)
        if dia.weekday() != 0 or dia.isoformat() != valor:
            raise ValueError
        return dia
    except (TypeError, ValueError):
        raise HTTPException(400, 'Escolha uma segunda-feira válida.')


def contexto_semana(db, segunda):
    alunos = db.query(models.Aluno).order_by(models.Aluno.nome, models.Aluno.id).all()
    vinculos = db.query(models.AlunoModalidade).all()
    mapa = {a.id: set() for a in alunos}
    for vinculo in vinculos:
        if vinculo.aluno_id in mapa and vinculo.modalidade in MODALIDADES:
            mapa[vinculo.aluno_id].add(vinculo.modalidade)
    agendados = db.query(models.TreinoAgendado).filter(
        models.TreinoAgendado.data_planejada >= segunda.isoformat(),
        models.TreinoAgendado.data_planejada <= (segunda + timedelta(days=4)).isoformat()).all()
    cobertura = {(t.aluno_id, t.modalidade) for t in agendados}
    destinatarios = {m: [{'id': a.id, 'nome': a.nome} for a in alunos if m in mapa[a.id]] for m in MODALIDADES}
    pendencias = []
    for aluno in alunos:
        faltantes = [m for m in MODALIDADES if m in mapa[aluno.id] and (aluno.id, m) not in cobertura]
        if faltantes or not mapa[aluno.id]:
            pendencias.append({'id': aluno.id, 'nome': aluno.nome, 'modalidades_sem_treino': faltantes,
                              'sem_modalidade': not bool(mapa[aluno.id]),
                              'sem_treino': bool(faltantes) and len(faltantes) == len(mapa[aluno.id])})
    return {'data_segunda': segunda.isoformat(), 'destinatarios': destinatarios, 'pendencias': pendencias,
            'total_alunos': len(alunos), 'total_agendamentos': len(agendados)}


def build_router(require_professor, get_db):
    router = APIRouter(prefix='/api/gestao-professor', tags=['Gestão do professor'])

    @router.get('/semana')
    def semana(data_segunda: str | None = None, db=Depends(get_db), professor=Depends(require_professor)):
        hoje = datetime.now(ZoneInfo('America/Sao_Paulo')).date()
        segunda = segunda_valida(data_segunda) if data_segunda else hoje - timedelta(days=hoje.weekday())
        return contexto_semana(db, segunda)

    @router.get('/planejamento')
    def planejamento(data_segunda: str, db=Depends(get_db), professor=Depends(require_professor)):
        segunda = segunda_valida(data_segunda)
        linhas = db.query(models.TreinoAgendado.treino_base_id, models.TreinoAgendado.data_planejada).filter(
            models.TreinoAgendado.data_planejada >= segunda.isoformat(),
            models.TreinoAgendado.data_planejada <= (segunda + timedelta(days=4)).isoformat()).distinct().all()
        bases = {t.id: t for t in db.query(models.TreinoBase).filter(models.TreinoBase.modalidade.in_(MODALIDADES)).all()}
        selecoes = {}
        for treino_id, data in linhas:
            if treino_id not in bases:
                continue
            dia = (date.fromisoformat(data) - segunda).days
            selecoes.setdefault((dia, bases[treino_id].modalidade), set()).add(treino_id)
        conflitos = [{'dia': k[0], 'modalidade': k[1]} for k, ids in selecoes.items() if len(ids) > 1]
        itens = [{'dia': k[0], 'treino_base_id': next(iter(ids))} for k, ids in selecoes.items() if len(ids) == 1]
        return {'itens': itens, 'conflitos': conflitos}

    @router.get('/rascunho')
    def obter_rascunho(data_segunda: str, db=Depends(get_db), professor=Depends(require_professor)):
        segunda_valida(data_segunda)
        row = db.query(models.PlanejamentoRascunho).filter_by(professor_id=professor.id, data_segunda=data_segunda).first()
        return {'itens': json.loads(row.itens_json) if row else [], 'versao': row.versao if row else 0}

    @router.put('/rascunho')
    def salvar_rascunho(data_segunda: str, dados: RascunhoInput, db=Depends(get_db), professor=Depends(require_professor)):
        segunda_valida(data_segunda)
        ids = [item.treino_base_id for item in dados.itens]
        bases = {t.id: t for t in db.query(models.TreinoBase).filter(models.TreinoBase.id.in_(ids)).all()} if ids else {}
        vistos = set()
        for item in dados.itens:
            treino = bases.get(item.treino_base_id)
            if not treino or treino.modalidade not in MODALIDADES:
                raise HTTPException(400, 'Um treino selecionado não está mais disponível. Atualize a página.')
            chave = (item.dia, treino.modalidade)
            if chave in vistos:
                raise HTTPException(400, 'Escolha apenas um treino por dia e modalidade.')
            vistos.add(chave)
        query = db.query(models.PlanejamentoRascunho).filter_by(professor_id=professor.id, data_segunda=data_segunda)
        conteudo = json.dumps([i.model_dump() for i in dados.itens])
        nova_versao = dados.versao + 1
        if dados.versao:
            atualizado = query.filter(models.PlanejamentoRascunho.versao == dados.versao).update(
                {'itens_json': conteudo, 'versao': nova_versao}, synchronize_session=False)
            if not atualizado:
                raise HTTPException(409, 'O rascunho mudou em outra aba. Carregue a versão salva antes de continuar.')
        else:
            db.add(models.PlanejamentoRascunho(professor_id=professor.id, data_segunda=data_segunda,
                                             itens_json=conteudo, versao=1))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, 'Já existe um rascunho salvo nesta semana. Carregue-o antes de continuar.')
        return {'versao': nova_versao, 'mensagem': 'Rascunho salvo. Nenhum treino foi enviado.'}

    return router
