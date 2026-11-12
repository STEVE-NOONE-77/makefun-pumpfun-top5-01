"""pumpfun-top5-forecast-01 entry: a Monte Carlo of the whole field at each answer read.

The forecast is scored 7 to 13 hours after the history ends (the final), so most of the coins it can see will have
collapsed by then and most places will be taken by coins not yet launched. The program reads the 10-minute marks and
simulates, independently for each read (the score is a mean of per-read log scores, so per-read marginals suffice):
  - survivors, every coin of the last mark: a collapse hazard per hour h0 * exp(-age / tau) + h_inf (young coins
    mostly collapse, older steady ones mostly hold), scaled up for coins that swung widely over the last 2 hours and
    by a runtime calibration on the history's own collapses; a coin that lives takes a Student-t move in log10(cap);
  - newcomers, the coins launched after the last mark: a Poisson process whose expected count above log cap x after
    L hours is A * L^beta * 10^(-alpha (x - 3.5)) (steeper above 10^4.6), with a per-simulation activity shock and a
    shrunk runtime calibration on the history's own field, plus rare "outlier" coins that their pools price at
    10^5.85 to 10^6.6 SOL from their first trade;
  - each simulated read's top 5 gives the order counts (a newcomer's place is left unnamed, for the scorer to share
    among the chart's coins not named) and the place sizes, smoothed in log space and mixed with a small uniform floor.
The priors come from 7-13 hour windows of PumpSwap price histories of recent pump.fun coins (see dev/).
Standard library only, seeded RNG, sorted iteration, values floored to 6 decimals: two runs write the same bytes.
"""
import json
import math
import os
import random
import sys
from datetime import datetime

IN = os.environ.get('MAKEFUN_INPUT_DIR') or '/input'
OUT = os.environ.get('MAKEFUN_OUTPUT_DIR') or '/output'

P = {
    'sims': 10000,
    'seed': 20261112,
    # survivors: collapse hazard per hour h(age) = h0 * exp(-age / tau) + h_inf (fit to the 7-13 h moves of graduated
    # coins: 81-92% of coins 0-2 h old collapse by more than 1 dex in 10 h, 43-81% at 2-6 h, 29-65% at 6-12 h, ~20%
    # older, the ranges over two fetches, the first survivor-biased; scores barely depend on it, h_inf leans higher)
    'h0': 0.9,
    'tau': 2.4,
    'h_inf': 0.03,
    'vol_hazard': 0.6,      # hazard x (1 + vol_hazard * (2 h range - 0.25) / 0.25), clipped to [vm_min, 1.8]
    'vm_min': 0.4,
    'drop_lo': 1.0,         # a collapse takes log10 cap down by U(drop_lo, drop_hi)
    'drop_hi': 2.3,
    'drift': 0.0,          # per hour, alive coins
    'vol_young': 0.22,      # per sqrt(hour), alive coin under 2 h old
    'vol_old': 0.10,        # per sqrt(hour), alive coin over 12 h old
    'nu': 3.0,
    'calib_k': 15.0,        # pseudo-count of the hazard's runtime calibration
    # newcomers: E[# born in the L hours after the cut with log cap >= x at the read] =
    #   A * L^beta * 10^(-alpha (x - 3.5)) up to x_b, steeper (alpha2) above (fit on 7-13 h windows)
    'A': 0.71,
    'beta': 0.7,
    'alpha': 0.8,
    'x_b': 4.6,
    'alpha2': 2.0,
    'x_min': 2.6,
    'act_sd': 0.55,         # ln sd of the day's activity multiplier
    'calib_k_new': 4.0,     # pseudo-count (coins >= 3.5) of the newcomer runtime calibration
    'calib_w_max': 0.1,     # most weight the runtime calibration may take
    'calib_x': 3.5,         # the calibration counts coins at or above this log cap
    # launch activity by UTC hour, relative to the prior. Coins launched 02-13Z held far fewer large caps at the
    # window's end than those launched 13-02Z (two days: 0-1 vs 2-5 coins >= 10^3.5 eleven hours on), but summed
    # over the history's lags (the calibration's statistic) the morning field looked normal, and the prior already
    # matches the evening windows: neutral (1.0), kept as a knob.
    'act_morning': 1.0,
    'morning_from': 2,
    'morning_to': 13,
    'out_rate': 0.04,       # per hour: newcomers priced as outliers (10^5.85 - 10^6.6 from their first trade; the
                            # house's pool formula on chain prices them the same, with thousands of SOL in the vault)
    'out_lo': 5.85,
    'out_hi': 6.6,
    # output
    'smooth_n': 2.0,
    'p_min': 0.0003,
    'size_bw': 0.07,
    'size_uniform': 0.02,
    'order_temper': 1.0,    # p^t over each place's outcomes (named coins + the unnamed share), t < 1 flattens
    'size_temper': 1.1,     # p^t over each place's size bins
}


def ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


def lcap(r):
    try:
        v = int(r['market_cap_lamports'])
    except (KeyError, TypeError, ValueError):
        return 0.0
    return math.log10(v) - 9 if v > 0 else 0.0


def born_at(r, default):
    try:
        return ts(r['created_at'])
    except (KeyError, TypeError, ValueError, AttributeError):
        return default


def load(indir):
    task = json.load(open(os.path.join(indir, 'task.json')))
    marks = []
    for line in open(os.path.join(indir, 'history.ndjson')):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get('ok') and isinstance(m.get('rows'), list) and isinstance(m.get('at'), str):
            m['rows'] = [r for r in m['rows'] if isinstance(r, dict) and isinstance(r.get('mint'), str)
                         and 32 <= len(r['mint']) <= 44]
            marks.append(m)
    marks.sort(key=lambda m: m['at'])
    return task, marks


def hazard_int(prm, age, L):
    """Integral of the collapse hazard from age to age + L (hours)."""
    tau = prm['tau']
    return prm['h_inf'] * L + prm['h0'] * tau * (math.exp(-age / tau) - math.exp(-(age + L) / tau))


def newcomer_count(prm, x, L, mult):
    """E[# newcomers with log cap >= x], L hours after the cut."""
    if L <= 0:
        return 0.0
    a = prm['A'] * mult * L ** prm['beta']
    if x <= prm['x_b']:
        return a * 10 ** (-prm['alpha'] * (x - 3.5))
    return a * 10 ** (-prm['alpha'] * (prm['x_b'] - 3.5)) * 10 ** (-prm['alpha2'] * (x - prm['x_b']))


def newcomer_inv(prm, lam, L, mult):
    """The log cap x at which newcomer_count(x) = lam."""
    a = prm['A'] * mult * L ** prm['beta']
    lb = a * 10 ** (-prm['alpha'] * (prm['x_b'] - 3.5))
    if lam >= lb:
        return 3.5 - math.log10(lam / a) / prm['alpha']
    return prm['x_b'] - math.log10(lam / lb) / prm['alpha2']


def activity(prm, start, L):
    """The mean launch-activity factor over the L hours from the instant `start` (UTC hours of the day)."""
    if L <= 0:
        return 1.0
    n = max(1, int(math.ceil(L * 6)))
    tot = 0.0
    for i in range(n):
        h = ((start + (i + 0.5) * L * 3600.0 / n) / 3600.0) % 24
        tot += prm['act_morning'] if prm['morning_from'] <= h < prm['morning_to'] else 1.0
    return tot / n


def calibrate(prm, marks, t0):
    """Runtime self-calibration from the history: the newcomer rate (the field of coins born since t0, as each mark
    saw it, against the prior's count) and the collapse hazard (coins at >= 10^3 that later fell 1 dex)."""
    obs = exp = 0.0
    seen_lags = set()
    for m in marks:
        L = (ts(m['at']) - t0) / 3600.0
        key = int(L * 2)  # one count per half hour of lag
        if L < 0.25 or key in seen_lags:
            continue
        seen_lags.add(key)
        obs += sum(1 for r in m['rows'] if prm['calib_x'] <= lcap(r) < prm['out_lo'])  # outliers: their own process
        exp += newcomer_count(prm, prm['calib_x'], L, activity(prm, t0, L))
    k = prm['calib_k_new']
    ratio = (obs + k) / (exp + k) if exp > 0 else 1.0
    w = min(prm['calib_w_max'], exp / (exp + k)) if exp > 0 else 0.0
    new_mult = ratio ** w
    # hazard: anchors at each mark, horizon up to 4 h within the history
    series = {}
    for m in marks:
        t = ts(m['at'])
        for r in m['rows']:
            series.setdefault(r['mint'], []).append((t, lcap(r), born_at(r, t - 3600.0)))
    hobs = hexp = 0.0
    for mint in sorted(series):
        sr = series[mint]
        for i in range(0, len(sr), 3):
            t, x, born = sr[i]
            if x < 3.0:
                continue
            # the coin's cap 2-4 h later (its last sighting in that span); a coin missing from later marks has fallen
            later = [(tt, xx) for tt, xx, _ in sr if 2 * 3600 <= tt - t <= 4 * 3600]
            if ts(marks[-1]['at']) - t < 2 * 3600:
                continue
            L = 3.0
            age = max(0.0, (t - born) / 3600.0)
            pdie = 1 - math.exp(-hazard_int(prm, age, L))
            fell = (not later) or later[-1][1] < x - 1.0
            hobs += 1.0 if fell else 0.0
            hexp += pdie
    kh = prm['calib_k']
    haz_mult = (hobs + kh * 0.5) / (hexp + kh * 0.5) if hexp > 0 else 1.0
    haz_mult = min(2.0, max(0.5, haz_mult))
    return new_mult, haz_mult, (obs, exp, hobs, hexp)


