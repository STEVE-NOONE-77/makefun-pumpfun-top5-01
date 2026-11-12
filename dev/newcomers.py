"""Top caps of the coins born in a window [s, s+L] as seen at s+L (the newcomers of a read L hours after a cut),
for many window starts s, from the cached market data (pool coins only; outliers above 10^5.7 counted apart).
Usage: python3 dev/newcomers.py <cache_dir>
"""
import sys
import time
from datetime import datetime

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
from gecko_data import load, cap_at  # noqa: E402


def main():
    coins = load(sys.argv[1])
    now = time.time() - 1800
    s = datetime.fromisoformat('2026-11-10T13:00:00+00:00').timestamp()
    res = {}
    while s < now:
        for L in (1, 3, 7, 10, 13):
            e = s + L * 3600
            if e > now:
                continue
            caps = sorted((cap_at(c, e) for c in coins.values() if s <= c['launch'] < e and cap_at(c, e) is not None), reverse=True)
            out = sum(1 for x in caps if x > 5.7)
            caps = [x for x in caps if x <= 5.7]
            res.setdefault(L, []).append((datetime.fromtimestamp(s).strftime('%m-%d %H'), out, [round(x, 2) for x in caps[:6]]))
        s += 3600
    for L in sorted(res):
        print('L =', L, 'h  windows', len(res[L]))
        for th in (3.3, 3.5, 3.8, 4.0, 4.3, 4.6, 5.0):
            n = [sum(1 for x in c if x >= th) for _, _, c in res[L]]
            print('   E[#>=%.1f] %.2f' % (th, sum(n) / len(n)), end='')
        print()
        print('   outlier windows', sum(1 for _, o, _ in res[L] if o) / len(res[L]))
        for r in res[L][::4]:
            print('  ', r)


if __name__ == '__main__':
    main()
