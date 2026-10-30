"""MySQL transaction/outbox backend; schema is provisioned separately."""
import json
import os
from contextlib import closing
import pymysql


def connect():
    kwargs = dict(host=os.environ['FDS_DB_HOST'], port=int(os.getenv('FDS_DB_PORT', '3306')),
                  user=os.environ['FDS_DB_USER'], password=os.environ['FDS_DB_PASSWORD'],
                  database=os.environ['FDS_DB_NAME'], charset='utf8mb4', connect_timeout=5,
                  read_timeout=10, write_timeout=10, cursorclass=pymysql.cursors.DictCursor)
    ca = os.getenv('FDS_DB_SSL_CA')
    if ca:
        kwargs.update(ssl={'ca': ca}, ssl_verify_cert=True, ssl_verify_identity=True)
    return pymysql.connect(**kwargs)


def initialize():
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute('SELECT 1 FROM fds_transactions LIMIT 1')
        cur.execute('SELECT 1 FROM fds_audit_outbox LIMIT 1')


def record(tx, event):
    with closing(connect()) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute('INSERT INTO fds_transactions (id,created_at,request_json,decision,risk_score,threshold_value,model_type) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                            (tx['id'],tx['created_at'],json.dumps(tx['request'],ensure_ascii=False),tx['decision'],tx['risk_score'],tx['threshold'],tx['model_type']))
                cur.execute('INSERT INTO fds_audit_outbox (event_id,transaction_id,created_at,event_type,payload_json) VALUES (%s,%s,%s,%s,%s)',
                            (event['event_id'],tx['id'],tx['created_at'],event['event_type'],json.dumps(event,ensure_ascii=False)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def recent(limit=20):
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute('SELECT t.id,t.created_at,t.request_json,t.decision,t.risk_score,t.threshold_value AS threshold,t.model_type,e.payload_json FROM fds_transactions t LEFT JOIN fds_audit_outbox e ON e.transaction_id=t.id ORDER BY t.created_at DESC LIMIT %s', (limit,))
        rows=cur.fetchall()
        return [{**row,'request':json.loads(row['request_json']), 'reasons':json.loads(row['payload_json']).get('reasons', []) if row['payload_json'] else []} for row in rows]


def audit(limit=50):
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute('SELECT payload_json FROM fds_audit_outbox ORDER BY created_at DESC LIMIT %s', (limit,))
        return [json.loads(row['payload_json']) for row in cur.fetchall()]


def blocked_events(limit=100):
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute("SELECT e.payload_json,t.request_json FROM fds_audit_outbox e LEFT JOIN fds_transactions t ON t.id=e.transaction_id WHERE e.event_type=%s ORDER BY e.created_at DESC, e.event_id DESC LIMIT %s", ('transaction_blocked', limit))
        return [{**json.loads(row['payload_json']), 'amount':json.loads(row['request_json']).get('amount') if row['request_json'] else None} for row in cur.fetchall()]


def hourly_counts(start, end):
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute("SELECT SUBSTR(created_at,1,13) AS hour, decision, COUNT(*) AS count FROM fds_transactions WHERE created_at >= %s AND created_at < %s GROUP BY SUBSTR(created_at,1,13), decision", (start, end))
        return cur.fetchall()
