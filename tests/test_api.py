import unittest
import tempfile
from pathlib import Path
import sqlite3
import numpy as np
from unittest.mock import patch

from fastapi.testclient import TestClient
from app.main import app, PUBLIC_MODEL_PATH, PUBLIC_EXAMPLES_PATH, PAYSIM_MODEL_PATH


class ApiTest(unittest.TestCase):
    def test_real_model_and_validation(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/health').json(), {'status': 'ok', 'model_loaded': True})
            transaction = {'amount': 47565, 'hour': 8, 'is_overseas': 0,
                           'transactions_last_10min': 0, 'distance_from_last_km': 3.24, 'is_new_device': 0}
            response = client.post('/predict', json=transaction)
            self.assertEqual(response.status_code, 200)
            result = response.json()
            self.assertEqual(result['decision'], 'block' if result['risk_score'] >= result['threshold'] else 'approve')
            self.assertEqual(result['status'], 'Abuse' if result['decision'] == 'block' else 'Normal')
            self.assertEqual(client.post('/predict', json={**transaction, 'hour': 24}).status_code, 422)
            self.assertEqual(client.post('/predict', json={**transaction, 'amount': -1}).status_code, 422)
            self.assertEqual(client.post('/predict', json={**transaction, 'unexpected': 1}).status_code, 422)

    def test_both_policy_outcomes(self):
        with TestClient(app) as client:
            transaction = {'amount': 10000, 'hour': 12, 'is_overseas': 0,
                           'transactions_last_10min': 0, 'distance_from_last_km': 0, 'is_new_device': 0}
            with patch.object(app.state.bundle['model'], 'predict_proba', return_value=np.array([[0.9, 0.1]])):
                self.assertEqual(client.post('/predict', json=transaction).json()['decision'], 'approve')
            with patch.object(app.state.bundle['model'], 'predict_proba', return_value=np.array([[0.1, 0.9]])):
                self.assertEqual(client.post('/predict', json=transaction).json()['decision'], 'block')

    @unittest.skipUnless(PUBLIC_MODEL_PATH.exists() and PUBLIC_EXAMPLES_PATH.exists(), 'public artifacts not installed')
    def test_public_examples(self):
        with TestClient(app) as client:
            self.assertEqual(client.get('/').status_code, 200)
            examples = client.get('/public/examples').json()
            self.assertEqual(len(examples), 20)
            self.assertEqual({item['label'] for item in examples}, {'정상', '사기'})
            for item in (examples[0], examples[-1]):
                response = client.post(f"/public/examples/{item['id']}/predict")
                self.assertEqual(response.status_code, 200)
                result = response.json()
                self.assertEqual(result['actual_label'], 'Abuse' if item['label'] == '사기' else 'Normal')
                self.assertEqual(result['decision'], 'block' if result['risk_score'] >= result['threshold'] else 'approve')
            self.assertEqual(client.post('/public/examples/missing/predict').status_code, 404)

    @unittest.skipUnless(PAYSIM_MODEL_PATH.exists(), 'PaySim model not installed')
    def test_paysim_prediction_and_validation(self):
        with TestClient(app) as client:
            transaction = {'amount': 50000, 'oldbalance': 100000, 'transaction_type': 'TRANSFER'}
            response = client.post('/paysim/predict', json=transaction)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data['decision'], 'block' if data['risk_score'] >= data['threshold'] else 'approve')
            self.assertEqual(client.post('/paysim/predict', json={**transaction, 'transaction_type': 'UNKNOWN'}).status_code, 422)
            self.assertEqual(client.post('/paysim/predict', json={**transaction, 'oldbalance': -1}).status_code, 422)

    @unittest.skipUnless(PAYSIM_MODEL_PATH.exists(), 'PaySim model not installed')
    def test_payment_records_and_audit(self):
        with tempfile.TemporaryDirectory() as directory, patch('app.store.DB_PATH', Path(directory) / 'test.sqlite3'):
            with TestClient(app) as client:
                payload = {'amount': 50000, 'oldbalance': 100000, 'transaction_type': 'TRANSFER',
                           'hour': 12, 'distance_from_last_km': 5}
                model = app.state.paysim_bundle['model']
                for score in (0.0, 1.0):
                    with patch.object(model, 'predict_proba', return_value=np.array([[1-score, score]])), patch.object(app.state.context_bundle['model'], 'predict_proba', return_value=np.array([[1., 0.]])):
                        response = client.post('/transactions', json=payload)
                    self.assertEqual(response.status_code, 201)
                    self.assertEqual(response.json()['decision'], 'block' if score else 'approve')
                transactions = client.get('/transactions').json()
                events = client.get('/audit-events').json()
                self.assertEqual(len(transactions), 2)
                self.assertEqual([event['event_type'] for event in events], ['transaction_blocked', 'transaction_approved'])
                self.assertEqual(transactions[0]['request']['hour'], 12)
                self.assertEqual(events[0]['reasons'], ['paysim'])
                with patch.object(model, 'predict_proba', return_value=np.array([[1., 0.]])), patch.object(app.state.context_bundle['model'], 'predict_proba', return_value=np.array([[0., 1.]])):
                    response = client.post('/transactions', json=payload)
                self.assertEqual(response.json()['reasons'], ['time_location'])
                self.assertEqual(response.json()['decision'], 'block')
                with patch('app.store.record', side_effect=sqlite3.OperationalError('unavailable')):
                    self.assertEqual(client.post('/transactions', json=payload).status_code, 503)
                self.assertEqual(len(client.get('/transactions').json()), 3)

    def test_paysim_unavailable(self):
        with patch('app.main.PAYSIM_MODEL_PATH') as path:
            path.exists.return_value = False
            with TestClient(app) as client:
                self.assertEqual(client.get('/health').status_code, 503)
                response = client.post('/paysim/predict', json={'amount': 100, 'oldbalance': 200, 'transaction_type': 'TRANSFER'})
                self.assertEqual(response.status_code, 503)

    def test_public_unavailable(self):
        with patch('app.main.PUBLIC_MODEL_PATH') as path:
            path.exists.return_value = False
            with TestClient(app) as client:
                self.assertEqual(client.get('/public/examples').status_code, 503)
                self.assertEqual(client.post('/public/examples/normal-1/predict').status_code, 503)


if __name__ == '__main__':
    unittest.main()
