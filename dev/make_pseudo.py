"""Build pseudo-contests (input dir with history.ndjson + task.json, and an answer file for dev/score.py) from the
cached market data. Only coins with PumpSwap data are present (curve coins are left out: they are far below the
top 5 at the reads), so the field is thinner than the house's: see the survivorship note in the report.

Usage: python3 dev/make_pseudo.py <cache_dir> <out_dir> <name> <t0 ISO> <hist_hours> <read_start_h> <read_step_min> [nreads]
  final-like:    ... d11 2026-11-11T02:00:00+00:00 11 18 60
  practice-like: ... p11 2026-11-11T20:00:00+00:00 1 1 10
"""
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gecko_data import load, cap_at  # noqa: E402

EDGES = [round(2 + 0.05 * i, 2) for i in range(81)]


def iso(t):
    return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def ranked(coins, t0, t):
    cur = []
    for c in coins.values():
        if t0 <= c['launch'] < t:
            x = cap_at(c, t)
            if x is not None:
                cur.append((-x, c['mint'], c))
    cur.sort()
    return [(-a, m, c) for a, m, c in cur]


def build(coins, out, name, t0, hist_h, read_h, step_min, nreads=7):
    t0 = datetime.fromisoformat(t0).timestamp()
    cut = t0 + hist_h * 3600
    d = os.path.join(out, name + '_input')
    os.makedirs(d, exist_ok=True)
    hist = set()
    nm = 0
    with open(os.path.join(d, 'history.ndjson'), 'w') as f:
        t = t0
        while t < cut:
            rows = []
            for i, (x, m, c) in enumerate(ranked(coins, t0, t)[:200]):
                cap = int(10 ** (x + 9))
                rows.append({'rank': i + 1, 'mint': m, 'market_cap_lamports': str(cap), 'venue': 'pool', 'slot': 0,
                             'name': '', 'symbol': '', 'created_at': iso(c['launch']), 'complete': True, 'mayhem': False,
                             'quote_reserves_lamports': str(int(math.sqrt(cap / 1e9 * 17.5) * 1e9))})
                hist.add(m)
            n = len(rows)
            f.write(json.dumps({'schema': 'makefun/pumpfun-top5-forecast/mark/v1', 'at': iso(t + 5), 'ok': True, 'error': None,
                                'kind': 'mark', 't0': iso(t0), 'counts': {'eligible': n, 'graduated': n, 'excluded_non_sol': 0,
                                'priced': n, 'refused': 0, 'calls': 1, 'http_429': 0, 'stream_coverage': None}, 'rows': rows}) + '\n')
            nm += 1
            t += 600
    reads_t = [t0 + read_h * 3600 + i * step_min * 60 for i in range(nreads)]
    task = {'schema': 'makefun/pumpfun-top5-forecast/task/v1', 'competition': 'pseudo', 't0': iso(t0), 'history_until': iso(cut),
            'window': {'deadline': iso(cut), 'answer_at': iso(reads_t[-1])}, 'reads': [iso(t) for t in reads_t], 'places': 5,
            'chart_size': 100, 'size': {'edges': EDGES}, 'cadence_minutes': 10, 'output': 'forecast.json', 'marks': nm}
    json.dump(task, open(os.path.join(d, 'task.json'), 'w'), indent=1)
    reads = []
    for t in reads_t:
        r = ranked(coins, t0, t)[:100]
        chart = [m for x, m, c in r]
        # the house chart lists 100 coins, most of them young curve coins born after the cut (absent here): pad
        chart += ['Z%038dpump' % i for i in range(100 - len(chart))]
        reads.append({'chart': chart, 'sizes': [x for x, m, c in r[:5]],
                      'born_after_cut': [c['launch'] >= cut for x, m, c in r[:5]]})
    json.dump({'history_mints': sorted(hist), 'reads': reads}, open(os.path.join(out, name + '.json'), 'w'))
    return reads


if __name__ == '__main__':
    a = sys.argv
    coins = load(a[1])
    reads = build(coins, a[2], a[3], a[4], float(a[5]), float(a[6]), float(a[7]), int(a[8]) if len(a) > 8 else 7)
    print(a[3], 'top sizes', [[round(v, 2) for v in r['sizes']] for r in reads][:3], 'new', [sum(r['born_after_cut']) for r in reads])
