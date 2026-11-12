"""Run entries on every pseudo-contest in <answers_dir> (pairs <name>_input/ + <name>.json) and print a table.
Usage: python3 dev/backtest.py <answers_dir> <entry.py> [<entry.py> ...] [--only prefix,prefix] [--tsv out.tsv]
"""
import json
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import score, validate  # noqa: E402


def main():
    args = sys.argv[1:]
    tsv = None
    only = None
    if '--tsv' in args:
        i = args.index('--tsv'); tsv = args[i + 1]; del args[i:i + 2]
    if '--only' in args:
        i = args.index('--only'); only = args[i + 1].split(','); del args[i:i + 2]
    d, entries = args[0], args[1:]
    names = sorted(n[:-5] for n in os.listdir(d) if n.endswith('.json') and os.path.isdir(os.path.join(d, n[:-5] + '_input')))
    if only:
        names = [n for n in names if any(n.startswith(o) for o in only)]
    lines = ['contest\tentry\torder\tsize\ttotal\tagree\tsecs']
    agg = {}
    for n in names:
        ans = json.load(open(os.path.join(d, n + '.json')))
        for e in entries:
            with tempfile.TemporaryDirectory() as out:
                env = dict(os.environ, MAKEFUN_INPUT_DIR=os.path.join(d, n + '_input'), MAKEFUN_OUTPUT_DIR=out)
                t = time.time()
                subprocess.run([sys.executable, e], env=env, check=True)
                secs = time.time() - t
                fc = json.load(open(os.path.join(out, 'forecast.json')))
            validate(fc)
            s = score(fc, ans)
            if not ans['reads'][0].get('sizes'):
                s['total'] = s['order']
            lines.append('%s\t%s\t%.3f\t%.3f\t%.3f\t%d\t%.1f' % (n, os.path.basename(e), s['order'], s['size'], s['total'], s['agreement'], secs))
            a = agg.setdefault(e, [])
            a.append(s)
    for l in lines:
        print(l)
    for e, a in agg.items():
        print('MEAN\t%s\t%.3f\t%.3f\t%.3f' % (os.path.basename(e), sum(s['order'] for s in a) / len(a), sum(s['size'] for s in a) / len(a), sum(s['total'] for s in a) / len(a)))
    if tsv:
        with open(tsv, 'a') as f:
            f.write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    main()
