"""Executar: python -m unittest discover -s tests -p test_strava.py -v
Usa banco temporário e respostas simuladas; nunca acessa contas reais.
"""
import os
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from unittest.mock import patch

TMP = tempfile.TemporaryDirectory()
os.environ['DATABASE_URL'] = ''
os.environ['DATABASE_PATH'] = str(Path(TMP.name) / 'test.db')
os.environ['SPYTEAM_SECRET'] = 'test-only-not-production-' * 3
os.environ['STRAVA_CLIENT_ID'] = '123'
os.environ['STRAVA_CLIENT_SECRET'] = 'test-only'
os.environ['STRAVA_REDIRECT_URI'] = 'https://www.spyteam.com.br/api/strava/callback'

from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Aluno, Usuario, StravaConexao
from app.auth import COOKIE_NAME, criar_token
from app.security import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, criar_token_csrf
from app import strava


class StravaTests(unittest.TestCase):
    def setUp(self):
        with SessionLocal() as db:
            db.query(StravaConexao).delete()
            db.query(Usuario).delete()
            db.query(Aluno).delete()
            for i in (1, 2):
                db.add(Aluno(id=i, nome=f'Aluno {i}', nivel='iniciante'))
                db.add(Usuario(id=i, usuario=f'aluno{i}', senha_hash='x', tipo='aluno', aluno_id=i, email=f'a{i}@example.com', email_verificado=True))
            db.add(Usuario(id=3, usuario='professor', senha_hash='x', tipo='professor'))
            db.commit()
        self.client = TestClient(app)
        self.login(1)

    def login(self, uid):
        self.client.cookies.clear()
        self.client.cookies.set(COOKIE_NAME, criar_token(uid, 'professor' if uid == 3 else 'aluno', 0))
        token = criar_token_csrf()
        self.client.cookies.set(CSRF_COOKIE_NAME, token)
        self.headers = {CSRF_HEADER_NAME: token}

    def post(self, route):
        return self.client.post('/api/strava/' + route, headers=self.headers)

    def begin(self):
        r = self.post('connect')
        self.assertEqual(r.status_code, 200, r.text)
        return parse_qs(urlparse(r.json()['url']).query)['state'][0]

    def tokens(self, athlete=123):
        return {'athlete': {'id': athlete}, 'access_token': 'access-plain',
                'refresh_token': 'refresh-plain', 'expires_at': int(time.time()) + 3600}

    def callback(self, state, scope='read,activity:read'):
        return self.client.get('/api/strava/callback', params={'state': state, 'code': 'code', 'scope': scope}, follow_redirects=False)

    def link(self):
        state = self.begin()
        with patch('app.strava.api', return_value=self.tokens()):
            r = self.callback(state)
        self.assertIn('connected', r.headers['location'])

    def test_auth_and_csrf(self):
        self.assertEqual(self.client.post('/api/strava/connect').status_code, 403)
        self.login(3)
        self.assertEqual(self.client.get('/api/strava/status').status_code, 403)
        self.login(1)
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/strava/status').status_code, 401)

    def test_callback_encryption_and_replay(self):
        state = self.begin()
        with patch('app.strava.api', return_value=self.tokens()) as remote:
            self.assertIn('connected', self.callback(state).headers['location'])
            self.assertIn('expired', self.callback(state).headers['location'])
            self.assertEqual(remote.call_count, 1)
        with SessionLocal() as db:
            row = db.get(StravaConexao, 1)
            self.assertNotEqual(row.access_token, 'access-plain')
            self.assertEqual(strava.decrypt(row.refresh_token), 'refresh-plain')
        self.assertNotIn('access-plain', self.client.get('/api/strava/status').text)

    def test_state_wrong_user_expired_and_scope(self):
        state = self.begin()
        self.login(2)
        with patch('app.strava.api') as remote:
            self.assertIn('expired', self.callback(state).headers['location'])
            remote.assert_not_called()
        self.login(1)
        state = self.begin()
        with SessionLocal() as db:
            db.get(StravaConexao, 1).state_expires = 1
            db.commit()
        self.assertIn('expired', self.callback(state).headers['location'])
        state = self.begin()
        with patch('app.strava.api') as remote:
            self.assertIn('scope', self.callback(state, 'read').headers['location'])
            remote.assert_not_called()

    def test_student_isolation_and_limit(self):
        self.link()
        self.login(2)
        self.assertFalse(self.client.get('/api/strava/status').json()['connected'])
        self.assertEqual(self.post('sync').status_code, 409)
        self.login(1)
        with patch('app.strava.api', return_value=[{'id': 7, 'name': '<script>test</script>', 'distance': 1500}]) as remote:
            r = self.post('sync')
            self.assertEqual(r.status_code, 200, r.text)
            self.assertEqual(r.headers['cache-control'], 'no-store')
            self.assertEqual(r.json()['activities'][0]['id'], '7')
            self.assertEqual(self.post('sync').status_code, 429)
            self.assertEqual(remote.call_count, 1)

    def test_refresh_persisted_when_activity_request_fails(self):
        self.link()
        with SessionLocal() as db:
            db.get(StravaConexao, 1).expires_at = 0
            db.commit()
        data = self.tokens(); data['refresh_token'] = 'rotated'
        with patch('app.strava.api', side_effect=[data, strava.StravaError(429)]):
            self.assertEqual(self.post('sync').status_code, 429)
        with SessionLocal() as db:
            self.assertEqual(strava.decrypt(db.get(StravaConexao, 1).refresh_token), 'rotated')

    def test_disconnect(self):
        self.link()
        with patch('app.strava.api', return_value={'access_token': 'access-plain'}):
            self.assertEqual(self.post('disconnect').status_code, 200)
        with SessionLocal() as db:
            self.assertIsNone(db.get(StravaConexao, 1))

    def test_duplicate_athlete(self):
        self.link(); self.login(2)
        state = self.begin()
        with patch('app.strava.api', return_value=self.tokens()):
            self.assertIn('linked', self.callback(state).headers['location'])

    def test_webhook_validation_and_forged_revocation(self):
        self.link()
        with patch.dict(os.environ, {'STRAVA_WEBHOOK_VERIFY_TOKEN': 'verify', 'STRAVA_WEBHOOK_SUBSCRIPTION_ID': '77'}):
            r = self.client.get('/api/strava/webhook', params={'hub.mode': 'subscribe', 'hub.verify_token': 'verify', 'hub.challenge': 'challenge'})
            self.assertEqual(r.json(), {'hub.challenge': 'challenge'})
            self.assertEqual(self.client.get('/api/strava/webhook').status_code, 403)
            event = {'subscription_id': 77, 'owner_id': 123, 'object_type': 'athlete', 'updates': {'authorized': 'false'}}
            with patch('app.strava.api', return_value={'id': 123}):
                self.assertEqual(self.client.post('/api/strava/webhook', json=event).status_code, 200)
            with SessionLocal() as db:
                self.assertIsNotNone(db.get(StravaConexao, 1))
            with patch('app.strava.api', side_effect=strava.StravaError(401)):
                self.assertEqual(self.client.post('/api/strava/webhook', json=event).status_code, 200)
            with SessionLocal() as db:
                self.assertIsNone(db.get(StravaConexao, 1))

    def test_activity_metrics_and_map(self):
        self.link()
        activity = {'id': 12345678901234, 'name': 'Corrida', 'sport_type': 'Run',
                    'distance': 5000, 'moving_time': 1500, 'elapsed_time': 1800,
                    'average_speed': 3.333, 'total_elevation_gain': 35,
                    'start_date_local': '2026-09-29T06:30:00Z',
                    'map': {'summary_polyline': '_p~iF~ps|U_ulLnnqC_mqNvxq`@'},
                    'athlete': {'id': 123}, 'description': 'Não retornar campos não solicitados'}
        with patch('app.strava.api', return_value=[activity]):
            r = self.post('sync')
        self.assertEqual(r.status_code, 200)
        data = r.json()['activities'][0]
        self.assertEqual(data['id'], '12345678901234')
        self.assertEqual(data['distance'], 5000)
        self.assertEqual(data['elapsed_time'], 1800)
        self.assertEqual(data['summary_polyline'], activity['map']['summary_polyline'])
        self.assertNotIn('athlete', data)
        missing = strava.activity_summary({'id': 1, 'map': None, 'distance': float('nan')})
        self.assertIsNone(missing['summary_polyline'])
        self.assertIsNone(missing['distance'])
        self.assertIsNone(missing['moving_time'])

    def test_profile_renders(self):
        r = self.client.get('/aluno/perfil')
        self.assertEqual(r.status_code, 200)
        self.assertIn('href="/aluno/strava"', r.text)
        r = self.client.get('/aluno/strava')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['cache-control'], 'no-store')
        self.assertEqual(r.text.count('id="stravaConnect"'), 1)
        self.assertIn('/static/js/strava-view.js?', r.text)
        self.login(3)
        self.assertEqual(self.client.get('/aluno/strava', follow_redirects=False).status_code, 403)


if __name__ == '__main__':
    unittest.main()
