import unittest
from unittest.mock import MagicMock, patch
from app import mysql_store


class MySQLStoreTest(unittest.TestCase):
    def test_insert_commits_as_one_transaction(self):
        conn = MagicMock(); cur = conn.cursor.return_value.__enter__.return_value
        tx = {'id':'tx', 'created_at':'2026-01-01T00:00:00+00:00', 'request':{}, 'decision':'block', 'risk_score':.7, 'threshold':.5, 'model_type':'demo'}
        event = {'event_id':'event', 'event_type':'transaction_blocked'}
        with patch('app.mysql_store.connect', return_value=conn): mysql_store.record(tx,event)
        self.assertEqual(cur.execute.call_count, 2)
        conn.commit.assert_called_once()
        conn.rollback.assert_not_called()

    def test_audit_insert_failure_rolls_back_transaction(self):
        conn = MagicMock(); cur = conn.cursor.return_value.__enter__.return_value
        cur.execute.side_effect = [None, RuntimeError('audit insert failed')]
        tx = {'id':'tx', 'created_at':'2026-01-01T00:00:00+00:00', 'request':{}, 'decision':'block', 'risk_score':.7, 'threshold':.5, 'model_type':'demo'}
        event = {'event_id':'event', 'event_type':'transaction_blocked'}
        with patch('app.mysql_store.connect', return_value=conn), self.assertRaises(RuntimeError): mysql_store.record(tx,event)
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()
