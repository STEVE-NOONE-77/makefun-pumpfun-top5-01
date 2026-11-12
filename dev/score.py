"""Local scorer for pumpfun-top5-forecast-01 (stdlib only), mirroring the rules' Scoring section.

Answer file (JSON): {"history_mints": [...], "edges": [81 edges] (optional),
                     "reads": [{"chart": [mint, ...  place 1 first, up to 100],
                                "sizes": [log10 cap in SOL of place 1..5]}, ...]}

Usage: python3 dev/score.py forecast.json answer.json      (prints order, size, total, agreement)
       python3 dev/score.py --selftest                      (the rules' worked examples)
"""
import json
import math
import sys

FLOOR = 1e-4
EDGES = [round(2 + 0.05 * i, 2) for i in range(81)]


def bin_of(r, edges=EDGES):
    lo, hi = 0, len(edges)
    while lo < hi:
        mid = (lo + hi) // 2
        if edges[mid] <= r:
            lo = mid + 1
        else:
            hi = mid
    return lo


def prepare(forecast, history_mints, places=5):
    """Per place: {mint: p} after dropping rows on mints the history never names, and the place's sum."""
    hist = set(history_mints) if history_mints is not None else None
    named = [dict() for _ in range(places)]
    for row in forecast.get('probabilities', []):
        if hist is not None and row['mint'] not in hist:
            continue
        named[row['place'] - 1][row['mint']] = row['p']
    sums = [sum(d.values()) for d in named]
    nbins = len(EDGES) + 1
    snamed = [dict() for _ in range(places)]
    for row in forecast.get('sizes', []):
        snamed[row['place'] - 1][row['bin']] = row['p']
    ssums = [sum(d.values()) for d in snamed]
    return named, sums, snamed, ssums, nbins


def place_p(named, sums, k, mint, chart):
    at = named[k]
    if mint in at:
        return at[mint]
    unnamed = sum(1 for c in set(chart) if c not in at)
    left = max(0.0, 1 - sums[k])
    return 0.0 if unnamed == 0 else left / unnamed


def size_p(snamed, ssums, nbins, k, b):
    at = snamed[k]
    if b in at:
        return at[b]
    unnamed = nbins - len(at)
    left = max(0.0, 1 - ssums[k])
    return 0.0 if unnamed == 0 else left / unnamed


def agreement(top, chart, places=5):
    head = chart[:places]
    pts = 0
    for i, m in enumerate(top):
        if m in head:
            pts += places - abs(i - head.index(m))
    return pts


def score(forecast, answer, places=5, detail=False):
    named, sums, snamed, ssums, nbins = prepare(forecast, answer.get('history_mints'), places)
    hist = set(answer['history_mints']) if answer.get('history_mints') is not None else None
    top = [m for m in forecast.get('top5', []) if hist is None or m in hist]
    o_tot = s_tot = agr = 0.0
    per_place_o = [0.0] * places
    per_place_s = [0.0] * places
    reads = answer['reads']
    for rd in reads:
        chart = rd['chart']
        n = min(places, len(chart))
        for k in range(n):
            lo = math.log(max(place_p(named, sums, k, chart[k], chart), FLOOR))
            o_tot += lo
            per_place_o[k] += lo
        for k, v in enumerate(rd.get('sizes', [])[:n]):
            ls = math.log(max(size_p(snamed, ssums, nbins, k, bin_of(v)), FLOOR))
            s_tot += ls
            per_place_s[k] += ls
        agr += agreement(top, chart, places)
    R = len(reads)
    out = {'order': o_tot / R, 'size': s_tot / R, 'total': (o_tot + s_tot) / R, 'agreement': agr}
    if detail:
        out['order_by_place'] = [x / R for x in per_place_o]
        out['size_by_place'] = [x / R for x in per_place_s]
    return out


