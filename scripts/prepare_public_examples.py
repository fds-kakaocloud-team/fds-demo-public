"""Extract reproducible held-out examples from the public dataset for the demo."""
import csv
import json
from pathlib import Path
import numpy as np
from sklearn.model_selection import train_test_split

source = Path('data/public/creditcard.csv')
features = ['Time'] + [f'V{i}' for i in range(1, 29)] + ['Amount']
with source.open(encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))
y = np.array([int(row['Class']) for row in rows])
_, test_indices = train_test_split(np.arange(len(rows)), test_size=.2, stratify=y, random_state=42)
examples = []
for label in (0, 1):
    indices = [int(i) for i in test_indices if y[i] == label][:10]
    for number, index in enumerate(indices, 1):
        row = rows[index]
        examples.append({'id': f'{"normal" if label == 0 else "fraud"}-{number}',
                         'values': [float(row[name]) for name in features], 'label': label})
output = Path('data/public/examples.json')
output.write_text(json.dumps({'features': features, 'examples': examples}, ensure_ascii=False), encoding='utf-8')
print(f'{output}: {len(examples)} held-out examples')
