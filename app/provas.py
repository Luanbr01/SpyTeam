"""Cadastro de provas por professores e consulta autenticada pelos alunos."""
import json
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from .models import Prova
from .security import registrar_acao_admin


class ProvaDados(BaseModel):
    nome: str = Field(min_length=2, max_length=160)
    data: date
    modalidade: Literal['Corrida', 'Natação', 'Musculação']
    opcoes: list[str] = Field(min_length=1, max_length=12)
    link_inscricao: str | None = Field(default=None, max_length=2048)

    @field_validator('nome')
    @classmethod
    def nome_valido(cls, value):
        value = ' '.join(value.split())
        if len(value) < 2:
            raise ValueError('Informe o nome da prova.')
        return value

    @field_validator('data')
    @classmethod
    def data_valida(cls, value):
        if not 2000 <= value.year <= 2100:
            raise ValueError('Informe uma data entre 2000 e 2100.')
        return value

    @field_validator('opcoes')
    @classmethod
    def opcoes_validas(cls, values):
        result = []
        for value in values:
            value = ' '.join(value.split())
            if not value or len(value) > 40:
                raise ValueError('Cada distância ou categoria deve ter de 1 a 40 caracteres.')
            if value.casefold() not in [v.casefold() for v in result]:
                result.append(value)
        return result

    @field_validator('link_inscricao')
    @classmethod
    def link_valido(cls, value):
        if not value or not value.strip():
            return None
        value = value.strip()
        try:
            url = urlsplit(value)
            if (url.scheme not in ('http', 'https') or not url.hostname or
                    url.username or url.password or '\\' in value or
                    any(c.isspace() or ord(c) < 32 for c in value)):
                raise ValueError()
            _ = url.port
        except ValueError:
            raise ValueError('Use um link de inscrição completo, iniciado por https:// ou http://.') from None
        return value


def serialize(row):
    return {'id': row.id, 'nome': row.nome, 'data': row.data,
            'modalidade': row.modalidade, 'opcoes': json.loads(row.opcoes_json),
            'link_inscricao': row.link_inscricao}


def apply(row, data):
    row.nome = data.nome
    row.data = data.data.isoformat()
    row.modalidade = data.modalidade
    row.opcoes_json = json.dumps(data.opcoes, ensure_ascii=False)
    row.link_inscricao = data.link_inscricao
    row.atualizado_em = int(time.time())


def build_router(get_current_user, require_professor, get_db):
    router = APIRouter(prefix='/api/provas', tags=['Provas'])

    @router.get('')
    def listar(ano: int | None = Query(default=None, ge=2000, le=2100),
               mes: int | None = Query(default=None, ge=1, le=12),
               usuario=Depends(get_current_user), db=Depends(get_db)):
        if usuario.tipo not in ('aluno', 'professor'):
            raise HTTPException(403, 'Acesso não permitido.')
        if (ano is None) != (mes is None):
            raise HTTPException(422, 'Informe ano e mês juntos.')
        query = db.query(Prova)
        if ano is not None:
            query = query.filter(Prova.data.like(f'{ano:04d}-{mes:02d}-%'))
        else:
            today = datetime.now(ZoneInfo('America/Sao_Paulo')).date().isoformat()
            query = query.filter(Prova.data >= today)
        total = query.count()
        rows = query.order_by(Prova.data, Prova.nome, Prova.id).limit(300).all()
        return JSONResponse({'provas': [serialize(row) for row in rows], 'total': total},
                            headers={'Cache-Control': 'no-store'})

    @router.post('', status_code=201)
    def criar(data: ProvaDados, request: Request, professor=Depends(require_professor), db=Depends(get_db)):
        row = Prova(criado_em=int(time.time()))
        apply(row, data)
        db.add(row)
        db.flush()
        registrar_acao_admin(db, request, professor, 'criar_prova', 'prova',
                            f'Prova cadastrada: {row.nome}', entidade_id=row.id)
        db.commit()
        return serialize(row)

    @router.put('/{prova_id}')
    def editar(prova_id: int, data: ProvaDados, request: Request,
               professor=Depends(require_professor), db=Depends(get_db)):
        row = db.get(Prova, prova_id)
        if not row:
            raise HTTPException(404, 'Prova não encontrada.')
        apply(row, data)
        registrar_acao_admin(db, request, professor, 'editar_prova', 'prova',
                            f'Prova atualizada: {row.nome}', entidade_id=row.id)
        db.commit()
        return serialize(row)

    @router.delete('/{prova_id}')
    def excluir(prova_id: int, request: Request, professor=Depends(require_professor), db=Depends(get_db)):
        row = db.get(Prova, prova_id)
        if not row:
            raise HTTPException(404, 'Prova não encontrada.')
        registrar_acao_admin(db, request, professor, 'excluir_prova', 'prova',
                            f'Prova excluída: {row.nome}', entidade_id=row.id)
        db.delete(row)
        db.commit()
        return {'mensagem': 'Prova excluída.'}

    return router
