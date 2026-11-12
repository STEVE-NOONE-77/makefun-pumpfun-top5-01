"""Reliability of named probabilities over the pseudo-contests: bucket each named (coin, place) p, compare with how
often that coin held that place over the reads. Also the unnamed share vs how often a place went to an unnamed coin.
Usage: python3 dev/reliability.py <answers_dir> [prefixes]"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from sweep import contests  # noqa: E402
import main as entry  # noqa: E402

d = sys.argv[1]
only = sys.argv[2].split(',') if len(sys.argv) > 2 else None
buckets = [(0, 0.001), (0.001, 0.01), (0.01, 0.05), (0.05, 0.15), (0.15, 0.35), (0.35, 0.6), (0.6, 1.01)]
agg = {b: [0.0, 0.0, 0] for b in buckets}
un = [0.0, 0.0, 0]
for name, task, marks, ans in contests(d, only):
    fc = entry.forecast(task, marks, {'sims': 3000})
    hist = set(ans['history_mints'])
    named = {}
    for r in fc['probabilities']:
        named[(r['mint'], r['place'])] = r['p']
    R = len(ans['reads'])
    for k in range(1, 6):
        at = {m: p for (m, pl), p in named.items() if pl == k}
        hits = {}
        unnamed_hits = 0
        for rd in ans['reads']:
            if len(rd['chart']) >= k:
                c = rd['chart'][k - 1]
                if c in at:
                    hits[c] = hits.get(c, 0) + 1
                else:
                    unnamed_hits += 1
        for m, p in at.items():
            for b in buckets:
                if b[0] <= p < b[1]:
                    agg[b][0] += p * R
                    agg[b][1] += hits.get(m, 0)
                    agg[b][2] += R
        un[0] += (1 - sum(at.values())) * R
        un[1] += unnamed_hits
        un[2] += R
for b in buckets:
    e, h, n = agg[b]
    if n:
        print('p in [%.3f, %.3f): expected hits %7.2f  observed %4d  (n %d)' % (b[0], b[1], e, h, n))
print('unnamed share: expected %.1f observed %d of %d place-reads' % (un[0], un[1], un[2]))
