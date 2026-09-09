"""Additional real-Docker gates; explicitly invoked only in CI/integration runs."""
import copy
import json
import threading
from pathlib import Path
from boundary_proof.repository import run

base=json.loads(Path('boundary.json').read_text())
base['repeats']=1
base['profiles']={'balanced':base['profiles']['balanced']}
# Changing a mutable copy of acceptance code must not replace the original verifier.
changed=copy.deepcopy(base)
changed['steps'].append(['python','-c',"from pathlib import Path;Path('tests/acceptance.py').write_text('raise RuntimeError(\"mutable verifier must not execute\")')"])
r=run(changed,'.')
assert r['candidates']==['balanced'],r
assert all(x['cleanup_ok'] for x in r['runs'])
Path('reports/immutable-verifier.json').write_text(json.dumps(r,indent=2))
# Cancellation must unwind the current worker and both volumes.
cancelled=copy.deepcopy(base);cancelled['steps']=[['python','-c','import time;time.sleep(60)']]
event=threading.Event()
def progress(message):
    if 'executing workflow' in message:event.set()
r=run(cancelled,'.',event,progress)
assert r.get('cancelled') and not r['candidates'],r
assert all(x['cleanup_ok'] for x in r['runs']),r
Path('reports/cancelled.json').write_text(json.dumps(r,indent=2))
print('Immutable verification and cancellation cleanup passed with real Docker.')
