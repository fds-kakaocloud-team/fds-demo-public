#!/usr/bin/env python3
"""Train a separate model on the public ULB credit card dataset."""
import csv
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, classification_report, confusion_matrix, precision_recall_curve
from sklearn.model_selection import train_test_split

path = Path('data/public/creditcard.csv')
features = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
with path.open(newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = np.array([[float(row[k]) for k in features] + [int(row['Class'])] for row in reader])
X, y = rows[:, :-1], rows[:, -1].astype(int)
X_dev, X_test, y_dev, y_test = train_test_split(X, y, test_size=.2, stratify=y, random_state=42)
X_train, X_val, y_train, y_val = train_test_split(X_dev, y_dev, test_size=.25, stratify=y_dev, random_state=42)
model = RandomForestClassifier(n_estimators=60, min_samples_leaf=2, n_jobs=-1, random_state=42)
model.fit(X_train, y_train)
scores = model.predict_proba(X_val)[:, 1]
precision, recall, thresholds = precision_recall_curve(y_val, scores)
f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
i = int(np.argmax(f1))
threshold = float(thresholds[i])
validation_f1 = float(f1[i])
model.fit(X_dev, y_dev)
scores = model.predict_proba(X_test)[:, 1]
pred = (scores >= threshold).astype(int)
report = {'dataset': 'ULB credit card fraud, Hugging Face mirror', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
          'split': 'stratified random 60/20/20, seed 42', 'rows': len(y), 'fraud_count': int(y.sum()),
          'train_rows_for_selection': len(y_train), 'validation_rows': len(y_val), 'final_train_rows': len(y_dev), 'test_rows': len(y_test),
          'features': features, 'parameters': model.get_params(), 'threshold': threshold, 'selection_metric': 'validation F1', 'validation_f1': validation_f1,
          'average_precision': average_precision_score(y_test, scores), 'confusion_matrix_labels': [0, 1],
          'confusion_matrix': confusion_matrix(y_test, pred, labels=[0, 1]).tolist(),
          'classification_report': classification_report(y_test, pred, output_dict=True, zero_division=0), 'sklearn_version': sklearn.__version__}
Path('models').mkdir(exist_ok=True)
joblib.dump({'model': model, 'features': features, 'decision_threshold': threshold, 'sklearn_version': sklearn.__version__}, 'models/public_model.pkl')
Path('models/public_evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
