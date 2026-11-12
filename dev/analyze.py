"""Pseudo-contests from the cached market data: t0 = 02:00Z of each complete day, history to t0+11h, reads at
t0+18h..t0+24h. Prints the facts the model is built on.
Usage: python3 dev/analyze.py <cache_dir>
"""
import math
import sys
from datetime import datetime, timezone

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from gecko_data import load, cap_at  # noqa: E402

H = 3600


def main():
    coins = load(sys.argv[1])
    print(len(coins), 'coins with series')
    days = ['2026-11-09', '2026-11-10', '2026-11-11']
    allmoves = []
    for day in days:
        t0 = datetime.fromisoformat(day + 'T02:00:00+00:00').timestamp()
        field = [c for c in coins.values() if t0 <= c['launch'] < t0 + 24 * H]
        print('\n== day', day, 'coins launched that day with pool data:', len(field))
        cut = t0 + 11 * H
        at11 = sorted(((cap_at(c, cut), c['mint']) for c in field if c['launch'] < cut and cap_at(c, cut) is not None), reverse=True)
        rank11 = {m: i + 1 for i, (x, m) in enumerate(at11)}
        print(' top caps at h11:', [round(x, 2) for x, m in at11[:10]])
        for h in range(18, 25):
            t = t0 + h * H
            cur = sorted(((cap_at(c, t), c['mint']) for c in field if c['launch'] < t and cap_at(c, t) is not None), reverse=True)
            row = []
            for x, m in cur[:5]:
                c = coins[m]
                age = (t - c['launch']) / H
                tag = 'new' if c['launch'] >= cut else 'r%s' % rank11.get(m, '-')
                row.append('%.2f(%s,a%.0f)' % (x, tag, age))
            print(' h%d' % h, ' '.join(row))
        for x, m in at11[:20]:
            c = coins[m]
            for h in range(18, 25):
                y = cap_at(c, t0 + h * H)
                allmoves.append((day, x, (cut - c['launch']) / H, h - 11, y - x))
    print('\nlog-cap moves h11 -> h18..24 for coins top-20 (listed) at h11:')
    for lo, hi in ((2.5, 3.3), (3.3, 3.8), (3.8, 6)):
        mv = sorted(d for _, x, a, l, d in allmoves if lo <= x < hi)
        if mv:
            q = lambda p: mv[min(len(mv) - 1, int(p * len(mv)))]
            print(' cap %.1f-%.1f n=%d  q10 %.2f q25 %.2f q50 %.2f q75 %.2f q90 %.2f mean %.2f' % (lo, hi, len(mv), q(.1), q(.25), q(.5), q(.75), q(.9), sum(mv) / len(mv)))


if __name__ == '__main__':
    main()
