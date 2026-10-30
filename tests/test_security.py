import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import store
from app.security import app as security_app
from app.main import app as main_app

class SecurityTest(unittest.TestCase):
    def test_monitor_reads_only_blocked_events(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.store.DB_PATH', Path(directory) / 'test.sqlite3'):
            store.initialize()
            for i, decision in enumerate(['approve', 'block']):
                tx = {'id':str(i), 'created_at':'2026-01-01T00:00:00+00:00', 'request':{}, 'decision':decision, 'risk_score':0.6, 'threshold':0.5, 'model_type':'demo'}
                event = {'event_id':str(i), 'transaction_id':str(i), 'created_at':tx['created_at'], 'event_type':'transaction_blocked' if decision=='block' else 'transaction_approved', 'reasons':['paysim']}
                store.record(tx,event)
            with TestClient(security_app) as client:
                self.assertEqual(client.get('/health').status_code, 200)
                events=client.get('/alerts').json()
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['transaction_id'], '1')
                self.assertEqual(events[0]['reasons'], ['paysim'])
            with patch('app.security.store.blocked_events', side_effect=sqlite3.OperationalError('offline')):
                with TestClient(security_app) as client:
                    self.assertEqual(client.get('/alerts').status_code, 503)

    def test_proxy_failure_is_reported(self):
        with TestClient(main_app) as client, patch('app.main.urllib.request.urlopen', side_effect=OSError('offline')):
            self.assertEqual(client.get('/security/alerts').status_code, 503)
