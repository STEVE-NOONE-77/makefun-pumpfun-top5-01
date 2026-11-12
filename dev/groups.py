"""Score parameter sets per group: A (t0 Nov 10), B (t0 Nov 11), mid (M*), short (P*, practice*), today (T*).
Usage: python3 dev/groups.py <answers_dir> '<json list of params>' [sims]"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sweep import contests, run  # noqa: E402

GROUPS = {'A': ('F10',), 'B': ('F11',), 'mid': ('M',), 'short': ('P', 'practice'), 'today': ('T',)}
if __name__ == '__main__':
    d = sys.argv[1]
    sims = int(sys.argv[3]) if len(sys.argv) > 3 else 2000
    cs = contests(d)
    for prm in json.loads(sys.argv[2]):
        res, _ = run(cs, dict(prm, sims=sims), verbose=False)
        out = []
        for g, pre in GROUPS.items():
            ns = [n for n in res if n.startswith(pre)]
            if ns:
                out.append('%s %.3f' % (g, sum(res[n]['total'] for n in ns) / len(ns)))
        print(json.dumps(prm), ' | '.join(out), flush=True)
