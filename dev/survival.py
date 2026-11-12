"""Log-cap moves over 7-13 hours by age, cap level and recent volatility, from the cached market data.
Anchors every 30 min where the coin's cap >= 10^3. Survivor-biased (only coins listed by recent volume): an upper
bound on survival.
Usage: python3 dev/survival.py <cache_dir>
"""
import math
import sys
import time

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from gecko_data import load, cap_at  # noqa: E402


def q(v, p):
    return v[min(len(v) - 1, int(p * len(v)))]


def main():
    coins = load(sys.argv[1])
    now = time.time()
    rows = []
    for c in coins.values():
        if max(c['lc']) > 5.7:
            continue  # the mispriced outliers
        t = c['ts'][0]
        while t + 13 * 3600 < now - 900:
            x = cap_at(c, t)
            if x is not None and x >= 3.0:
                age = (t - c['launch']) / 3600
                past = [cap_at(c, t - 1800 * i) for i in range(1, 5)]
                pv = [p for p in past if p is not None]
                rv = (max(pv + [x]) - min(pv + [x])) if pv else 1.0
                dd = max(c['lc'][:max(1, sum(1 for s in c['ts'] if s <= t))]) - x
                for L in (7, 10, 13):
                    y = cap_at(c, t + L * 3600)
                    rows.append((age, x, rv, dd, L, y - x, c['mint']))
            t += 1800
    print(len(rows), 'anchors from', len({r[6] for r in rows}), 'coins')

    def show(label, sel):
        mv = sorted(r[5] for r in sel)
        if len(mv) < 5:
            print(label, 'n', len(mv)); return
        died = sum(1 for v in mv if v < -1.0) / len(mv)
        up = sum(1 for v in mv if v > 0) / len(mv)
        print('%-28s n %4d coins %3d  q10 %5.2f q25 %5.2f q50 %5.2f q75 %5.2f q90 %5.2f  P(<-1) %.2f P(>0) %.2f' % (
            label, len(mv), len({r[6] for r in sel}), q(mv, .1), q(mv, .25), q(mv, .5), q(mv, .75), q(mv, .9), died, up))
    for a0, a1 in ((0, 2), (2, 6), (6, 12), (12, 24), (24, 99)):
        show('age %d-%d' % (a0, a1), [r for r in rows if a0 <= r[0] < a1])
    for x0, x1 in ((3.0, 3.5), (3.5, 4.0), (4.0, 4.5), (4.5, 6)):
        show('cap %.1f-%.1f' % (x0, x1), [r for r in rows if x0 <= r[1] < x1])
    for v0, v1 in ((0, 0.1), (0.1, 0.25), (0.25, 0.5), (0.5, 9)):
        show('2h range %.2f-%.2f' % (v0, v1), [r for r in rows if v0 <= r[2] < v1])
    for d0, d1 in ((0, 0.1), (0.1, 0.3), (0.3, 9)):
        show('drawdown %.1f-%.1f' % (d0, d1), [r for r in rows if d0 <= r[3] < d1])
    show('age<6 & cap>=3.5', [r for r in rows if r[0] < 6 and r[1] >= 3.5])
    show('age>=6 & cap>=3.5', [r for r in rows if r[0] >= 6 and r[1] >= 3.5])
    for L in (7, 10, 13):
        show('L=%d' % L, [r for r in rows if r[4] == L])


if __name__ == '__main__':
    main()