def validate(forecast, places=5, nbins=82):
    """Raise ValueError when the forecast is not of the rules' shape."""
    if not isinstance(forecast, dict) or sorted(forecast) != ['probabilities', 'sizes', 'top5']:
        raise ValueError('keys')
    sums = [0.0] * places
    seen = set()
    counts = [0] * places
    for r in forecast['probabilities']:
        if sorted(r) != ['mint', 'p', 'place']:
            raise ValueError('prob row keys')
        if not isinstance(r['mint'], str) or not (32 <= len(r['mint']) <= 44):
            raise ValueError('mint')
        if not isinstance(r['place'], int) or isinstance(r['place'], bool) or not 1 <= r['place'] <= places:
            raise ValueError('place')
        if not isinstance(r['p'], (int, float)) or isinstance(r['p'], bool) or not 0 <= r['p'] <= 1:
            raise ValueError('p')
        if (r['mint'], r['place']) in seen:
            raise ValueError('dup')
        seen.add((r['mint'], r['place']))
        sums[r['place'] - 1] += r['p']
        counts[r['place'] - 1] += 1
    if max(sums) > 1 or max(counts) > 100:
        raise ValueError('sum/count %s %s' % (sums, counts))
    t = forecast['top5']
    if not isinstance(t, list) or len(t) != places or len(set(t)) != places or not all(isinstance(x, str) for x in t):
        raise ValueError('top5')
    ss = [0.0] * places
    sseen = set()
    for r in forecast['sizes']:
        if sorted(r) != ['bin', 'p', 'place']:
            raise ValueError('size row keys')
        if not isinstance(r['bin'], int) or not 0 <= r['bin'] < nbins or not isinstance(r['place'], int) or not 1 <= r['place'] <= places:
            raise ValueError('bin/place')
        if not isinstance(r['p'], (int, float)) or not 0 <= r['p'] <= 1:
            raise ValueError('size p')
        if (r['place'], r['bin']) in sseen:
            raise ValueError('size dup')
        sseen.add((r['place'], r['bin']))
        ss[r['place'] - 1] += r['p']
    if max(ss) > 1:
        raise ValueError('size sum %s' % ss)
    return {'prob_sums': sums, 'size_sums': ss, 'rows': counts}


def selftest():
    A, B, C, D, E, F, G = [ch * 40 + 'pump' for ch in 'ABCDEFG']
    fc = {'probabilities': [{'mint': A, 'place': 1, 'p': 0.5}, {'mint': B, 'place': 1, 'p': 0.2}, {'mint': B, 'place': 2, 'p': 0.4}],
          'top5': [A, B, C, D, E], 'sizes': [{'place': 1, 'bin': 26, 'p': 0.3}, {'place': 1, 'bin': 27, 'p': 0.3}]}
    filler = ['X%039dpump' % i for i in range(95)]
    hist = [A, B, C, D, E] + filler
    r1 = {'chart': [A, C, B, F, G] + filler, 'sizes': [math.log10(1800), 3.0, 3.0, 3.0, 3.0]}
    r2 = {'chart': [A, B, C, F, G] + filler, 'sizes': [math.log10(2100), 3.0, 3.0, 3.0, 3.0]}
    s1 = score(fc, {'history_mints': hist, 'reads': [r1]})
    s2 = score(fc, {'history_mints': hist, 'reads': [r2]})
    s12 = score(fc, {'history_mints': hist, 'reads': [r1, r2]})
    assert abs(s1['total'] - -38.445453) < 1e-6, s1
    assert abs(s1['order'] - -19.614603) < 1e-6 and abs(s1['size'] - -18.830850) < 1e-6, s1
    assert s1['agreement'] == 13, s1
    assert abs(s2['total'] - -34.255798) < 1e-6 and s2['agreement'] == 15, s2
    assert abs(s12['total'] - -36.350626) < 1e-6 and abs(s12['order'] - -17.519776) < 1e-6, s12
    even = score({'probabilities': [], 'top5': [A, B, C, D, E], 'sizes': []}, {'history_mints': hist, 'reads': [r1, r2]})
    assert abs(even['total'] - -45.059447) < 1e-6, even
    # a row naming F (born after the cut) is dropped: same score
    fc2 = dict(fc, probabilities=fc['probabilities'] + [{'mint': F, 'place': 4, 'p': 0.9}])
    assert abs(score(fc2, {'history_mints': hist, 'reads': [r1]})['total'] - s1['total']) < 1e-12
    validate(fc)
    print('selftest ok:', round(s1['total'], 6), round(s2['total'], 6), round(s12['total'], 6), round(even['total'], 6))


if __name__ == '__main__':
    if sys.argv[1:2] == ['--selftest']:
        selftest()
    else:
        fc = json.load(open(sys.argv[1]))
        ans = json.load(open(sys.argv[2]))
        print(json.dumps(validate(fc)))
        print(json.dumps(score(fc, ans, detail=True)))