def forecast(task, marks, prm=None, info=None):
    prm = dict(P, **(prm or {}))
    places = int(task.get('places', 5))
    edges = [float(e) for e in task['size']['edges']]
    nb = len(edges) + 1
    t0 = ts(task['t0'])
    reads = sorted(ts(r) for r in task['reads'])
    marks = [m for m in marks if m['rows']]
    if not marks:
        raise ValueError('no rows')
    t_last = ts(marks[-1]['at'])
    last = sorted(marks[-1]['rows'], key=lambda r: (-lcap(r), r['mint']))
    hist_mints = sorted({r['mint'] for m in marks for r in m['rows']})
    new_mult, haz_mult, cal = calibrate(prm, marks, t0)
    if info is not None:
        info.update(new_mult=new_mult, haz_mult=haz_mult, cal=cal)

    # survivors: the last mark's coins, with their 2 h range
    series = {}
    for m in marks:
        if ts(m['at']) >= t_last - 2 * 3600 - 60:
            for r in m['rows']:
                series.setdefault(r['mint'], []).append(lcap(r))
    surv = []
    for r in last:
        x = lcap(r)
        age = max(0.0, (t_last - born_at(r, t_last - 3600.0)) / 3600.0)
        sr = series.get(r['mint'], [x])
        rng2 = max(sr) - min(sr) if len(sr) > 1 else 0.5
        vm = min(1.8, max(prm['vm_min'], 1 + prm['vol_hazard'] * (rng2 - 0.25) / 0.25))
        surv.append((r['mint'], x, age, vm))
    ns = len(surv)

    rng = random.Random(prm['seed'])
    S = int(prm['sims'])
    nr = len(reads)
    cnt = [dict() for _ in range(places)]
    newcnt = [0] * places
    sizecnt = [[0.0] * nb for _ in range(places)]
    nu = prm['nu']
    tscale = math.sqrt((nu - 2.0) / nu)
    # per read: each survivor's collapse probability and alive sd
    per_read = []
    for tr in reads:
        L = max(0.0, (tr - t_last) / 3600.0)
        pd, sd = [], []
        for (_, x, age, vm) in surv:
            pd.append(1 - math.exp(-hazard_int(prm, age, L) * vm * haz_mult))
            a_mid = age + L / 2
            v = prm['vol_young'] if a_mid <= 2 else (prm['vol_old'] if a_mid >= 12 else
                                                       prm['vol_young'] + (prm['vol_old'] - prm['vol_young']) * (a_mid - 2) / 10)
            sd.append(v * math.sqrt(L))
        per_read.append((L, pd, sd))
    read_act = [activity(prm, t_last, max(0.0, (tr - t_last) / 3600.0)) for tr in reads]
    if info is not None:
        info['read_act'] = read_act
    gauss = rng.gauss
    rand = rng.random
    for s in range(S):
        act_s = new_mult * math.exp(gauss(0.0, prm['act_sd']))
        for j in range(nr):
            L, pd, sd = per_read[j]
            vals = []
            for i in range(ns):
                x = surv[i][1]
                if rand() < pd[i]:
                    x -= prm['drop_lo'] + (prm['drop_hi'] - prm['drop_lo']) * rand()
                elif sd[i] > 0:
                    c = rng.gammavariate(nu / 2.0, 2.0 / nu)
                    x += prm['drift'] * L + sd[i] * gauss(0.0, 1.0) / math.sqrt(c) * tscale
                vals.append((x, 0, i))
            vals.sort(key=lambda e: (-e[0], e[2]))
            vals = vals[:places]
            # newcomers: the top of a Poisson process (cumulative exponentials through the inverse count)
            if L > 0:
                act = act_s * read_act[j]
                lam = 0.0
                lam_min = newcomer_count(prm, prm['x_min'], L, act)
                for _ in range(places):
                    lam += -math.log(1.0 - rand())
                    if lam > lam_min:
                        break
                    vals.append((newcomer_inv(prm, lam, L, act), 1, -1))
                no = 0
                u = rand()
                po = math.exp(-prm['out_rate'] * L)
                cum = po
                while u > cum and no < 3:
                    no += 1
                    po *= prm['out_rate'] * L / no
                    cum += po
                for _ in range(no):
                    vals.append((prm['out_lo'] + (prm['out_hi'] - prm['out_lo']) * rand(), 1, -1))
            vals.sort(key=lambda e: (-e[0], e[1], e[2]))
            for k, (v, isnew, i) in enumerate(vals[:places]):
                if isnew:
                    newcnt[k] += 1
                else:
                    cnt[k][i] = cnt[k].get(i, 0) + 1
                lo, hi = 0, len(edges)
                while lo < hi:
                    mid = (lo + hi) // 2
                    if edges[mid] <= v:
                        lo = mid + 1
                    else:
                        hi = mid
                sizecnt[k][lo] += 1.0
    if info is not None:
        info['new_share'] = [n / float(S * nr) for n in newcnt]
    return assemble(prm, task, surv, cnt, sizecnt, S * nr, places, edges, nb, last, hist_mints)


