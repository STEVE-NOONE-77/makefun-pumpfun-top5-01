"""Fetch calibration data from GeckoTerminal's free public API (no key), caching every response.

Usage: python3 dev/fetch_gecko.py <cache_dir> [days_back]

1. Lists PumpSwap pools (pages 1-10, sorted by 24h volume and by 24h tx count).
2. For each pool whose base token is a pump.fun mint (ends in 'pump') and whose pool was created in the
   last `days_back` days, fetches 15-minute OHLCV (close in SOL per token, 1000 candles, ~10 days) and the
   token's pool list (to find the bonding-curve pool, whose creation time is the coin's launch).
Sleeps 2.2 s between network calls (GeckoTerminal allows about 30 calls a minute).
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = 'https://api.geckoterminal.com/api/v2'
_last = [0.0]


def get(url, path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    for attempt in range(5):
        wait = 2.2 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'research-script/1.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            with open(path + '.tmp', 'w') as f:
                json.dump(data, f)
            os.replace(path + '.tmp', path)
            return data
        except urllib.error.HTTPError as e:
            print('HTTP', e.code, url, file=sys.stderr)
            if e.code == 429:
                time.sleep(20 * (attempt + 1))
            elif e.code in (400, 404):
                return None
            else:
                time.sleep(5)
        except Exception as e:  # network hiccup
            print('ERR', e, url, file=sys.stderr)
            time.sleep(5)
    return None


def main():
    cache = sys.argv[1]
    days_back = float(sys.argv[2]) if len(sys.argv) > 2 else 4
    os.makedirs(os.path.join(cache, 'list'), exist_ok=True)
    os.makedirs(os.path.join(cache, 'ohlcv'), exist_ok=True)
    os.makedirs(os.path.join(cache, 'tokpools'), exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H')
    pools = {}
    for sort in ('h24_volume_usd_desc', 'h24_tx_count_desc'):
        for page in range(1, 11):
            url = f'{BASE}/networks/solana/dexes/pumpswap/pools?page={page}&sort={sort}'
            d = get(url, os.path.join(cache, 'list', f'{stamp}_{sort}_{page}.json'))
            if not d:
                continue
            for x in d.get('data', []):
                a = x['attributes']
                base = x['relationships']['base_token']['data']['id'].split('_', 1)[1]
                pools[a['address']] = {'pool': a['address'], 'base': base, 'name': a['name'],
                                       'pool_created_at': a['pool_created_at']}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    cand = [p for p in pools.values() if p['base'].endswith('pump')
            and datetime.fromisoformat(p['pool_created_at'].replace('Z', '+00:00')) >= cutoff]
    cand.sort(key=lambda p: p['pool_created_at'], reverse=True)
    print(len(pools), 'pools listed,', len(cand), 'candidates', file=sys.stderr)
    with open(os.path.join(cache, f'pools_{stamp}.json'), 'w') as f:
        json.dump(sorted(pools.values(), key=lambda p: p['pool']), f)
    for i, p in enumerate(cand):
        get(f"{BASE}/networks/solana/pools/{p['pool']}/ohlcv/minute?aggregate=15&currency=token&limit=1000",
            os.path.join(cache, 'ohlcv', p['pool'] + '.json'))
        if i % 20 == 0:
            print(i, '/', len(cand), file=sys.stderr)
    print('done', file=sys.stderr)


if __name__ == '__main__':
    main()
