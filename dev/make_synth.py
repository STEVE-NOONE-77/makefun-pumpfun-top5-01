"""A synthetic final-scale history (66 marks x 200 rows) for speed, memory and validity checks: coins launched at
~150 an hour over 11 hours, each with a random log-cap path (most stall on the curve, a few graduate, some collapse,
two outliers priced at 10^6.3). Seeded.
Usage: python3 dev/make_synth.py <kit input dir> <out dir> [seed]
"""
import json
import math
import os
import random
import sys
from datetime import datetime, timezone


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def main():
    kit, out = sys.argv[1], sys.argv[2]
    rng = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 7)
    task = json.load(open(os.path.join(kit, 'task.json')))
    t0 = datetime.fromisoformat('2026-11-12T02:00:00+00:00').timestamp()
    cut = t0 + 11 * 3600
    task.update(t0=iso(t0), history_until=iso(cut), marks=66,
                reads=[iso(t0 + h * 3600) for h in range(18, 25)])
    task['window'] = {'deadline': iso(cut + 3600), 'answer_at': iso(t0 + 24 * 3600)}
    os.makedirs(out, exist_ok=True)
    json.dump(task, open(os.path.join(out, 'task.json'), 'w'), indent=1)
    alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    coins = []
    for i in range(int(150 * 11)):
        born = t0 + rng.random() * 11 * 3600
        mint = ''.join(rng.choice(alphabet) for _ in range(40)) + 'pump'
        peak = 1.45 + rng.expovariate(1 / 0.35)
        if i < 2:
            peak = 6.3
        coins.append({'mint': mint, 'born': born, 'peak': peak, 'grow': rng.uniform(0.1, 2.0),
                      'die': rng.expovariate(1 / 3.0), 'mayhem': rng.random() < 0.05})
    with open(os.path.join(out, 'history.ndjson'), 'w') as f:
        for j in range(66):
            t = t0 + 600 * j
            rows = []
            for c in coins:
                if c['born'] > t:
                    continue
                age = (t - c['born']) / 3600
                x = 1.3 + (c['peak'] - 1.3) * min(1.0, age / c['grow'])
                if c['peak'] > 2.6 and age > c['grow'] + c['die'] and c['peak'] < 6:
                    x = 1.26
                x += rng.gauss(0, 0.02)
                venue = 'pool' if x > 2.6 or c['peak'] > 2.6 and age > c['grow'] else 'curve'
                rows.append((x, c, venue))
            rows.sort(key=lambda r: (-r[0], r[1]['mint']))
            out_rows = []
            for k, (x, c, venue) in enumerate(rows[:200]):
                cap = int(10 ** (x + 9))
                out_rows.append({'rank': k + 1, 'mint': c['mint'], 'market_cap_lamports': str(cap), 'venue': venue,
                                 'slot': 468000000 + j, 'name': 'n', 'symbol': 's', 'created_at': iso(int(c['born'])),
                                 'complete': venue != 'curve', 'mayhem': c['mayhem'] and venue == 'pool',
                                 'quote_reserves_lamports': str(int(math.sqrt(cap / 1e9 * 17.5) * 1e9))})
            f.write(json.dumps({'schema': 'makefun/pumpfun-top5-forecast/mark/v1', 'at': iso(t + 4), 'ok': True, 'error': None,
                                'kind': 'mark', 't0': iso(t0), 'counts': {'eligible': len(rows), 'graduated': 0, 'excluded_non_sol': 0,
                                'priced': len(rows), 'refused': 0, 'calls': 40, 'http_429': 0, 'stream_coverage': 0.9},
                                'rows': out_rows}) + '\n')


if __name__ == '__main__':
    main()
