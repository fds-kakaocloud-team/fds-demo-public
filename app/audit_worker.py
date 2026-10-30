"""Deliver MySQL outbox events to S3-compatible storage with retry."""
import json
import logging
import os
import time
from contextlib import closing
from datetime import datetime
import boto3
from botocore.config import Config
from app import mysql_store

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('fds.audit')


def object_key(event):
    stamp = datetime.fromisoformat(event['created_at'])
    return f"{os.getenv('FDS_AUDIT_PREFIX', 'fds/audit').strip('/')}/{stamp:%Y/%m/%d}/{event['event_id']}.json"


def deliver_one(client):
    # A row lock prevents two WAS workers delivering the same event concurrently.
    with closing(mysql_store.connect()) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT event_id, payload_json FROM fds_audit_outbox WHERE delivered_at IS NULL AND (last_attempt_at IS NULL OR last_attempt_at < UTC_TIMESTAMP(6) - INTERVAL 30 SECOND) ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED")
                row = cur.fetchone()
                if not row:
                    conn.commit()
                    return False
                event = json.loads(row['payload_json'])
                try:
                    client.put_object(Bucket=os.environ['FDS_AUDIT_BUCKET'], Key=object_key(event),
                                      Body=json.dumps(event, ensure_ascii=False).encode('utf-8'), ContentType='application/json')
                except Exception:
                    cur.execute('UPDATE fds_audit_outbox SET attempts=attempts+1, last_attempt_at=UTC_TIMESTAMP(6) WHERE event_id=%s', (row['event_id'],))
                    conn.commit()
                    log.exception('Audit upload failed; will retry event %s', row['event_id'])
                    return True
                cur.execute('UPDATE fds_audit_outbox SET delivered_at=UTC_TIMESTAMP(6), attempts=attempts+1, last_attempt_at=UTC_TIMESTAMP(6) WHERE event_id=%s', (row['event_id'],))
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            raise


def main():
    client = boto3.client('s3', endpoint_url=os.getenv('FDS_S3_ENDPOINT','https://objectstorage.kr-central-2.kakaocloud.com'),
                          region_name=os.getenv('AWS_DEFAULT_REGION','kr-central-2'),
                          config=Config(connect_timeout=5, read_timeout=10, retries={'max_attempts': 2}))
    while True:
        try:
            if not deliver_one(client): time.sleep(5)
        except Exception:
            log.exception('Audit worker database error')
            time.sleep(5)

if __name__ == '__main__': main()
