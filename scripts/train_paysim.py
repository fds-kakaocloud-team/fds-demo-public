#!/usr/bin/env python3
"""Train on PaySim using only transaction information available before processing."""
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pyarrow.parquet as pq
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, classification_report, confusion_matrix, precision_recall_curve

path = Path('data/public/paysim.parquet')
types = ['CASH_IN', 'CASH_OUT', 'DEBIT', 'PAYMENT', 'TRANSFER']
columns = ['step', 'type', 'amount', 'oldbalanceOrg', 'isFraud']
df = pq.read_table(path, columns=columns).to_pandas()
train = df[df.step <= 500]
fraud = train[train.isFraud == 1]
normal = train[train.isFraud == 0].sample(n=300000, random_state=42)
train = __import__('pandas').concat([fraud, normal])
val = df[(df.step > 500) & (df.step <= 600)]
test = df[df.step > 600]
def features(data):
    return np.column_stack([data.amount.to_numpy(), data.oldbalanceOrg.to_numpy()] + [(data.type == kind).to_numpy().astype(int) for kind in types])
model = RandomForestClassifier(n_estimators=100, min_samples_leaf=3, n_jobs=-1, random_state=42)
model.fit(features(train), train.isFraud)
scores = model.predict_proba(features(val))[:, list(model.classes_).index(1)]
p, r, thresholds = precision_recall_curve(val.isFraud, scores)
f1 = 2*p[:-1]*r[:-1] / np.maximum(p[:-1]+r[:-1], 1e-12)
i = int(np.argmax(f1)); threshold = float(thresholds[i])
scores = model.predict_proba(features(test))[:, list(model.classes_).index(1)]
pred = (scores >= threshold).astype(int)
report = {'dataset': 'PaySim', 'source_sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(path.read_bytes()).hexdigest(),
          'split': 'steps 1-500 train, 501-600 validation, 601+ test', 'training_sampling': 'all fraud and 300000 randomly sampled normal transactions',
          'train_rows': len(train), 'validation_rows': len(val), 'test_rows': len(test), 'threshold': threshold,
          'validation_f1': float(f1[i]), 'test_average_precision': average_precision_score(test.isFraud, scores),
          'confusion_matrix_labels': [0,1], 'confusion_matrix': confusion_matrix(test.isFraud, pred, labels=[0,1]).tolist(),
          'classification_report': classification_report(test.isFraud, pred, output_dict=True, zero_division=0), 'sklearn_version': sklearn.__version__}
joblib.dump({'model': model, 'types': types, 'decision_threshold': threshold, 'sklearn_version': sklearn.__version__}, 'models/paysim_model.pkl')
Path('models/paysim_evaluation.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
