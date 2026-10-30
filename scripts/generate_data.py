#!/usr/bin/env python3
"""Generate reproducible synthetic transactions for an educational FDS demo."""
import argparse
import csv
import math
import random
from pathlib import Path

FIELDS = ["amount", "hour", "is_overseas", "transactions_last_10min", "distance_from_last_km", "is_new_device", "is_fraud"]


def generate(count: int, seed: int):
    rng = random.Random(seed)
    for _ in range(count):
        amount = round(min(rng.lognormvariate(10.5, 1.1), 10_000_000), 2)
        hour = rng.randrange(24)
        overseas = int(rng.random() < 0.12)
        recent = min(int(rng.expovariate(1 / 1.5)), 20)
        distance = round(min(rng.expovariate(1 / (800 if overseas else 30)), 12000), 2)
        new_device = int(rng.random() < 0.15)
        # Probabilistic labels produce overlap between normal and fraud examples.
        score = (-4.8 + 0.9 * (amount > 500_000) + 0.8 * (hour < 6)
                 + 0.9 * overseas + 0.24 * recent + 0.8 * (distance > 300)
                 + 1.0 * new_device + 0.8 * (overseas and new_device))
        probability = 1 / (1 + math.exp(-score))
        yield [amount, hour, overseas, recent, distance, new_device, int(rng.random() < probability)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count', type=int, default=10000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--output', type=Path, default=Path('data/transactions.csv'))
    args = parser.parse_args()
    if args.count <= 0:
        parser.error('--count must be positive')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fraud = 0
    with args.output.open('w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(FIELDS)
        for row in generate(args.count, args.seed):
            writer.writerow(row)
            fraud += row[-1]
    print(f'{args.output}: {args.count}건 생성, 사기 {fraud}건 ({fraud / args.count:.1%})')


if __name__ == '__main__':
    main()
