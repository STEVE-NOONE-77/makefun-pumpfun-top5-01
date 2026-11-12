"""Edge cases: every one must still write a valid forecast. Usage: python3 dev/edge_test.py <kit input dir> <tmp dir>"""
import json
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score import validate  # noqa: E402

kit, tmp = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lines = open(os.path.join(kit, 'history.ndjson')).read().splitlines()
last = json.loads(lines[-1])
cases = {
    'empty_history': [],
    'one_empty_mark': [lines[0]],
    'garbage_line': lines[:3] + ['{not json'] + lines[3:],
    'missing_fields': [json.dumps(dict(last, rows=[{k: v for k, v in r.items() if k not in ('created_at', 'rank')} for r in last['rows']]))],
    'three_coins': [json.dumps(dict(last, rows=last['rows'][:3]))],
    'full': lines,
}
for name, hist in cases.items():
    d = os.path.join(tmp, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(d, 'in'))
    shutil.copy(os.path.join(kit, 'task.json'), os.path.join(d, 'in'))
    open(os.path.join(d, 'in', 'history.ndjson'), 'w').write('\n'.join(hist) + ('\n' if hist else ''))
    env = dict(os.environ, MAKEFUN_INPUT_DIR=os.path.join(d, 'in'), MAKEFUN_OUTPUT_DIR=os.path.join(d, 'out'))
    r = subprocess.run([sys.executable, os.path.join(HERE, 'main.py')], env=env, capture_output=True, text=True)
    fc = json.load(open(os.path.join(d, 'out', 'forecast.json')))
    v = validate(fc)
    print('%-16s rc %d rows %s fallback %s' % (name, r.returncode, v['rows'], 'yes' if r.stderr else 'no'), r.stderr.strip()[:80])
