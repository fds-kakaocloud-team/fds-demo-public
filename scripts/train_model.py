#!/usr/bin/env python3
"""Tune a demonstration fraud classifier using a separate validation split."""
import argparse
import csv
import json
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, classification_report, confusion_matrix, balanced_accuracy_score
from sklearn.model_selection import train_test_split

FEATURES = ["amount", "hour", "is_overseas", "transactions_last_10min", "distance_from_last_km", "is_new_device"]


def evaluate(y, scores, threshold):
    predictions = (scores >= threshold).astype(int)
    return {'confusion_matrix': confusion_matrix(y, predictions, labels=[0, 1]).tolist(),
            'average_precision': average_precision_score(y, scores),
            'classification_report': classification_report(y, predictions, output_dict=True, zero_division=0)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path('data/transactions.csv'))
    parser.add_argument('--model', type=Path, default=Path('models/fds_model.pkl'))
    parser.add_argument('--report', type=Path, default=Path('models/evaluation.json'))
    args = parser.parse_args()
    with args.data.open(encoding='utf-8', newline='') as file:
        rows = list(csv.DictReader(file))
    X = np.array([[float(row[name]) for name in FEATURES] for row in rows])
    y = np.array([int(row['is_fraud']) for row in rows])
    # Keep the same 20% test set as the original baseline.
    X_dev, X_test, y_dev, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    X_train, X_val, y_train, y_val = train_test_split(X_dev, y_dev, test_size=0.25, random_state=42, stratify=y_dev)
    candidates = []
    for leaf in (5, 20, 50, 100, 200):
        for weight in (None, 'balanced'):
            model = RandomForestClassifier(n_estimators=200, min_samples_leaf=leaf, class_weight=weight, random_state=42, n_jobs=-1)
            model.fit(X_train, y_train)
            scores = model.predict_proba(X_val)[:, list(model.classes_).index(1)]
            for threshold in np.linspace(0.05, 0.8, 76):
                score = balanced_accuracy_score(y_val, scores >= threshold)
                candidates.append((score, float(threshold), leaf, weight))
    # Choose balanced accuracy on validation only; favor the higher threshold on ties.
    best = max(candidates, key=lambda item: (item[0], item[1]))
    val_balanced_accuracy, threshold, leaf, weight = best
    model = RandomForestClassifier(n_estimators=200, min_samples_leaf=leaf, class_weight=weight, random_state=42, n_jobs=-1)
    model.fit(X_dev, y_dev)
    test_scores = model.predict_proba(X_test)[:, list(model.classes_).index(1)]
    result = evaluate(y_test, test_scores, threshold)
    report = {'dataset': str(args.data), 'train_rows_for_selection': len(y_train), 'validation_rows': len(y_val),
              'final_train_rows': len(y_dev), 'test_rows': len(y_test), 'features': FEATURES,
              'decision_threshold': threshold, 'selection_metric': 'validation balanced accuracy', 'validation_balanced_accuracy': val_balanced_accuracy,
              'parameters': {'n_estimators': 200, 'min_samples_leaf': leaf, 'class_weight': weight},
              'sklearn_version': sklearn.__version__, 'confusion_matrix_labels': [0, 1], **result}
    args.model.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({'model': model, 'features': FEATURES, 'decision_threshold': threshold, 'sklearn_version': sklearn.__version__}, args.model)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
