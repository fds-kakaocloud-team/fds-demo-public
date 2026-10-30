#!/usr/bin/env python3
"""Evaluate the selected model on newly generated synthetic examples."""
import json
from pathlib import Path
import joblib
import numpy as np
from sklearn.metrics import balanced_accuracy_score, classification_report, confusion_matrix
from generate_data import generate

bundle = joblib.load('models/fds_model.pkl')
rows = np.array(list(generate(10000, 2026)), dtype=float)
y = rows[:, -1].astype(int)
scores = bundle['model'].predict_proba(rows[:, :-1])[:, 1]
predictions = (scores >= bundle['decision_threshold']).astype(int)
result = {'seed': 2026, 'rows': len(y), 'threshold': bundle['decision_threshold'],
          'confusion_matrix_labels': [0, 1],
          'confusion_matrix': confusion_matrix(y, predictions, labels=[0, 1]).tolist(),
          'balanced_accuracy': balanced_accuracy_score(y, predictions),
          'classification_report': classification_report(y, predictions, output_dict=True, zero_division=0)}
Path('models/fresh_evaluation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
