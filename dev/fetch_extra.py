"""Widen the calibration set beyond GeckoTerminal's volume-sorted lists (which keep only pools with ~$1M+ of 24h
volume, a survivorship bias): mints from given history files and from DexScreener's public token-profile and boost
lists are resolved to their PumpSwap pair (with the launch time) through DexScreener, then their 15-minute OHLCV is
fetched from GeckoTerminal like the others. Public endpoints, no key, everything cached.
Usage: python3 dev/fetch_extra.py <cache_dir> [history.ndjson ...]
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_gecko import BASE, get  # noqa: E402


def fetch_json(url):
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'research-script/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main():
    cache = sys.argv[1]
    mints = set()
    for h in sys.argv[2:]:
        for line in open(h):
            if line.strip():
                for r in json.loads(line).get('rows') or []:
                    mints.add(r['mint'])
    for ep in ('token-profiles/latest/v1', 'token-boosts/latest/v1', 'token-boosts/top/v1'):
        try:
            for x in fetch_json('https://api.dexscreener.com/' + ep):
                if x.get('chainId') == 'solana' and x.get('tokenAddress', '').endswith('pump'):
                    mints.add(x['tokenAddress'])
        except Exception as e:
            print('ERR', ep, e, file=sys.stderr)
        time.sleep(1.2)
    lp = os.path.join(cache, 'launch.json')
    launch = json.load(open(lp)) if os.path.exists(lp) else {}
    xp = os.path.join(cache, 'pools_extra.json')
    extra = {p['base']: p for p in json.load(open(xp))} if os.path.exists(xp) else {}
    todo = sorted(m for m in mints if m not in extra and m not in launch)
    print(len(mints), 'mints,', len(todo), 'to resolve', file=sys.stderr)
    for i in range(0, len(todo), 30):
        batch = todo[i:i + 30]
        try:
            data = fetch_json('https://api.dexscreener.com/tokens/v1/solana/' + ','.join(batch))
        except Exception as e:
            print('ERR', e, file=sys.stderr)
            time.sleep(5)
            continue
        for x in data:
            m = x['baseToken']['address']
            if x.get('dexId') == 'pumpswap' and x.get('pairCreatedAt') and x.get('quoteToken', {}).get('symbol') == 'SOL':
                launch[m] = x['pairCreatedAt'] / 1000
                extra[m] = {'pool': x['pairAddress'], 'base': m, 'name': x['baseToken'].get('symbol', ''),
                            'pool_created_at': None}
        time.sleep(1.2)
    json.dump(launch, open(lp, 'w'), sort_keys=True)
    json.dump(sorted(extra.values(), key=lambda p: p['pool']), open(xp, 'w'))
    now = time.time()
    cand = [p for p in extra.values() if launch.get(p['base']) and now - launch[p['base']] < 4.2 * 86400]
    print(len(cand), 'extra pools to fetch', file=sys.stderr)
    for p in sorted(cand, key=lambda p: p['pool']):
        get(f"{BASE}/networks/solana/pools/{p['pool']}/ohlcv/minute?aggregate=15&currency=token&limit=1000",
            os.path.join(cache, 'ohlcv', p['pool'] + '.json'))
    print('done', file=sys.stderr)


if __name__ == '__main__':
    main()
