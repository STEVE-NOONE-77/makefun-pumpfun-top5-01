"""The house baseline ported to Python (persistence of the last mark), for the backtests. Thin pseudo histories with
fewer than 5 ranked coins get filler mints (the house's own program would stop there)."""
import json
import math
import os

IN = os.environ.get('MAKEFUN_INPUT_DIR') or '/input'
OUT = os.environ.get('MAKEFUN_OUTPUT_DIR') or '/output'


def main():
    task = json.load(open(os.path.join(IN, 'task.json')))
    marks = [json.loads(l) for l in open(os.path.join(IN, 'history.ndjson')) if l.strip()]
    marks = [m for m in marks if m.get('ok') and isinstance(m.get('rows'), list)]
    chart = sorted(marks[-1]['rows'], key=lambda r: r['rank'])
    while len(chart) < 6:
        chart.append({'mint': 'F%043d' % len(chart), 'market_cap_lamports': str(10 ** 11)})
    edges = task['size']['edges']
    places = task['places']
    probs, sizes = [], []
    for k in range(1, places + 1):
        probs.append({'mint': chart[k - 1]['mint'], 'place': k, 'p': 0.3})
        if k > 1:
            probs.append({'mint': chart[k - 2]['mint'], 'place': k, 'p': 0.1})
        if k < len(chart):
            probs.append({'mint': chart[k]['mint'], 'place': k, 'p': 0.1})
        mean = math.log10(int(chart[k - 1]['market_cap_lamports'])) - 9
        cdf = lambda x: 0.5 * math.erfc(-(x - mean) / (0.35 * math.sqrt(2)))
        for b in range(len(edges) + 1):
            lo = 0.0 if b == 0 else cdf(edges[b - 1])
            hi = 1.0 if b == len(edges) else cdf(edges[b])
            u = math.floor((hi - lo) * 1e6)
            if u > 0:
                sizes.append({'place': k, 'bin': b, 'p': u / 1e6})
    out = {'probabilities': probs, 'top5': [r['mint'] for r in chart[:places]], 'sizes': sizes}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, task.get('output', 'forecast.json')), 'w') as f:
        f.write(json.dumps(out) + '\n')


if __name__ == '__main__':
    main()
