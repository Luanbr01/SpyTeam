"""Testes locais: python -m unittest discover -s tests -p test_provas.py -v"""
import unittest
import test_strava as fixture
from app.database import SessionLocal
from app.models import Prova


class ProvasTests(unittest.TestCase):
    login = fixture.StravaTests.login

    def setUp(self):
        fixture.StravaTests.setUp(self)
        with SessionLocal() as db:
            db.query(Prova).delete(); db.commit()
        self.login(3)
        self.payload = {'nome': 'Corrida da Orla', 'data': '2090-10-13', 'modalidade': 'Corrida',
                        'opcoes': ['5 km', '10 km'], 'link_inscricao': 'https://example.com/inscricao'}

    def create(self):
        r = self.client.post('/api/provas', json=self.payload, headers=self.headers)
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_crud_and_student_read_only(self):
        row = self.create()
        self.login(1)
        r = self.client.get('/api/provas?ano=2090&mes=10')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['provas'][0]['opcoes'], ['5 km','10 km'])
        for method,path in [('post','/api/provas'),('put',f'/api/provas/{row["id"]}'),('delete',f'/api/provas/{row["id"]}')]:
            kwargs={'headers':self.headers}
            if method!='delete': kwargs['json']=self.payload
            self.assertEqual(getattr(self.client,method)(path,**kwargs).status_code,403)
        self.login(3)
        self.payload.update(data='2090-11-02', opcoes=['21 km'])
        self.assertEqual(self.client.put(f'/api/provas/{row["id"]}',json=self.payload,headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/provas?ano=2090&mes=10').json()['provas'],[])
        self.assertEqual(len(self.client.get('/api/provas?ano=2090&mes=11').json()['provas']),1)
        self.assertEqual(self.client.delete(f'/api/provas/{row["id"]}',headers=self.headers).status_code,200)
        self.assertEqual(self.client.get('/api/provas').json()['provas'],[])

    def test_validation(self):
        for change in [{'nome':'  '},{'opcoes':[]},{'opcoes':[' ']},{'data':'2026-02-29'},
                       {'modalidade':'Triátlon'},{'link_inscricao':'javascript:alert(1)'},
                       {'link_inscricao':'https://user:password@example.com'},
                       {'link_inscricao':'https://example.com\\@evil.example'},
                       {'opcoes':['x'*41]}]:
            r=self.client.post('/api/provas',json={**self.payload,**change},headers=self.headers)
            self.assertEqual(r.status_code,422,str(change)+r.text)
        self.assertEqual(self.client.get('/api/provas?ano=2090').status_code,422)
        self.assertEqual(self.client.get('/api/provas?ano=2090&mes=13').status_code,422)

    def test_csrf_session_and_no_link(self):
        self.assertEqual(self.client.post('/api/provas',json=self.payload).status_code,403)
        self.payload['link_inscricao']=''
        self.payload['opcoes']=['5 km','5 km','7 km']
        data=self.create()
        self.assertIsNone(data['link_inscricao'])
        self.assertEqual(data['opcoes'],['5 km','7 km'])
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/provas').status_code,401)

    def test_upcoming_and_past_calendar(self):
        self.payload['data']='2000-01-01'; self.create()
        self.assertEqual(self.client.get('/api/provas').json()['provas'],[])
        self.assertEqual(len(self.client.get('/api/provas?ano=2000&mes=1').json()['provas']),1)

    def test_templates_and_existing_calendar(self):
        response=self.client.get('/calendario')
        self.assertEqual(response.status_code,200)
        self.assertIn('id="novaProva"',response.text)
        self.assertEqual(self.client.get('/api/calendario?ano=2090&mes=10').status_code,200)
        self.login(1)
        response=self.client.get('/aluno/provas')
        self.assertEqual(response.status_code,200)
        self.assertIn('Próximas provas',response.text)
        self.assertIn('id="calendarioGrid"',response.text)
        self.assertNotIn('id="provaForm"',response.text)
        self.assertIn('href="/aluno/provas"',self.client.get('/aluno').text)
        self.assertEqual(self.client.get('/api/calendario?ano=2090&mes=10').status_code,403)

if __name__=='__main__': unittest.main()
