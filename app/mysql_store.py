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
        cur.execute('SELECT id,created_at,request_json,decision,risk_score,threshold_value AS threshold,model_type FROM fds_transactions ORDER BY created_at DESC LIMIT %s', (limit,))
        rows=cur.fetchall()
        return [{**row,'request':json.loads(row['request_json'])} for row in rows]


def audit(limit=50):
    with closing(connect()) as conn, conn.cursor() as cur:
        cur.execute('SELECT payload_json FROM fds_audit_outbox ORDER BY created_at DESC LIMIT %s', (limit,))
        return [json.loads(row['payload_json']) for row in cur.fetchall()]
