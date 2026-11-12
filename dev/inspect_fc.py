"""Per-place view of a forecast against a pseudo answer: size quantiles vs actual sizes, p of the actual coin.
Usage: python3 dev/inspect_fc.py <answers_dir> <contest> ['<json params>']"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import main as entry  # noqa: E402
from score import prepare, place_p, size_p, bin_of  # noqa: E402

d, name = sys.argv[1], sys.argv[2]
prm = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
task, marks = entry.load(os.path.join(d, name + '_input'))
ans = json.load(open(os.path.join(d, name + '.json')))
fc = entry.forecast(task, marks, prm)
named, sums, snamed, ssums, nb = prepare(fc, ans['history_mints'])
edges = [round(2 + 0.05 * i, 2) for i in range(81)]
for k in range(5):
    ps = [size_p(snamed, ssums, nb, k, b) for b in range(nb)]
    cum, qs = 0.0, {}
    for b in range(nb):
        cum += ps[b]
        for q in (0.1, 0.5, 0.9):
            if q not in qs and cum >= q:
                qs[q] = 2 + 0.05 * (b - 0.5)
    act = [rd['sizes'][k] for rd in ans['reads'] if len(rd['sizes']) > k]
    pa = [place_p(named, sums, k, rd['chart'][k], rd['chart']) for rd in ans['reads'] if len(rd['chart']) > k]
    print('place', k + 1, 'size q10/50/90 %.2f %.2f %.2f' % (qs[0.1], qs[0.5], qs[0.9]), 'actual', [round(a, 2) for a in act],
          'lnp size', [round(math.log(max(1e-4, size_p(snamed, ssums, nb, k, bin_of(a)))), 1) for a in act])
    print('        named sum %.3f' % sums[k], 'p(actual)', [round(p, 4) for p in pa], 'new?', [rd.get('born_after_cut', [None] * 5)[k] if len(rd['chart']) > k else None for rd in ans['reads']])
