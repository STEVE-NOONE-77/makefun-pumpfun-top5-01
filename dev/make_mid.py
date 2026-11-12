"""Mid-horizon pseudo-contest on a real history: the kit's practice history (t0 2026-11-11T20:00Z, cut 21:00Z) with
answer reads built from the cached market data at whole hours after the cut (coins launched at or after t0, ranked
by their PumpSwap price; curve coins left out, as they are far below the top 5 hours later).
Usage: python3 dev/make_mid.py <cache_dir> <kit input dir> <out_dir> <name> <first read hours after cut> <nreads>
"""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gecko_data import load  # noqa: E402
from make_pseudo import ranked, iso  # noqa: E402


def main():
    cache, kit, out, name, first, nreads = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), int(sys.argv[6])
    coins = load(cache)
    d = os.path.join(out, name + '_input')
    os.makedirs(d, exist_ok=True)
    shutil.copy(os.path.join(kit, 'history.ndjson'), d)
    task = json.load(open(os.path.join(kit, 'task.json')))
    t0 = datetime.fromisoformat(task['t0'].replace('Z', '+00:00')).timestamp()
    cut = datetime.fromisoformat(task['history_until'].replace('Z', '+00:00')).timestamp()
    reads_t = [cut + first * 3600 + 3600 * i for i in range(nreads)]
    task['reads'] = [iso(t) for t in reads_t]
    task['window']['answer_at'] = task['reads'][-1]
    json.dump(task, open(os.path.join(d, 'task.json'), 'w'), indent=1)
    hist = sorted({r['mint'] for l in open(os.path.join(kit, 'history.ndjson')) if l.strip() for r in json.loads(l)['rows']})
    reads = []
    for t in reads_t:
        r = ranked(coins, t0, t)[:100]
        chart = [m for x, m, c in r]
        # the house chart lists 100 coins, most of them young curve coins born after the cut (absent here): pad
        chart += ['Z%038dpump' % i for i in range(100 - len(chart))]
        reads.append({'chart': chart, 'sizes': [x for x, m, c in r[:5]],
                      'born_after_cut': [c['launch'] >= cut for x, m, c in r[:5]]})
        print(iso(t), [(round(x, 2), m[:6], m in hist) for x, m, c in r[:5]], len(r))
    json.dump({'history_mints': hist, 'reads': reads}, open(os.path.join(out, name + '.json'), 'w'))


if __name__ == '__main__':
    main()
