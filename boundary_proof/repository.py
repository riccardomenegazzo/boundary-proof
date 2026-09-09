"""Evaluate a committed repository snapshot in disposable named volumes.

User-configured workload code executes only inside containers. Acceptance code is
restored from the immutable original snapshot in a separate verifier container.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import uuid
from .core import CHECKS, digest, summarize, validate_contract
from .runner import PROBE, base_report, observe

class Cancelled(RuntimeError): pass

class Docker:
    def __init__(self, cancel=None): self.cancel=cancel or threading.Event()
    def call(self,args,timeout=30,cleanup=False):
        start=time.monotonic()
        # Spool output to files, avoiding unbounded stdout memory from a workload.
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            process=subprocess.Popen(['docker',*args],stdout=out,stderr=err)
            timed=False
            while process.poll() is None:
                if not cleanup and self.cancel.is_set():
                    process.kill();process.wait();raise Cancelled('Evaluation cancelled')
                if os.fstat(out.fileno()).st_size+os.fstat(err.fileno()).st_size>10_000_000:
                    timed=True;process.kill();process.wait();break
                if time.monotonic()-start>timeout:
                    timed=True;process.kill();process.wait();break
                time.sleep(.05)
            def tail(f,limit):
                f.seek(0,2);f.seek(max(0,f.tell()-limit));return f.read(limit).decode('utf-8','replace')
            return {'exit_code':None if timed else process.returncode,'timeout':timed,'duration_ms':round((time.monotonic()-start)*1000),'stdout':tail(out,8000),'stderr':tail(err,4000)}
    def need(self,args):
        r=self.call(args)
        if r['exit_code']!=0: raise RuntimeError(r['stderr'] or 'Docker operation failed')
        return r['stdout'].strip()

def git(args,repo,timeout=30):
    p=subprocess.run(['git','-C',str(repo),*args],capture_output=True,timeout=timeout,check=False)
    if p.returncode: raise ValueError(p.stderr.decode(errors='replace').strip())
    return p.stdout

def source_identity(repo):
    repo=Path(repo).resolve()
    if not repo.is_dir(): raise ValueError('Repository directory does not exist')
    top=git(['rev-parse','--show-toplevel'],repo).decode().strip()
    if Path(top).resolve()!=repo: raise ValueError('Select the root of the Git repository')
    if git(['status','--porcelain','--untracked-files=no'],repo).strip(): raise ValueError('Commit tracked changes before evaluation; only HEAD is executed')
    # Submodules are not expanded by git archive; silently omitting them is misleading.
    if any(line.startswith(b'160000 ') for line in git(['ls-files','--stage'],repo).splitlines()): raise ValueError('Submodules must be vendored before snapshot evaluation')
    sha=git(['rev-parse','HEAD'],repo).decode().strip()
    archive=git(['archive','--format=tar',sha],repo,60)
    if len(archive)>100*1024*1024: raise ValueError('Repository snapshot exceeds 100 MB')
    import tarfile,io
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:
        for member in t:
            if not (member.isfile() or member.isdir()): raise ValueError('Symlinks, submodules and special files are not supported in snapshots')
            parts=Path(member.name).parts
            if '..' in parts or member.name.startswith('/') or any(x in ('.env','.ssh','.aws') or x.endswith(('.pem','.key')) for x in parts): raise ValueError('Snapshot contains a sensitive or unsupported path: '+member.name)
    return {'commit':sha,'snapshot_sha256':hashlib.sha256(archive).hexdigest(),'snapshot_bytes':len(archive)},archive

SEED='''import tarfile,os
with tarfile.open('/tmp/source.tar') as t:
    t.extractall('/workspace',filter='data')
with tarfile.open('/tmp/source.tar') as t:
    t.extractall('/reference',filter='data')
for root,dirs,files in os.walk('/workspace'):
    os.chmod(root,0o777)
    for name in files: os.chmod(os.path.join(root,name),0o666)
'''
ARTIFACTS='''import hashlib,json,os,sys
from pathlib import Path
result=[]
for name in json.loads(sys.argv[1]):
 p=Path('/workspace')/name
 if p.is_symlink() or any(x.is_symlink() for x in p.parents) or not p.is_file() or p.stat().st_size>50000000:
  raise ValueError('Missing, symbolic, or oversized artifact: '+name)
 result.append({'path':name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
print(json.dumps(result))
'''

def run(contract,repo,cancel=None,progress=None):
    validate_contract(contract)
    if contract['schema_version']!='2.0': raise ValueError('Repository evaluation requires schema 2.0')
    if contract.get('agent'):
        from .agent import configuration
        configuration()
    d=Docker(cancel);identity,archive=source_identity(repo)
    info=json.loads(d.need(['info','--format','{{json .}}']))
    image=d.need(['image','inspect',contract['image'],'--format','{{.Id}}'])
    if not image.startswith('sha256:'): raise RuntimeError('Pull the selected image before evaluating')
    report=base_report(contract,'docker');report['schema_version']='2.0';report['profiles']=contract['profiles']
    report['scope']='Committed repository workflow, independent acceptance scripts and four deterministic boundary probes. No host escape or unknown-exploit resistance claim.'
    report['environment']={'image_id':image,'docker_version':info.get('ServerVersion'),'kernel':info.get('KernelVersion'),'os':info.get('OperatingSystem'),'architecture':info.get('Architecture'),'security_options':info.get('SecurityOptions',[]),'network':'none','probe_digest':digest(PROBE)}
    report['repository']=identity;report['events']=[]
    def event(message):
        report['events'].append(message)
        if progress: progress(message)
    with tempfile.TemporaryDirectory(prefix='bp-source-') as folder:
        src=Path(folder)/'source.tar';src.write_bytes(archive)
        secret=Path(folder)/'secret';secret.write_text('BOUNDARY_PROOF_SYNTHETIC_ONLY');secret.chmod(0o444)
        for profile,settings in contract['profiles'].items():
            for iteration in range(1,contract.get('repeats',3)+1):
                if d.cancel.is_set(): report['cancelled']=True;return summarize(report)
                prefix='boundary-proof-'+uuid.uuid4().hex;workspace=prefix+'-work';reference=prefix+'-ref'
                containers=[];volumes=[]
                trial={'profile':profile,'iteration':iteration,'checks':{},'task':{'status':'inconclusive'},'steps':[],'verification':[]}
                event(f'{profile} · trial {iteration}: preparing snapshot')
                def create(name,opts):
                    containers.append(name)
                    d.need(['create','--name',name,'--label','org.boundary-proof.run='+report['id'],'--network','none','--cap-drop','ALL','--security-opt','no-new-privileges=true','--memory','512m','--cpus','1','--pids-limit','128','--tmpfs','/tmp:rw,nosuid,size=128m',*opts,image,'python','-c','import time;time.sleep(3600)'])
                    d.need(['start',name])
                try:
                    for volume in (workspace,reference):
                        volumes.append(volume);d.need(['volume','create','--label','org.boundary-proof.run='+report['id'],volume])
                    seed=prefix+'-seed';create(seed,['--user','0:0','--mount',f'type=volume,src={workspace},dst=/workspace','--mount',f'type=volume,src={reference},dst=/reference'])
                    d.need(['cp',str(src),seed+':/tmp/source.tar']);d.need(['exec',seed,'python','-c',SEED]);d.need(['rm','-f',seed]);containers.remove(seed)
                    worker=prefix+'-worker';opts=['--user',settings['user'],'--workdir','/workspace','--mount',f'type=volume,src={workspace},dst=/workspace'+('' if settings['workspace_writable'] else ',readonly'),'--mount',f'type=volume,src={reference},dst=/reference,readonly']
                    if settings['read_only']:opts+=['--read-only']
                    if settings['secret_shared']:opts+=['--mount',f'type=bind,src={secret},dst=/synthetic/secret,readonly']
                    create(worker,opts)
                    for kind in CHECKS:trial['checks'][kind]=observe(d.call(['exec',worker,'python','-c',PROBE,kind]),kind)
                    event(f'{profile} · trial {iteration}: executing workflow')
                    for cmd in contract['steps']:
                        r=d.call(['exec',worker,*cmd],contract.get('timeout_seconds',120));trial['steps'].append({'command':cmd,**r})
                        if r['exit_code']!=0:break
                    if contract.get('agent') and all(x['exit_code']==0 for x in trial['steps']):
                        from .agent import execute as agent_execute
                        event(f'{profile} · trial {iteration}: agent session')
                        trial['agent']=agent_execute(contract['agent'],lambda argv:d.call(['exec',worker,*argv],contract.get('timeout_seconds',120)),d.cancel)
                    # Stop ALL workspace writers before independent acceptance checks.
                    d.need(['rm','-f',worker]);containers.remove(worker)
                    verifier=prefix+'-verify';create(verifier,['--read-only','--user','10001:10001','--workdir','/workspace','--env','PYTHONDONTWRITEBYTECODE=1','--mount',f'type=volume,src={workspace},dst=/workspace,readonly','--mount',f'type=volume,src={reference},dst=/reference,readonly'])
                    event(f'{profile} · trial {iteration}: independent verification')
                    for cmd in contract['verify']:
                        r=d.call(['exec',verifier,cmd[0],'-I',*cmd[1:]],contract.get('timeout_seconds',120));trial['verification'].append({'command':cmd,**r})
                    artifact=d.call(['exec',verifier,'python','-c',ARTIFACTS,json.dumps(contract.get('artifacts',[]))]);trial['artifact_evidence']=artifact
                    if artifact['exit_code']==0:trial['artifacts']=json.loads(artifact['stdout'])
                    all_results=[*trial['steps'],*trial['verification'],artifact]
                    unknown=(contract.get('agent') is not None and trial.get('agent',{}).get('status')!='completed') or any(r['timeout'] or r['exit_code'] in (None,125,126,127,137) for r in all_results)
                    passed=not unknown and len(trial['steps'])==len(contract['steps']) and all(r['exit_code']==0 for r in all_results)
                    trial['task']={'status':'passed' if passed else 'inconclusive' if unknown else 'failed','artifact_verified':passed,'evidence':{'stdout':'Independent verification completed' if passed else 'Inspect workflow and verification steps','duration_ms':sum(r['duration_ms'] for r in all_results)}}
                except Cancelled:
                    trial['cancelled']=True;report['cancelled']=True
                except (RuntimeError,OSError,ValueError) as e:
                    trial['setup_error']={'stderr':str(e)}
                finally:
                    failures=[]
                    for name in reversed(containers):
                        if d.call(['rm','-f',name],cleanup=True)['exit_code']!=0:failures.append(name)
                    for name in reversed(volumes):
                        if d.call(['volume','rm',name],cleanup=True)['exit_code']!=0:failures.append(name)
                    trial['cleanup_ok']=not failures
                    if failures:trial['cleanup_error']='Failed to remove: '+', '.join(failures)
                report['runs'].append(trial);event(f'{profile} · trial {iteration}: recorded')
    return summarize(report)
