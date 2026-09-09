import http.client
import json
import pathlib
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from boundary_proof.contracts import starter
from boundary_proof.service import Workspace,handler

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.w=Workspace('.',starter(),self.tmp.name)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.w,'dist'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.tmp.cleanup()
    def request(self,path,headers=None,body=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        conn.request('POST' if body is not None else 'GET',path,body,headers or {})
        r=conn.getresponse();data=r.read();conn.close();return r.status,data
    def test_private_workspace_requires_token(self):self.assertEqual(self.request('/api/workspace')[0],401)
    def test_authenticated_workspace(self):
        status,data=self.request('/api/workspace',{'X-Boundary-Token':self.w.token});self.assertEqual(status,200);self.assertIn('contract',json.loads(data))
    def test_cross_origin_blocked(self):
        status,_=self.request('/api/validate',{'X-Boundary-Token':self.w.token,'Origin':'https://untrusted.invalid','Content-Type':'application/json'},json.dumps({'contract':starter()}));self.assertEqual(status,403)
    def test_dns_rebinding_host_blocked(self):self.assertEqual(self.request('/api/health',{'Host':'attacker.invalid'})[0],403)
    def test_path_traversal_blocked(self):self.assertEqual(self.request('/../pyproject.toml')[0],404)
    def test_contract_validation(self):
        status,_=self.request('/api/validate',{'X-Boundary-Token':self.w.token,'Content-Type':'application/json'},json.dumps({'contract':starter()}));self.assertEqual(status,200)
    def test_no_demo_default(self):
        status,data=self.request('/');self.assertEqual(status,200);self.assertIn(b'No synthetic results',data)

if __name__=='__main__':unittest.main()
