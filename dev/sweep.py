"""In-process parameter sweeps of main.forecast over the pseudo-contests.
Usage: python3 dev/sweep.py <answers_dir> '<json list of param overrides>' [--only a,b] [--sims N]
Prints per contest order/size/total and a weighted mean (long-horizon contests F*, mid M*, short P*/practice*).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import main as entry  # noqa: E402
from score import score  # noqa: E402


def contests(d, only=None):
    out = []
    for n in sorted(os.listdir(d)):
        if n.endswith('.json') and os.path.isdir(os.path.join(d, n[:-5] + '_input')):
            name = n[:-5]
            if only and not any(name.startswith(o) for o in only):
                continue
            task, marks = entry.load(os.path.join(d, name + '_input'))
            out.append((name, task, marks, json.load(open(os.path.join(d, n)))))
    return out


def run(cs, prm, verbose=True):
    res = {}
    for name, task, marks, ans in cs:
        info = {}
        try:
            fc = entry.forecast(task, marks, prm, info)
        except Exception as e:
            fc = entry.fallback(task, marks)
            info['err'] = repr(e)
        s = score(fc, ans)
        if not ans['reads'][0].get('sizes'):
            s['size'] = 0.0
            s['total'] = s['order']
        res[name] = s
        if verbose:
            print('  %-14s order %8.3f size %8.3f total %8.3f  %s' % (name, s['order'], s['size'], s['total'],
                  {k: (round(v, 3) if isinstance(v, float) else ([round(x, 2) for x in v] if isinstance(v, (list, tuple)) else v)) for k, v in info.items()}))
    groups = {'long': [n for n in res if n.startswith('F')], 'mid': [n for n in res if n.startswith('M')],
              'short': [n for n in res if n.startswith('P') or n.startswith('practice')]}
    summ = {g: (sum(res[n]['total'] for n in ns) / len(ns) if ns else 0.0) for g, ns in groups.items()}
    return res, summ


if __name__ == '__main__':
    a = sys.argv[1:]
    only = None
    sims = None
    if '--only' in a:
        i = a.index('--only'); only = a[i + 1].split(','); del a[i:i + 2]
    if '--sims' in a:
        i = a.index('--sims'); sims = int(a[i + 1]); del a[i:i + 2]
    cs = contests(a[0], only)
    for prm in json.loads(a[1]):
        if sims:
            prm = dict(prm, sims=sims)
        print(prm)
        res, summ = run(cs, prm)
        print('  SUMMARY', {k: round(v, 3) for k, v in summ.items()}, 'weighted', round(0.6 * summ['long'] + 0.25 * summ['mid'] + 0.15 * summ['short'], 3))
