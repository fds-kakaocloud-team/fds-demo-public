"""Demo transaction scoring API using the synthetic-data model."""
from contextlib import asynccontextmanager
import json
import sqlite3
import pymysql
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path
from typing import Literal

import joblib
from app import store
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

MODEL_PATH = Path(__file__).resolve().parent.parent / 'models' / 'fds_model.pkl'
BASE_DIR = Path(__file__).resolve().parent.parent
CONTEXT_MODEL_PATH = BASE_DIR / 'models' / 'context_model.pkl'
PAYSIM_MODEL_PATH = BASE_DIR / 'models' / 'paysim_model.pkl'
PAYSIM_TYPES = ['CASH_IN', 'CASH_OUT', 'DEBIT', 'PAYMENT', 'TRANSFER']
PUBLIC_MODEL_PATH = BASE_DIR / 'models' / 'public_model.pkl'
PUBLIC_EXAMPLES_PATH = BASE_DIR / 'data' / 'public' / 'examples.json'
PUBLIC_FEATURES = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
FEATURES = ['amount', 'hour', 'is_overseas', 'transactions_last_10min', 'distance_from_last_km', 'is_new_device']


@asynccontextmanager
async def lifespan(app: FastAPI):
    bundle = joblib.load(MODEL_PATH)
    if bundle['features'] != FEATURES or not 0 <= bundle['decision_threshold'] <= 1:
        raise ValueError('Model feature order or threshold is invalid')
    context = joblib.load(CONTEXT_MODEL_PATH)
    if context['features'] != ['hour', 'distance_from_last_km'] or not 0 <= context['decision_threshold'] <= 1:
        raise ValueError('Context model schema or threshold is invalid')
    app.state.context_bundle = context
    store.initialize()
    app.state.bundle = bundle
    app.state.paysim_bundle = None
    if PAYSIM_MODEL_PATH.exists():
        paysim_bundle = joblib.load(PAYSIM_MODEL_PATH)
        if paysim_bundle['types'] != PAYSIM_TYPES or not 0 <= paysim_bundle['decision_threshold'] <= 1:
            raise ValueError('PaySim model schema or threshold is invalid')
        app.state.paysim_bundle = paysim_bundle
    app.state.public_bundle = None
    app.state.examples = {}
    if PUBLIC_MODEL_PATH.exists() and PUBLIC_EXAMPLES_PATH.exists():
        public_bundle = joblib.load(PUBLIC_MODEL_PATH)
        examples_data = json.loads(PUBLIC_EXAMPLES_PATH.read_text(encoding='utf-8'))
        if public_bundle['features'] != PUBLIC_FEATURES or examples_data['features'] != PUBLIC_FEATURES:
            raise ValueError('Public model feature order is invalid')
        app.state.public_bundle = public_bundle
        app.state.examples = {example['id']: example for example in examples_data['examples']}
    yield


app = FastAPI(title='FDS Demo API', version='0.2.0', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=BASE_DIR / 'app' / 'static'), name='static')


class Transaction(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)
    amount: float = Field(gt=0, le=10_000_000, description='거래 금액 (원)')
    hour: int = Field(ge=0, le=23, description='거래 시간 (0~23)')
    is_overseas: Literal[0, 1] = Field(description='해외 거래 여부')
    transactions_last_10min: int = Field(ge=0, le=20, description='최근 10분 거래 횟수')
    distance_from_last_km: float = Field(ge=0, le=12000, description='직전 거래와의 거리 (km)')
    is_new_device: Literal[0, 1] = Field(description='신규 기기 여부')


class Prediction(BaseModel):
    status: Literal['Normal', 'Abuse']
    decision: Literal['approve', 'block']
    risk_score: float
    threshold: float
    model_type: str = 'synthetic_demo'


@app.get('/health')
def health():
    if not getattr(app.state, 'paysim_bundle', None) or not getattr(app.state, 'context_bundle', None):
        raise HTTPException(503, '필수 모델이 준비되지 않았습니다.')
    try:
        store.initialize()
    except (sqlite3.Error, pymysql.MySQLError):
        raise HTTPException(503, '저장소에 연결할 수 없습니다.')
    return {'status': 'ok', 'model_loaded': True}


@app.post('/predict', response_model=Prediction)
def predict(transaction: Transaction):
    bundle = app.state.bundle
    model = bundle['model']
    values = transaction.model_dump()
    features = [[values[name] for name in FEATURES]]
    fraud_index = list(model.classes_).index(1)
    score = float(model.predict_proba(features)[0, fraud_index])
    blocked = score >= bundle['decision_threshold']
    return Prediction(status='Abuse' if blocked else 'Normal', decision='block' if blocked else 'approve',
                      risk_score=score, threshold=bundle['decision_threshold'])


