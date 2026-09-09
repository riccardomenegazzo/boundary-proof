import threading
import unittest
from unittest.mock import patch
from boundary_proof.agent import execute,configuration

class AgentTests(unittest.TestCase):
    def test_credentials_required_for_remote(self):
        with patch.dict('os.environ',{'BOUNDARY_PROOF_API_BASE':'https://provider.invalid/v1','BOUNDARY_PROOF_API_KEY':''}):self.assertRaises(ValueError,configuration)
    def test_insecure_remote_rejected(self):
        with patch.dict('os.environ',{'BOUNDARY_PROOF_API_BASE':'http://provider.invalid/v1'}):self.assertRaises(ValueError,configuration)
    def test_tool_executes_only_through_container_executor(self):
        responses=[{'choices':[{'message':{'tool_calls':[{'id':'1','type':'function','function':{'name':'container_command','arguments':'{"argv":["python","--version"]}'}}]}}]},{'choices':[{'message':{'content':'done'}}]}]
        commands=[]
        with patch('boundary_proof.agent.configuration',return_value=('http://127.0.0.1/v1','')),patch('boundary_proof.agent.request',side_effect=responses):
            r=execute({'model':'protocol-fixture','instruction':'check'},lambda argv:commands.append(argv) or {'timeout':False,'exit_code':0},threading.Event())
        self.assertEqual(commands,[['python','--version']]);self.assertEqual(r['status'],'completed')
    def test_malformed_command_is_inconclusive(self):
        bad={'choices':[{'message':{'tool_calls':[{'id':'1','function':{'name':'container_command','arguments':'{"argv":"rm"}'}}]}}]}
        with patch('boundary_proof.agent.configuration',return_value=('http://127.0.0.1/v1','')),patch('boundary_proof.agent.request',return_value=bad):
            r=execute({'model':'fixture','instruction':'test'},lambda _:self.fail('Must not execute'),threading.Event())
        self.assertEqual(r['status'],'inconclusive')
    def test_turn_budget_is_inconclusive(self):
        response={'choices':[{'message':{'tool_calls':[{'id':'1','function':{'name':'container_command','arguments':'{"argv":["true"]}'}}]}}]}
        with patch('boundary_proof.agent.configuration',return_value=('http://127.0.0.1/v1','')),patch('boundary_proof.agent.request',return_value=response):
            r=execute({'model':'fixture','instruction':'test','max_turns':1},lambda _:{'exit_code':0,'timeout':False},threading.Event())
        self.assertEqual(r['status'],'inconclusive')
