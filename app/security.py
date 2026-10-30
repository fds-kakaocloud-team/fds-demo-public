"""Separate local security service for presenting blocked transaction events."""
import sqlite3
import pymysql
from fastapi import FastAPI, HTTPException
from app import store

app = FastAPI(title='FDS security monitor')


@app.get('/health')
def health():
    try:
        store.blocked_events(1)
    except (sqlite3.Error, pymysql.MySQLError):
        raise HTTPException(503, '보안 이벤트 저장소에 연결할 수 없습니다.')
    return {'status': 'ok'}


@app.get('/alerts')
def alerts():
    try:
        events = store.blocked_events()
    except (sqlite3.Error, pymysql.MySQLError):
        raise HTTPException(503, '보안 이벤트 저장소에 연결할 수 없습니다.')
    return [{'event_id': event.get('event_id', event['transaction_id']),
             'transaction_id': event['transaction_id'], 'created_at': event['created_at'],
             'reasons': event.get('reasons', [])} for event in events]
