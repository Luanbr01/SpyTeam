import unittest
import test_strava as fixture
from app.database import SessionLocal
from app import models

class GestaoTests(unittest.TestCase):
    login = fixture.StravaTests.login
    def setUp(self):
        with SessionLocal() as db:
            for cls in (models.PlanejamentoRascunho,models.TreinoAgendado,models.TreinoBase,models.AlunoModalidade): db.query(cls).delete()
            db.commit()
        fixture.StravaTests.setUp(self)
        self.login(3)
        with SessionLocal() as db:
            db.add_all([models.AlunoModalidade(aluno_id=1,modalidade='Corrida'),models.AlunoModalidade(aluno_id=1,modalidade='Natação'),models.AlunoModalidade(aluno_id=2,modalidade='Corrida'),models.TreinoBase(id=1,titulo='Leve',modalidade='Corrida',descricao='Correr')]);db.commit()
        self.semana='2090-10-09'
        self.url='/api/gestao-professor/rascunho?data_segunda='+self.semana

    def test_draft_and_concurrent_update(self):
        body={'itens':[{'dia':0,'treino_base_id':1}],'versao':0}
        self.assertEqual(self.client.put(self.url,json=body,headers=self.headers).status_code,200)
        self.assertEqual(self.client.get(self.url).json()['itens'],body['itens'])
        self.assertEqual(self.client.put(self.url,json=body,headers=self.headers).status_code,409)
        body['versao']=1
        self.assertEqual(self.client.put(self.url,json=body,headers=self.headers).json()['versao'],2)
        with SessionLocal() as db: self.assertEqual(db.query(models.TreinoAgendado).count(),0)

    def test_permissions_validation_and_isolation(self):
        self.assertEqual(self.client.put(self.url,json={'itens':[],'versao':0}).status_code,403)
        self.login(1);self.assertEqual(self.client.get(self.url).status_code,403);self.login(3)
        for itens in [[{'dia':5,'treino_base_id':1}],[{'dia':0,'treino_base_id':999}],[{'dia':0,'treino_base_id':1}]*2]:
            self.assertIn(self.client.put(self.url,json={'itens':itens,'versao':0},headers=self.headers).status_code,[400,422])
        self.assertEqual(self.client.get(self.url.replace('2090-10-09','2090-10-10')).status_code,400)
        self.client.put(self.url,json={'itens':[],'versao':0},headers=self.headers)
        with SessionLocal() as db:
            db.add(models.Usuario(id=4,usuario='professor2',senha_hash='x',tipo='professor'));db.commit()
        from app.auth import criar_token,COOKIE_NAME
        self.client.cookies.set(COOKIE_NAME,criar_token(4,'professor',0))
        self.assertEqual(self.client.get(self.url).json()['versao'],0)

    def test_week_recipients_partial_coverage_and_reuse(self):
        url='/api/gestao-professor/semana?data_segunda='+self.semana
        data=self.client.get(url).json()
        self.assertEqual(len(data['destinatarios']['Corrida']),2)
        self.assertEqual(len(data['destinatarios']['Natação']),1)
        with SessionLocal() as db:
            for aluno in (1,2): db.add(models.TreinoAgendado(aluno_id=aluno,treino_base_id=1,titulo='Leve',modalidade='Corrida',descricao='Correr',data_planejada=self.semana))
            db.commit()
        pendencias=self.client.get(url).json()['pendencias']
        self.assertEqual(pendencias[0]['modalidades_sem_treino'],['Natação'])
        self.assertFalse(pendencias[0]['sem_treino'])
        reuse=self.client.get('/api/gestao-professor/planejamento?data_segunda='+self.semana).json()
        self.assertEqual(reuse['itens'],[{'dia':0,'treino_base_id':1}])
        with SessionLocal() as db:
            self.assertEqual(db.query(models.TreinoAgendado).count(),2)
            db.add(models.TreinoBase(id=2,titulo='Outro',modalidade='Corrida',descricao='Outro'));db.commit()
            db.add(models.TreinoAgendado(aluno_id=1,treino_base_id=2,titulo='Outro',modalidade='Corrida',descricao='Outro',data_planejada=self.semana));db.commit()
        reuse=self.client.get('/api/gestao-professor/planejamento?data_segunda='+self.semana).json()
        self.assertEqual(reuse['conflitos'],[{'dia':0,'modalidade':'Corrida'}])

    def test_list_and_pages(self):
        rows=self.client.get('/api/alunos').json()
        self.assertEqual(rows[0]['modalidades'],['Corrida','Natação'])
        for route,needle in [('/alunos','buscaAlunos'),('/treinos-base','buscaTreinos'),('/planejamento-semanal','estadoRascunho'),('/home','pendenciasSemana')]:
            r=self.client.get(route);self.assertEqual(r.status_code,200);self.assertIn(needle,r.text)
