"""Local transactional storage for demo transactions and audit events."""
from contextlib import closing
import json
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(os.environ.get('FDS_DB_PATH', Path(__file__).resolve().parent.parent / 'data' / 'fds.sqlite3'))


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def initialize():
    with closing(connect()) as conn, conn:
        conn.executescript('''CREATE TABLE IF NOT EXISTS transactions (
          id TEXT PRIMARY KEY, created_at TEXT NOT NULL, request_json TEXT NOT NULL,
          decision TEXT NOT NULL, risk_score REAL NOT NULL, threshold REAL NOT NULL, model_type TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, transaction_id TEXT NOT NULL, created_at TEXT NOT NULL,
          event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
          FOREIGN KEY(transaction_id) REFERENCES transactions(id));''')


def record(tx, event):
    with closing(connect()) as conn, conn:
        conn.execute('INSERT INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?)',
                     (tx['id'], tx['created_at'], json.dumps(tx['request'], ensure_ascii=False), tx['decision'],
                      tx['risk_score'], tx['threshold'], tx['model_type']))
        conn.execute('INSERT INTO audit_events (transaction_id, created_at, event_type, payload_json) VALUES (?, ?, ?, ?)',
                     (tx['id'], tx['created_at'], event['event_type'], json.dumps(event, ensure_ascii=False)))


def recent(limit=20):
    with closing(connect()) as conn, conn:
        rows = conn.execute('SELECT * FROM transactions ORDER BY rowid DESC LIMIT ?', (limit,)).fetchall()
        return [{**dict(row), 'request': json.loads(row['request_json'])} for row in rows]


def audit(limit=50):
    with closing(connect()) as conn, conn:
        rows = conn.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
        return [json.loads(row['payload_json']) for row in rows]


def blocked_events(limit=100):
    with closing(connect()) as conn, conn:
        rows = conn.execute("SELECT payload_json FROM audit_events WHERE event_type = ? ORDER BY id DESC LIMIT ?", ('transaction_blocked', limit)).fetchall()
        return [json.loads(row['payload_json']) for row in rows]


# Keep the SQLite implementation for local development and tests.
if os.getenv('FDS_STORAGE', 'sqlite') == 'mysql':
    from app import mysql_store as _backend
    initialize = _backend.initialize
    record = _backend.record
    recent = _backend.recent
    audit = _backend.audit
    blocked_events = _backend.blocked_events
elif os.getenv('FDS_STORAGE', 'sqlite') != 'sqlite':
    raise ValueError('FDS_STORAGE must be sqlite or mysql')
