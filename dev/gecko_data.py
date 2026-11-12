"""Load the cached GeckoTerminal / DexScreener data into per-coin log10(cap in SOL) step series.

A coin's cap at time T is the close of the last 15-minute candle that ended at or before T (price in SOL per token
x 1e9, the ordinary 1B supply). Before its first PumpSwap candle the coin is on its curve (cap under ~10^2.6 SOL):
cap_at returns None then.
"""
import bisect
import glob
import json
import math
import os


def load(cache):
    launch = json.load(open(os.path.join(cache, 'launch.json')))
    pools = {}
    for f in sorted(glob.glob(os.path.join(cache, 'pools_*.json'))):
        for p in json.load(open(f)):
            if p['base'].endswith('pump'):
                pools.setdefault(p['base'], p['pool'])
    coins = {}
    for base, pool in sorted(pools.items()):
        f = os.path.join(cache, 'ohlcv', pool + '.json')
        if not os.path.exists(f) or not launch.get(base):
            continue
        try:
            d = json.load(open(f))
            lst = d['data']['attributes']['ohlcv_list']
            if d['meta']['quote']['address'] != 'So11111111111111111111111111111111111111112':
                continue  # quoted in another coin: not a contest coin
        except Exception:
            continue
        pts = sorted((int(c[0]) + 900, float(c[4])) for c in lst if float(c[4]) > 0)
        if not pts:
            continue
        coins[base] = {'mint': base, 'launch': float(launch[base]), 'ts': [p[0] for p in pts],
                       'lc': [math.log10(p[1] * 1e9) for p in pts]}
    return coins


def cap_at(c, t):
    i = bisect.bisect_right(c['ts'], t) - 1
    if i < 0:
        return None
    return c['lc'][i]