@app.get('/', include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / 'app' / 'static' / 'index.html')


@app.get('/public/examples')
def public_examples():
    if app.state.public_bundle is None:
        raise HTTPException(503, '공개 데이터 모델 또는 예시가 없습니다. README의 준비 단계를 실행하세요.')
    return [{'id': item['id'], 'label': '사기' if item['label'] else '정상',
             'amount': item['values'][-1]} for item in app.state.examples.values()]


@app.post('/public/examples/{example_id}/predict')
def predict_public_example(example_id: str):
    bundle = app.state.public_bundle
    if bundle is None:
        raise HTTPException(503, '공개 데이터 모델 또는 예시가 없습니다. README의 준비 단계를 실행하세요.')
    example = app.state.examples.get(example_id)
    if example is None:
        raise HTTPException(404, '거래 예시를 찾을 수 없습니다.')
    model = bundle['model']
    score = float(model.predict_proba([example['values']])[0, list(model.classes_).index(1)])
    threshold = bundle['decision_threshold']
    blocked = score >= threshold
    return {'status': 'Abuse' if blocked else 'Normal', 'decision': 'block' if blocked else 'approve',
            'risk_score': score, 'threshold': threshold, 'model_type': 'public_credit_card',
            'actual_label': 'Abuse' if example['label'] else 'Normal', 'example_id': example_id}


class PaySimTransaction(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, strict=True)
    amount: float = Field(gt=0, le=1000000000, description='거래 금액 (데이터의 통화 단위)')
    oldbalance: float = Field(ge=0, le=1000000000, description='거래 전 출금 계좌 잔액')
    transaction_type: Literal['CASH_IN', 'CASH_OUT', 'DEBIT', 'PAYMENT', 'TRANSFER']


@app.post('/paysim/predict')
def predict_paysim(transaction: PaySimTransaction):
    bundle = app.state.paysim_bundle
    if bundle is None:
        raise HTTPException(503, 'PaySim 모델이 없습니다. README의 학습 단계를 실행하세요.')
    model = bundle['model']
    inputs = [[transaction.amount, transaction.oldbalance] + [int(transaction.transaction_type == kind) for kind in PAYSIM_TYPES]]
    score = float(model.predict_proba(inputs)[0, list(model.classes_).index(1)])
    threshold = bundle['decision_threshold']
    blocked = score >= threshold
    return {'status': 'Abuse' if blocked else 'Normal', 'decision': 'block' if blocked else 'approve',
            'risk_score': score, 'threshold': threshold, 'model_type': 'paysim_public_synthetic'}


class MockPayment(PaySimTransaction):
    hour: int = Field(ge=0, le=23)
    distance_from_last_km: float = Field(ge=0, le=12000)


@app.post('/transactions', status_code=201)
def create_transaction(transaction: MockPayment):
    prediction = predict_paysim(PaySimTransaction(amount=transaction.amount, oldbalance=transaction.oldbalance,
                                                   transaction_type=transaction.transaction_type))
    context = app.state.context_bundle
    context_model = context['model']
    context_score = float(context_model.predict_proba([[transaction.hour, transaction.distance_from_last_km]])[0, list(context_model.classes_).index(1)])
    context_blocked = context_score >= context['decision_threshold']
    reasons = (['paysim'] if prediction['decision'] == 'block' else []) + (['time_location'] if context_blocked else [])
    prediction.update({'decision': 'block' if reasons else 'approve', 'status': 'Abuse' if reasons else 'Normal',
                       'context_score': context_score, 'context_threshold': context['decision_threshold'], 'reasons': reasons})
    tx = {'id': str(uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(),
          'request': transaction.model_dump(), **prediction}
    event = {'event_id': str(uuid4()), 'transaction_id': tx['id'], 'created_at': tx['created_at'],
             'event_type': 'transaction_blocked' if tx['decision'] == 'block' else 'transaction_approved',
             'decision': tx['decision'], 'risk_score': tx['risk_score'], 'threshold': tx['threshold'],
             'model_type': tx['model_type'], 'context_score': context_score,
             'context_threshold': context['decision_threshold'], 'reasons': reasons}
    try:
        store.record(tx, event)
    except (sqlite3.Error, pymysql.MySQLError):
        raise HTTPException(503, '거래 기록을 저장하지 못해 모의 결제를 처리하지 않았습니다.')
    return {**tx, 'alert': '차단 알림이 감사 이벤트에 기록되었습니다.' if tx['decision'] == 'block' else None,
            'context_used_in_model': True}


@app.get('/transactions')
def transactions():
    return store.recent()


@app.get('/audit-events')
def audit_events():
    return store.audit()