def assemble(prm, task, surv, cnt, sizecnt, N, places, edges, nb, last, hist_mints):
    ns = len(surv)
    N = float(N)
    probs = []
    pk_best = []
    for k in range(places):
        order = sorted(range(ns), key=lambda i: (-cnt[k].get(i, 0), i))[:100]
        prior_w = [1.0 / (1 + abs(i - k)) ** 2 for i in order]
        pw = sum(prior_w) or 1.0
        rows = []
        for i, w in zip(order, prior_w):
            p = (cnt[k].get(i, 0) + prm['smooth_n'] * w / pw) / (N + prm['smooth_n'])
            rows.append([surv[i][0], p])
        # global temper over the place's outcomes (each named coin, and the unnamed share as one outcome)
        tau = prm['order_temper']
        if tau != 1.0:
            un = max(1e-9, 1.0 - sum(p for _, p in rows))
            z = sum(p ** tau for _, p in rows) + un ** tau
            for r in rows:
                r[1] = r[1] ** tau / z
        for r in rows:
            r[1] = max(r[1], prm['p_min'])
        tot = sum(p for _, p in rows)
        if tot > 0.995:
            for r in rows:
                r[1] *= 0.995 / tot
        for mint, p in rows:
            probs.append({'mint': mint, 'place': k + 1, 'p': p})
        pk_best.append([m for m, _ in sorted(rows, key=lambda r: (-r[1], r[0]))])
    sizes = []
    centers = [edges[0] - 0.025] + [(edges[i - 1] + edges[i]) / 2 for i in range(1, len(edges))] + [edges[-1] + 0.025]
    bw = prm['size_bw']
    for k in range(places):
        h = sizecnt[k]
        sm = [0.0] * nb
        for b in range(nb):
            if h[b] == 0:
                continue
            if b == 0 or b == nb - 1:  # the open tails hold their own mass
                sm[b] += h[b]
                continue
            ws = [math.exp(-0.5 * ((centers[c] - centers[b]) / bw) ** 2) for c in range(nb)]
            sw = sum(ws)
            for c in range(nb):
                sm[c] += h[b] * ws[c] / sw
        if prm['size_temper'] != 1.0:  # global temper of the size distribution
            sm = [v ** prm['size_temper'] if v > 0 else 0.0 for v in sm]
        tot = sum(sm) or 1.0
        u = prm['size_uniform']
        for b in range(nb):
            sizes.append({'place': k + 1, 'bin': b, 'p': (1 - u) * sm[b] / tot + u / nb})
    top5 = []
    for k in range(places):
        for m in pk_best[k]:
            if m not in top5:
                top5.append(m)
                break
    for m in [r['mint'] for r in last] + hist_mints:
        if len(top5) >= places:
            break
        if m not in top5:
            top5.append(m)
    i = 0
    while len(top5) < places:
        top5.append('1111111111111111111111111111111%d' % i)
        i += 1
    return finalize({'probabilities': probs, 'top5': top5[:places], 'sizes': sizes}, places, nb, set(hist_mints))


