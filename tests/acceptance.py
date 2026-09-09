"""Immutable acceptance program used to evaluate this repository itself."""
import json
from pathlib import Path
import sys
import zipfile
sys.path.insert(0,'/workspace')
from boundary_proof.core import validate_report, verdict
report=json.loads(Path('/workspace/tests/fixtures/legacy-report.json').read_text())
validate_report(report)
assert report['candidates']==['balanced']
case=report['runs'][-1]
case['checks'].pop('secret_read')
assert verdict(case)=='inconclusive', 'Missing evidence must never pass'
with zipfile.ZipFile('/workspace/boundary-proof-source.zip') as package:
    assert 'core.py' in package.namelist()
    assert package.read('core.py')==Path('/workspace/boundary_proof/core.py').read_bytes()
print('Independent acceptance passed: report validation, uncertainty handling, source artifact')
