"""Launch times (DexScreener's pairCreatedAt of the PumpSwap pair equals the coin's CreateEvent time) for every
pump mint in the cached GeckoTerminal pool lists. Public API, no key, 30 mints per call, cached.
Usage: python3 dev/fetch_dexs.py <cache_dir>
"""
import glob
import json
import os
import sys
import time
import urllib.request


def main():
    cache = sys.argv[1]
    mints = set()
    for f in glob.glob(os.path.join(cache, 'pools_*.json')):
        for p in json.load(open(f)):
            if p['base'].endswith('pump'):
                mints.add(p['base'])
    out_path = os.path.join(cache, 'launch.json')
    launch = json.load(open(out_path)) if os.path.exists(out_path) else {}
    todo = sorted(m for m in mints if m not in launch)
    for i in range(0, len(todo), 30):
        batch = todo[i:i + 30]
        url = 'https://api.dexscreener.com/tokens/v1/solana/' + ','.join(batch)
        req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'research-script/1.0'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
        except Exception as e:
            print('ERR', e, file=sys.stderr)
            time.sleep(5)
            continue
        for x in data:
            m = x['baseToken']['address']
            if x.get('dexId') == 'pumpswap' and x.get('pairCreatedAt'):
                launch[m] = min(launch.get(m, 1e18), x['pairCreatedAt'] / 1000)
        for m in batch:
            launch.setdefault(m, None)
        time.sleep(1.2)
    json.dump(launch, open(out_path, 'w'), sort_keys=True)
    print(len(launch), 'launch times,', sum(1 for v in launch.values() if v), 'known', file=sys.stderr)


if __name__ == '__main__':
    main()
