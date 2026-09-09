"""Authenticated loopback service for one explicitly selected repository."""
import hmac
import json
import re
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from .core import validate_contract, validate_report
from .repository import run

class Workspace:
    def __init__(self,repo,contract,state):
        self.repo=Path(repo).resolve();self.contract=validate_contract(contract)
        if contract['schema_version']!='2.0':raise ValueError('Local workspace requires a repository contract (2.0)')
        self.state=Path(state).resolve();self.state.mkdir(parents=True,exist_ok=True)
        self.token=secrets.token_urlsafe(32);self.lock=threading.Lock();self.job=None;self.cancel=threading.Event()
    def reports(self):
        result=[]
        for p in self.state.glob('*.json'):
            try:
                r=validate_report(json.loads(p.read_text()));result.append({'id':r['id'],'created_at':r['created_at'],'name':r['contract']['name'],'candidates':r['candidates'],'summary':r['summary'],'source':r['source']})
            except (ValueError,KeyError,TypeError,OSError):continue
        return sorted(result,key=lambda r:r['created_at'],reverse=True)
    def start(self,contract):
        validate_contract(contract)
        if contract['schema_version']!='2.0':raise ValueError('Use a repository contract')
        with self.lock:
            if self.job and self.job['status']=='running':raise ValueError('An evaluation is already running')
            self.cancel=threading.Event();self.job={'id':str(uuid.uuid4()),'status':'running','events':[]};self.contract=contract
        def event(msg):
            with self.lock:self.job['events'].append(msg)
        def worker():
            try:
                report=run(contract,self.repo,self.cancel,event)
                path=self.state/(report['id']+'.json');tmp=path.with_suffix('.tmp')
                tmp.write_text(json.dumps(report,indent=2));tmp.replace(path)
                with self.lock:self.job.update(status='cancelled' if report.get('cancelled') else 'completed',report_id=report['id'])
            except Exception as e:
                with self.lock:self.job.update(status='failed',error=str(e))
        threading.Thread(target=worker,daemon=True).start()
        return self.job

def handler(workspace,directory):
    directory=Path(directory).resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def respond(self,status,data,kind='application/json'):
            payload=json.dumps(data).encode() if kind=='application/json' else data
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(payload)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'");self.end_headers();self.wfile.write(payload)
        def host_ok(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
        def authorized(self):
            token=self.headers.get('X-Boundary-Token','')
            origin=self.headers.get('Origin')
            return self.host_ok() and hmac.compare_digest(token,workspace.token) and (origin is None or origin in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'))
        def do_GET(self):
            if not self.host_ok():return self.respond(403,{'error':'Invalid Host'})
            path=urlparse(self.path).path
            if path=='/api/health':return self.respond(200,{'mode':'local','version':'0.2.0'})
            if path.startswith('/api/'):
                if not self.authorized():return self.respond(401,{'error':'Open the session URL printed by boundary-proof serve'})
                if path=='/api/workspace':return self.respond(200,{'repository':str(workspace.repo),'contract':workspace.contract,'reports':workspace.reports()})
                if path=='/api/job':
                    with workspace.lock:return self.respond(200,workspace.job)
                if re.fullmatch(r'/api/reports/[0-9a-f-]{36}',path):
                    try:return self.respond(200,json.loads((workspace.state/(path.rsplit('/',1)[1]+'.json')).read_text()))
                    except (OSError,ValueError):return self.respond(404,{'error':'Report not found'})
                return self.respond(404,{'error':'Unknown endpoint'})
            allowed={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path not in allowed:return self.respond(404,{'error':'Not found'})
            file=directory/allowed[path]
            kind={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}[file.suffix]
            try:return self.respond(200,file.read_bytes(),kind)
            except OSError:return self.respond(404,{'error':'Dashboard assets are missing'})
        def do_POST(self):
            if not self.authorized():return self.respond(403,{'error':'Session token and same origin required'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=128000:raise ValueError('Invalid request size')
                if self.headers.get('Content-Type')!='application/json':raise ValueError('Use application/json')
                body=json.loads(self.rfile.read(size));path=urlparse(self.path).path
                if path=='/api/run':return self.respond(202,workspace.start(body['contract']))
                if path=='/api/cancel':workspace.cancel.set();return self.respond(200,{'cancel_requested':True})
                if path=='/api/validate':validate_contract(body['contract']);return self.respond(200,{'valid':True})
                return self.respond(404,{'error':'Unknown endpoint'})
            except (ValueError,KeyError,TypeError) as e:return self.respond(400,{'error':str(e)})
    return Handler

def serve(repo,contract,state,directory,port):
    w=Workspace(repo,contract,state)
    with ThreadingHTTPServer(('127.0.0.1',port),handler(w,directory)) as server:
        print(f'Boundary Proof workspace: http://127.0.0.1:{server.server_port}/#session={w.token}',flush=True)
        print('Only the selected repository can be evaluated. Ctrl-C cancels active work.',flush=True)
        try:server.serve_forever()
        finally:
            w.cancel.set()
            # Allow the active evaluation to remove only its own resources.
            import time
            deadline=time.monotonic()+60
            while w.job and w.job['status']=='running' and time.monotonic()<deadline:time.sleep(.1)
