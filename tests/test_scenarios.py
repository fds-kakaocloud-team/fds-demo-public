"""End-to-end demo scenarios with real models and isolated SQLite storage."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app, PAYSIM_MODEL_PATH


@unittest.skipUnless(PAYSIM_MODEL_PATH.exists(), 'Run scripts/train_paysim.py first')
class DemoScenarios(unittest.TestCase):
    def test_full_flow(self):
        with tempfile.TemporaryDirectory() as tmp, patch('app.store.DB_PATH', Path(tmp) / 'demo.sqlite3'):
            with TestClient(app) as client:
                base = {'amount': 10000, 'oldbalance': 100000, 'transaction_type': 'TRANSFER', 'hour': 12, 'distance_from_last_km': 5}
                for payload, decision, reason in [(base, 'approve', None),
                    ({**base, 'amount': 100000}, 'block', 'paysim'),
                    ({**base, 'hour': 2, 'distance_from_last_km': 1000}, 'block', 'time_location')]:
                    response = client.post('/transactions', json=payload)
                    self.assertEqual(response.status_code, 201)
                    result = response.json()
                    self.assertEqual(result['decision'], decision)
                    if reason: self.assertIn(reason, result['reasons'])
                    matches = [e for e in client.get('/audit-events').json() if e['transaction_id'] == result['id']]
                    self.assertEqual(len(matches), 1)
                    self.assertEqual(matches[0]['decision'], decision)
                self.assertEqual(len(client.get('/transactions').json()), 3)
                self.assertEqual(client.post('/transactions', json={**base, 'hour': 24}).status_code, 422)
                with sqlite3.connect(Path(tmp) / 'demo.sqlite3') as conn:
                    conn.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_events BEGIN SELECT RAISE(ABORT, 'audit unavailable'); END")
                self.assertEqual(client.post('/transactions', json=base).status_code, 503)
                self.assertEqual(len(client.get('/transactions').json()), 3)
                self.assertEqual(len(client.get('/audit-events').json()), 3)

if __name__ == '__main__':
    unittest.main()