def finalize(fc, places, nb, hist):
    """Round down to 6 decimals, keep each place's sums <= 0.999999, check the shape."""
    probs = []
    sums = [0.0] * places
    seen = set()
    rows_per = [0] * places
    for r in sorted(fc['probabilities'], key=lambda r: (r['place'], -r['p'], r['mint'])):
        k = r['place']
        if r['mint'] not in hist or (r['mint'], k) in seen or rows_per[k - 1] >= 100:
            continue
        p = math.floor(min(1.0, max(0.0, r['p'])) * 1e6) / 1e6
        if sums[k - 1] + p > 0.999999:
            p = max(0.0, math.floor((0.999999 - sums[k - 1]) * 1e6) / 1e6)
        seen.add((r['mint'], k))
        rows_per[k - 1] += 1
        sums[k - 1] += p
        probs.append({'mint': r['mint'], 'place': k, 'p': p})
    sizes = []
    ssum = [0.0] * places
    for r in sorted(fc['sizes'], key=lambda r: (r['place'], r['bin'])):
        k = r['place']
        p = math.floor(min(1.0, max(0.0, r['p'])) * 1e6) / 1e6
        if ssum[k - 1] + p > 0.999999:
            p = max(0.0, math.floor((0.999999 - ssum[k - 1]) * 1e6) / 1e6)
        if p <= 0:
            continue
        ssum[k - 1] += p
        sizes.append({'place': k, 'bin': r['bin'], 'p': p})
    top5 = list(fc['top5'])
    out = {'probabilities': probs, 'top5': top5, 'sizes': sizes}
    check(out, places, nb)
    return out


def check(fc, places, nb):
    assert sorted(fc) == ['probabilities', 'sizes', 'top5']
    sums = [0.0] * places
    n = [0] * places
    seen = set()
    for r in fc['probabilities']:
        assert isinstance(r['mint'], str) and 32 <= len(r['mint']) <= 44
        assert isinstance(r['place'], int) and 1 <= r['place'] <= places
        assert 0 <= r['p'] <= 1 and (r['mint'], r['place']) not in seen
        seen.add((r['mint'], r['place']))
        sums[r['place'] - 1] += r['p']
        n[r['place'] - 1] += 1
    assert max(sums) <= 0.9999995 and max(n) <= 100
    t = fc['top5']
    assert len(t) == places and len(set(t)) == places and all(isinstance(m, str) and 32 <= len(m) <= 44 for m in t)
    ss = [0.0] * places
    sseen = set()
    for r in fc['sizes']:
        assert isinstance(r['bin'], int) and 0 <= r['bin'] < nb and 1 <= r['place'] <= places
        assert 0 <= r['p'] <= 1 and (r['place'], r['bin']) not in sseen
        sseen.add((r['place'], r['bin']))
        ss[r['place'] - 1] += r['p']
    assert max(ss) <= 0.9999995


def fallback(task, marks):
    """A safe forecast: persistence of the last mark, the even spread elsewhere."""
    places = int(task.get('places', 5))
    nb = len(task['size']['edges']) + 1
    rows = []
    for m in reversed(marks):
        if m.get('rows'):
            rows = sorted(m['rows'], key=lambda r: (-lcap(r), r['mint']))
            break
    probs = []
    top5 = []
    for r in rows:
        if r['mint'] not in top5:
            top5.append(r['mint'])
        if len(top5) == places:
            break
    for k in range(places):
        if k < len(top5):
            probs.append({'mint': top5[k], 'place': k + 1, 'p': 0.1})
    i = 0
    while len(top5) < places:  # cannot happen on a real history; a valid shape all the same
        top5.append('1111111111111111111111111111111%d' % i)
        i += 1
    # sizes: place k's log cap normal around 4.7 - 0.25 (k - 1), sd 0.5 (the reads of the days studied), 3% uniform
    edges = [float(e) for e in task['size']['edges']]
    sizes = []
    for k in range(places):
        mu = 4.7 - 0.25 * k
        cdf = [0.0] + [0.5 * math.erfc(-(e - mu) / (0.5 * math.sqrt(2))) for e in edges] + [1.0]
        for b in range(nb):
            p = math.floor((0.97 * (cdf[b + 1] - cdf[b]) + 0.03 / nb) * 1e6) / 1e6
            if p > 0:
                sizes.append({'place': k + 1, 'bin': b, 'p': p})
    return {'probabilities': probs, 'top5': top5, 'sizes': sizes}


def main():
    task = {'places': 5, 'size': {'edges': [round(2 + 0.05 * i, 2) for i in range(81)]}, 'output': 'forecast.json'}
    marks = []
    try:
        task, marks = load(IN)
        fc = forecast(task, marks)
    except Exception as e:  # never leave without a forecast
        print('forecast failed, falling back:', repr(e), file=sys.stderr)
        fc = fallback(task, marks)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, task.get('output') or 'forecast.json'), 'w') as f:
        f.write(json.dumps(fc, separators=(',', ':')) + '\n')


if __name__ == '__main__':
    main()
