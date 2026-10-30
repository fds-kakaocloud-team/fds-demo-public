import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import store
from app.main import app

class StatisticsTest(unittest.TestCase):
    def test_full_counts_and_seoul_day_boundary(self):
        with tempfile.TemporaryDirectory() as temp, patch('app.store.DB_PATH', Path(temp) / 'data.sqlite3'):
            with TestClient(app) as client:
                seoul=timezone(timedelta(hours=9))
                today=datetime.now(seoul).date()
                boundary=datetime.combine(today, datetime.min.time(), seoul).astimezone(timezone.utc)
                for i in range(25):
                    when=boundary + timedelta(hours=1) if i < 24 else boundary-timedelta(seconds=1)
                    decision='block' if i==24 else 'approve'
                    tx={'id':str(i),'created_at':when.isoformat(),'request':{},'decision':decision,'risk_score':0.,'threshold':0.5,'model_type':'demo'}
                    event={'event_type':'transaction_blocked' if decision=='block' else 'transaction_approved'}
                    store.record(tx,event)
                data=client.get('/statistics').json()
                self.assertEqual(len(data['days']),7)
                self.assertEqual(data['days'][-1]['approve'],24)
                self.assertEqual(data['days'][-2]['block'],1)
                self.assertEqual(data['total_approved'],24)
                self.assertEqual(data['total_blocked'],1)
                self.assertEqual(data['timezone'],'Asia/Seoul')
