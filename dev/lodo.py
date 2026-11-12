"""Leave-one-day-out: coordinate-descent fit of the swept parameters on one group of final-like contests, scored on
the other. Group A = t0 on Nov 10 (F10*), group B = t0 on Nov 11 (F11*). Writes the full grid to <out.json>.
Usage: python3 dev/lodo.py <answers_dir> <out.json> [sims]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sweep import contests, run  # noqa: E402

GRID = {
    'out_rate': [0.0, 0.02, 0.035, 0.06, 0.09],
    'drift': [-0.03, -0.01, 0.0, 0.01],
    'alpha': [0.65, 0.8, 0.95],
    'A': [0.5, 0.71, 1.0],
    'act_sd': [0.25, 0.45, 0.7],
    'h0': [0.6, 0.9, 1.3],
    'h_inf': [0.012, 0.025, 0.045],
    'p_min': [0.0001, 0.0003, 0.001],
    'calib_w_max': [0.0, 0.3, 0.6],
    'size_uniform': [0.01, 0.02, 0.05],
    'size_bw': [0.05, 0.07, 0.12],
}


def mean(res, names):
    return sum(res[n]['total'] for n in names) / len(names)


def main():
    d, out = sys.argv[1], sys.argv[2]
    sims = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    cs = contests(d, ['F'])
    A = [c[0] for c in cs if c[0].startswith('F10')]
    B = [c[0] for c in cs if c[0].startswith('F11')]
    cache = {}

    def evalp(prm):
        key = json.dumps(prm, sort_keys=True)
        if key not in cache:
            res, _ = run(cs, dict(prm, sims=sims), verbose=False)
            cache[key] = {n: res[n]['total'] for n in res}
        return cache[key]

    def score(prm, names):
        r = evalp(prm)
        return sum(r[n] for n in names) / len(names)

    fits = {}
    for gname, train in (('A', A), ('B', B)):
        cur = {}
        for p, vals in GRID.items():
            best = max(vals, key=lambda v: (score(dict(cur, **{p: v}), train), -abs(vals.index(v) - len(vals) // 2)))
            cur[p] = best
        fits[gname] = cur
        print('fit on', gname, cur, flush=True)
    base = evalp({})
    table = {'groups': {'A': A, 'B': B}, 'current': base, 'fit_A': evalp(fits['A']), 'fit_B': evalp(fits['B']),
             'fits': fits, 'grid': {p: {str(v): evalp({p: v}) for v in vals} for p, vals in GRID.items()}}
    json.dump(table, open(out, 'w'), indent=1)
    for label, prm in (('current', {}), ('fit on A', fits['A']), ('fit on B', fits['B'])):
        print('%-10s A %.3f  B %.3f' % (label, score(prm, A), score(prm, B)))


if __name__ == '__main__':
    main()
