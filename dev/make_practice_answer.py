"""Practice-proxy answers built from the kit's practice input.

1. 'practice_last': the one read whose top 5 the rules publish (the last practice read), order only; its chart is the
   known top 5, then the last mark's other coins by rank, then filler for coins born after the cut, 100 in all.
   The filler share is a guess (the rules give 2 of 5 top coins born after the cut), so this is a weak proxy.
2. 'practice_cut3': pseudo-answer from the history itself: history cut after the 20:30 mark, answer = the 20:40 and
   20:50 marks (charts and sizes from the marks).
Usage: python3 dev/make_practice_answer.py <kit input dir> <out dir>
"""
import json
import math
import os
import sys

TOP5 = ['5qaP7oKUqKffwwo5DaEqDoTtsBLMpdbQTxEkCDaTpump', '4Dgjitjn8br3LcdcBnkc9tYJ8d1cnCCJd2nsVgzZpump',
        'BuaseKYxFH5Bcz6uoTU2JiX32hRGsGfGLTgamoWpump', 'HzwVr7KjPhUriHK9MrJbFzbTDTPwUXGrL2Ah2wVhpump',
        'FjFVmDDM3w7qVLS9uxLkXnDM4qCGsqXSow6d32phpump']


def main():
    src, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    marks = [json.loads(l) for l in open(os.path.join(src, 'history.ndjson')) if l.strip()]
    hist = sorted({r['mint'] for m in marks for r in m['rows']})
    print('known top5 in history:', [m in hist for m in TOP5])
    last = sorted(marks[-1]['rows'], key=lambda r: r['rank'])
    chart = list(TOP5)
    for r in last:  # about 60 of the chart from the history, the rest newcomers (guess)
        if len(chart) >= 65:
            break
        if r['mint'] not in chart:
            chart.append(r['mint'])
    i = 0
    while len(chart) < 100:
        chart.append('N%039dpump' % i)
        i += 1
    json.dump({'history_mints': hist, 'reads': [{'chart': chart, 'sizes': []}]}, open(os.path.join(out, 'practice_last.json'), 'w'))
    # pseudo: cut after mark index 3 (20:30)
    cut = 4
    os.makedirs(os.path.join(out, 'practice_cut3_input'), exist_ok=True)
    with open(os.path.join(out, 'practice_cut3_input', 'history.ndjson'), 'w') as f:
        for m in marks[:cut]:
            f.write(json.dumps(m) + '\n')
    task = json.load(open(os.path.join(src, 'task.json')))
    task['history_until'] = marks[cut]['at'][:16] + ':00.000Z'
    task['reads'] = [m['at'][:16] + ':00.000Z' for m in marks[cut:]]
    task['marks'] = cut
    json.dump(task, open(os.path.join(out, 'practice_cut3_input', 'task.json'), 'w'))
    h3 = sorted({r['mint'] for m in marks[:cut] for r in m['rows']})
    reads = []
    for m in marks[cut:]:
        rows = sorted(m['rows'], key=lambda r: r['rank'])[:100]
        reads.append({'chart': [r['mint'] for r in rows],
                      'sizes': [math.log10(int(r['market_cap_lamports'])) - 9 for r in rows[:5]]})
    json.dump({'history_mints': h3, 'reads': reads}, open(os.path.join(out, 'practice_cut3.json'), 'w'))


if __name__ == '__main__':
    main()
