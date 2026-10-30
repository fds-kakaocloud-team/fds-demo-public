import json
import unittest
from unittest.mock import MagicMock, patch
from app.audit_worker import deliver_one, object_key

class AuditWorkerTest(unittest.TestCase):
    def test_upload_and_mark_delivered(self):
        event = {'event_id':'abcdef', 'created_at':'2026-10-30T00:00:00+00:00'}
        conn = MagicMock(); cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'event_id':'abcdef', 'payload_json': json.dumps(event)}
        client = MagicMock()
        with patch.dict('os.environ', {'FDS_AUDIT_BUCKET':'test-bucket'}), patch('app.audit_worker.mysql_store.connect', return_value=conn):
            self.assertTrue(deliver_one(client))
        self.assertEqual(object_key(event), 'fds/audit/2026/10/30/abcdef.json')
        self.assertEqual(client.put_object.call_args.kwargs['Key'], 'fds/audit/2026/10/30/abcdef.json')
        self.assertIn('delivered_at=UTC_TIMESTAMP', cursor.execute.call_args.args[0])
        conn.commit.assert_called_once()

    def test_failed_upload_stays_pending(self):
        event = {'event_id':'abcdef', 'created_at':'2026-10-30T00:00:00+00:00'}
        conn = MagicMock(); cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = {'event_id':'abcdef', 'payload_json':json.dumps(event)}
        client = MagicMock(); client.put_object.side_effect = RuntimeError('failure')
        with patch.dict('os.environ', {'FDS_AUDIT_BUCKET':'test-bucket'}), patch('app.audit_worker.mysql_store.connect', return_value=conn), self.assertLogs('fds.audit', level='ERROR'):
            self.assertTrue(deliver_one(client))
        self.assertNotIn('delivered_at=UTC_TIMESTAMP', cursor.execute.call_args.args[0])
        self.assertIn('attempts=attempts+1', cursor.execute.call_args.args[0])
        conn.commit.assert_called_once()
