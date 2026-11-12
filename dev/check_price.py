"""Price-mapping check: the house's pool formula on chain now vs DexScreener's live price.

For each mint: derive the canonical PumpSwap pool (PDA ["pool", u16 LE 0, pool_authority, mint, WSOL] under
pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA, pool_authority = PDA ["pool-authority", mint] under the pump program),
read it and its two vaults with getMultipleAccounts from the public mainnet RPC (no key), and compute
cap = (quote vault amount + virtual_quote_reserves (i128 at byte 245)) * S / base vault amount, S = 1e15 (2e15 mayhem).
Usage: python3 dev/check_price.py <mint> [<mint> ...]
"""
import base64
import hashlib
import json
import math
import sys
import time
import urllib.request

ALPH = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
RPC = 'https://api.mainnet-beta.solana.com'
PUMP = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P'
PAMM = 'pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA'
WSOL = 'So11111111111111111111111111111111111111112'


def b58d(s):
    n = 0
    for c in s:
        n = n * 58 + ALPH.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, 'big') if n else b''
    return b'\0' * (len(s) - len(s.lstrip('1'))) + b


def b58e(b):
    n = int.from_bytes(b, 'big')
    s = ''
    while n:
        n, r = divmod(n, 58)
        s = ALPH[r] + s
    return '1' * (len(b) - len(b.lstrip(b'\0'))) + s


P_ = 2 ** 255 - 19
D_ = (-121665 * pow(121666, P_ - 2, P_)) % P_


def on_curve(b):
    y = int.from_bytes(b, 'little') & ((1 << 255) - 1)
    if y >= P_:
        return False
    u = (y * y - 1) % P_
    v = (D_ * y * y + 1) % P_
    x2 = u * pow(v, P_ - 2, P_) % P_
    if x2 == 0:
        return not (b[31] >> 7)
    return pow(x2, (P_ - 1) // 2, P_) == 1


def pda(seeds, program):
    for bump in range(255, -1, -1):
        h = hashlib.sha256(b''.join(seeds) + bytes([bump]) + b58d(program) + b'ProgramDerivedAddress').digest()
        if not on_curve(h):
            return b58e(h)
    raise ValueError('no pda')


def rpc(method, params):
    req = urllib.request.Request(RPC, data=json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode(),
                                 headers={'Content-Type': 'application/json', 'User-Agent': 'research-script/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)['result']


def dexs_price(mint):
    req = urllib.request.Request('https://api.dexscreener.com/tokens/v1/solana/' + mint, headers={'User-Agent': 'research-script/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        for x in json.load(r):
            if x.get('dexId') == 'pumpswap':
                return float(x['priceNative']), x['pairAddress']
    return None, None


def main():
    for mint in sys.argv[1:]:
        auth = pda([b'pool-authority', b58d(mint)], PUMP)
        pool = pda([b'pool', (0).to_bytes(2, 'little'), b58d(auth), b58d(mint), b58d(WSOL)], PAMM)
        acc = rpc('getMultipleAccounts', [[pool], {'encoding': 'base64'}])['value'][0]
        if acc is None:
            print(mint[:8], 'no canonical pool', pool)
            continue
        d = base64.b64decode(acc['data'][0])
        base_vault, quote_vault = b58e(d[139:171]), b58e(d[171:203])
        vq = int.from_bytes(d[245:261], 'little', signed=True)
        mayhem = d[243] if len(d) > 243 else None
        res = rpc('getMultipleAccounts', [[base_vault, quote_vault], {'encoding': 'base64'}])
        slot = res['context']['slot']
        amt = [int.from_bytes(base64.b64decode(a['data'][0])[64:72], 'little') for a in res['value']]
        S = 2 * 10 ** 15 if mayhem == 1 else 10 ** 15
        cap = (amt[1] + vq) * S // amt[0]
        time.sleep(1.0)
        pn, pair = dexs_price(mint)
        dx = math.log10(pn * 1e9 * (2 if mayhem == 1 else 1)) if pn else float('nan')
        print('%s pool %s (dexscreener pair %s) slot %d mayhem_byte %s base %d quote %d vq %d -> house log cap %.3f, '
              'dexscreener price x supply %.3f, diff %.3f' % (mint[:8], pool[:8], (pair or '')[:8], slot, mayhem, amt[0], amt[1], vq,
                                                            math.log10(cap) - 9, dx, math.log10(cap) - 9 - dx))
        time.sleep(1.0)


if __name__ == '__main__':
    main()
