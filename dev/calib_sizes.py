"""Size calibration over pooled pseudo-contests: per place, PIT values (mid-bin), coverage of the central 50% and
90% intervals, and the mean size log score. A well-calibrated forecast covers ~50% / ~90% with a flat PIT.
Usage: python3 dev/calib_sizes.py <answers_dir> [prefixes] ['<json params>']"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from sweep import contests  # noqa: E402
from score import prepare, size_p, bin_of  # noqa: E402
import main as entry  # noqa: E402


def collect(d, only, prm):
    out = {k: [] for k in range(5)}  # (pit, in50, in90, lnp, contest)
    for name, task, marks, ans in contests(d, only):
        fc = entry.forecast(task, marks, dict({'sims': 3000}, **prm))
        _, _, snamed, ssums, nb = prepare(fc, ans['history_mints'])
        for k in range(5):
            ps = [size_p(snamed, ssums, nb, k, b) for b in range(nb)]
            tot = sum(ps)
            cdf = []
            c = 0.0
            for p in ps:
                c += p / tot
                cdf.append(c)
            for rd in ans['reads']:
                if len(rd['sizes']) <= k:
                    continue
                b = bin_of(rd['sizes'][k])
                lo = cdf[b - 1] if b > 0 else 0.0
                pit = (lo + cdf[b]) / 2
                out[k].append((pit, 0.25 <= pit <= 0.75, 0.05 <= pit <= 0.95, math.log(max(1e-4, ps[b])), name))
    return out


def report(out):
    for k in range(5):
        v = out[k]
        if not v:
            continue
        n = len(v)
        hist = [0] * 5
        for pit, *_ in v:
            hist[min(4, int(pit * 5))] += 1
        print('place %d n %3d  cover50 %.2f cover90 %.2f  mean PIT %.2f  PIT quintiles %s  mean ln p %.2f' % (
            k + 1, n, sum(x[1] for x in v) / n, sum(x[2] for x in v) / n, sum(x[0] for x in v) / n, hist, sum(x[3] for x in v) / n))
    allv = [x for k in out for x in out[k]]
    n = len(allv)
    print('ALL n %d cover50 %.2f cover90 %.2f mean PIT %.2f mean ln p %.3f' % (n, sum(x[1] for x in allv) / n, sum(x[2] for x in allv) / n,
                                                                              sum(x[0] for x in allv) / n, sum(x[3] for x in allv) / n))


if __name__ == '__main__':
    d = sys.argv[1]
    only = sys.argv[2].split(',') if len(sys.argv) > 2 and sys.argv[2] else None
    prm = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    report(collect(d, only, prm))
