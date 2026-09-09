import copy
import json
import pathlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from boundary_proof.contracts import starter, validate
from boundary_proof.repository import source_identity, Docker, Cancelled
from boundary_proof.core import summarize, validate_report
from boundary_proof.runner import demo

class ContractTests(unittest.TestCase):
    def test_starter(self):validate(starter())
    def test_arbitrary_host_options_rejected(self):
        c=starter();c['mounts']=['/'];self.assertRaises(ValueError,validate,c)
    def test_mutable_verifier_rejected(self):
        c=starter();c['verify']=[['python','/workspace/check.py']];self.assertRaises(ValueError,validate,c)
    def test_profile_types(self):
        c=copy.deepcopy(starter());c['profiles']['balanced']['read_only']='true';self.assertRaises(ValueError,validate,c)
    def test_artifact_traversal_rejected(self):
        c=starter();c['artifacts']=['../outside'];self.assertRaises(ValueError,validate,c)
    def test_unbounded_trials_rejected(self):
        c=starter();c['repeats']=21;self.assertRaises(ValueError,validate,c)
    def test_custom_profiles_frontier(self):
        from boundary_proof.runner import base_report
        c=copy.deepcopy(starter());c['profiles']={'one':c['profiles']['balanced'],'same':c['profiles']['balanced']};c['repeats']=1
        r=base_report(c,'docker');r['schema_version']='2.0';r['profiles']=c['profiles']
        from boundary_proof.core import CHECKS
        for name in c['profiles']:
            r['runs'].append({'profile':name,'iteration':1,'checks':{k:{'status':'passed' if k=='workspace_write' else 'blocked'} for k in CHECKS},'task':{'status':'passed'}})
        summarize(r);self.assertEqual(r['candidates'],['one','same']);validate_report(r)
    def test_cleanup_failure_never_candidate(self):
        from boundary_proof.core import verdict
        r={'cleanup_ok':False,'task':{'status':'passed'}}
        self.assertEqual(verdict(r),'inconclusive')

class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
        self.git('init','-q');self.git('config','user.name','Test');self.git('config','user.email','test@example.invalid')
        (self.root/'app.py').write_text('print("hello")');self.commit()
    def tearDown(self):self.tmp.cleanup()
    def git(self,*args):return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.DEVNULL)
    def commit(self):self.git('add','.');self.git('commit','-qm','snapshot')
    def test_snapshot_ignores_untracked_files(self):
        first,data=source_identity(self.root);(self.root/'untracked').write_text('not included')
        second,other=source_identity(self.root);self.assertEqual(first,second);self.assertEqual(data,other)
    def test_dirty_tracked_files_rejected(self):
        (self.root/'app.py').write_text('different');self.assertRaises(ValueError,source_identity,self.root)
    def test_symlinks_rejected(self):
        (self.root/'link').symlink_to('app.py');self.commit();self.assertRaises(ValueError,source_identity,self.root)
    def test_sensitive_paths_rejected(self):
        (self.root/'.env').write_text('SYNTHETIC=true');self.commit();self.assertRaises(ValueError,source_identity,self.root)

if __name__=='__main__':unittest.main()
