import copy
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch
from boundary_proof.core import CHECKS, digest, summarize, validate_contract, validate_report, verdict
from boundary_proof.runner import demo, observe, execute, command, TASK

CONTRACT = json.loads(pathlib.Path('examples/contract.json').read_text())

class EvaluationTests(unittest.TestCase):
    def setUp(self): self.report = demo(copy.deepcopy(CONTRACT))
    def test_profile_frontier(self):
        self.assertEqual(self.report['candidates'], ['balanced'])
        self.assertEqual(self.report['summary'], {'candidate':3,'violated':3,'unusable':3,'inconclusive':0})
    def test_missing_check_is_not_pass(self):
        run = self.report['runs'][-1]; del run['checks']['secret_read']
        self.assertEqual(verdict(run), 'inconclusive')
    def test_violation_survives_timeout(self):
        run = self.report['runs'][0]; run['checks']['rootfs_write']['status']='inconclusive'
        self.assertEqual(verdict(run), 'violated')
    def test_partial_repetitions_do_not_qualify(self):
        self.report['runs'].pop(); self.assertEqual(summarize(self.report)['candidates'], [])
    def test_failed_task_not_safe_candidate(self):
        run=self.report['runs'][-1];run['task']['status']='failed'
        self.assertEqual(verdict(run),'unusable')
    def test_tamper_detected(self):
        self.report['contract']['name']='Modified'
        with self.assertRaises(ValueError): validate_report(self.report)
    def test_forged_summary_rejected_even_with_new_checksum(self):
        self.report['candidates']=['permissive']
        self.report['integrity']['digest']=digest({k:v for k,v in self.report.items() if k!='integrity'})
        with self.assertRaises(ValueError): validate_report(self.report)
    def test_duplicates_rejected(self):
        self.report['runs'].append(copy.deepcopy(self.report['runs'][0]))
        with self.assertRaises(ValueError): validate_report(self.report)
    def test_valid_report(self): validate_report(self.report)
    def test_repeats_strict(self):
        for value in [True,0,21,'3']:
            c={**CONTRACT,'repeats':value}
            with self.assertRaises(ValueError): validate_contract(c)
    def test_unknown_workflow_rejected(self):
        with self.assertRaises(ValueError): validate_contract({**CONTRACT,'workflow':'shell'})
    def test_probe_exit_codes(self):
        for code in [None,1,125,126,127,137]:
            self.assertEqual(observe({'exit_code':code},'secret_read')['status'],'inconclusive')
        self.assertEqual(observe({'exit_code':42},'secret_read')['status'],'violated')
        self.assertEqual(observe({'exit_code':41},'secret_read')['status'],'blocked')
    def test_no_docker_is_explicit(self):
        with patch('shutil.which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'Docker CLI unavailable'): execute(CONTRACT)
    def test_timeout(self):
        import sys
        self.assertTrue(command([sys.executable,'-c','import time;time.sleep(1)'],timeout=.01)['timeout'])
    def test_fixture_produces_expected_artifact(self):
        import zipfile
        with tempfile.TemporaryDirectory() as d:
            exec(TASK.replace("'/workspace'",repr(d)))
            self.assertFalse(any(p.is_dir() for p in pathlib.Path(d).iterdir()), 'Avoid foreign-owned nested directories on host bind mounts')
            with zipfile.ZipFile(pathlib.Path(d)/'artifact.zip') as z:
                self.assertEqual(z.read('calculator.py'),b'def add(a, b):\n    return a + b\n')

if __name__=='__main__': unittest.main()
