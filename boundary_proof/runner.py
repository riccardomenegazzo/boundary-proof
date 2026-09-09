"""Fixed, non-exploit Docker probes. The host controller owns verdicts and artifacts."""
import datetime
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import uuid
from .core import CHECKS, PROFILES, digest, summarize, validate_contract

# Each probe catches only expected OS permission errors. Unexpected errors are inconclusive.
PROBE = '''import errno, os, sys
kind = sys.argv[1]
try:
    if kind == 'secret_read':
        with open('/synthetic/secret') as f: value = f.read()
        sys.exit(42 if value == 'BOUNDARY_PROOF_SYNTHETIC_ONLY' else 43)
    elif kind == 'rootfs_write':
        with open('/etc/boundary-proof-canary', 'w') as f: f.write('synthetic')
        sys.exit(42)
    elif kind == 'root_identity':
        sys.exit(42 if os.geteuid() == 0 else 41)
    elif kind == 'workspace_write':
        with open('/workspace/probe', 'w') as f: f.write('ok')
        sys.exit(40)
except OSError as e:
    sys.exit(41 if e.errno in (errno.EACCES, errno.EPERM, errno.EROFS, errno.ENOENT) else 43)
'''
TASK = '''import pathlib, py_compile, zipfile
p = pathlib.Path('/workspace')
source = p / 'calculator.py'
source.write_text('def add(a, b):\\n    return a + b\\n')
py_compile.compile(str(source), cfile=str(p / 'calculator.pyc'), doraise=True)
ns = {}; exec(source.read_text(), ns)
assert ns['add'](2, 3) == 5
assert ns['add'](-2, 2) == 0
with zipfile.ZipFile(p / 'artifact.zip', 'w') as z: z.write(source, 'calculator.py')
print('2 assertions passed; artifact.zip built')
'''

def command(args, timeout=30):
    start = time.monotonic()
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
        return {"exit_code": p.returncode, "duration_ms": round((time.monotonic()-start)*1000), "stdout": p.stdout[-4000:], "stderr": p.stderr[-2000:], "timeout": False}
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "duration_ms": round((time.monotonic()-start)*1000), "stdout": "", "stderr": "Execution exceeded its time budget", "timeout": True}

def observe(result, kind):
    code = result["exit_code"]
    status = ("passed" if code == 40 else "blocked" if code == 41 else "inconclusive") if kind == "workspace_write" else ("violated" if code == 42 else "blocked" if code == 41 else "inconclusive")
    return {"status": status, "evidence": result}

def base_report(contract, source):
    return {"schema_version": "1.0", "id": str(uuid.uuid4()), "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "source": source, "contract": contract, "contract_digest": digest(contract), "profiles": PROFILES, "runs": [], "scope": "Fixed synthetic Python workflow and four deterministic probes; not an agent benchmark or host-escape assessment."}

def execute(contract, image="python:3.12-alpine"):
    validate_contract(contract)
    if not shutil.which('docker'):
        raise RuntimeError("Docker CLI unavailable. Install Docker Desktop/Engine, or use 'demo' for explicitly synthetic data.")
    info = command(['docker', 'info', '--format', '{{json .ServerVersion}}'])
    if info['exit_code'] != 0:
        raise RuntimeError("Docker daemon unavailable: " + info['stderr'])
    inspection = command(['docker', 'image', 'inspect', image, '--format', '{{.Id}}'])
    if inspection['exit_code'] != 0:
        raise RuntimeError(f"Image not available locally. Pull {image} explicitly before running.")
    image_id = inspection['stdout'].strip()
    if not image_id.startswith('sha256:'):
        raise RuntimeError("Cannot resolve immutable image identity")
    report = base_report(contract, 'docker')
    report['environment'] = {"docker_version": info['stdout'].strip(), "image_id": image_id, "requested_image": image, "network": "none", "probe_digest": digest(PROBE), "task_digest": digest(TASK)}
    for profile, settings in PROFILES.items():
        for iteration in range(1, contract.get('repeats', 3)+1):
            name = 'boundary-proof-' + uuid.uuid4().hex
            with tempfile.TemporaryDirectory(prefix='boundary-proof-') as folder:
                root = pathlib.Path(folder); workspace = root/'workspace'; workspace.mkdir(); workspace.chmod(0o777)
                secret = root/'secret'; secret.write_text('BOUNDARY_PROOF_SYNTHETIC_ONLY'); secret.chmod(0o444)
                args = ['docker', 'create', '--name', name, '--network', 'none', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges=true', '--pids-limit', '64', '--memory', '128m', '--cpus', '1', '--user', settings['user'], '--tmpfs', '/tmp:rw,noexec,nosuid,size=16m', '--mount', f'type=bind,src={workspace},dst=/workspace'+('' if settings['workspace_writable'] else ',readonly')]
                if settings['read_only']: args += ['--read-only']
                if settings['secret_shared']: args += ['--mount', f'type=bind,src={secret},dst=/synthetic/secret,readonly']
                args += [image_id, 'python', '-c', 'import time; time.sleep(300)']
                run = {"profile": profile, "iteration": iteration, "checks": {}, "task": {"status": "inconclusive"}}
                try:
                    created = command(args)
                    started = command(['docker', 'start', name]) if created['exit_code'] == 0 else created
                    if started['exit_code'] != 0:
                        run['setup_error'] = started
                    else:
                        for kind in CHECKS:
                            run['checks'][kind] = observe(command(['docker','exec',name,'python','-c',PROBE,kind]), kind)
                        result = command(['docker','exec',name,'python','-c',TASK])
                        # The controller verifies the produced artifact independently of task stdout.
                        import zipfile
                        artifact = workspace/'artifact.zip'
                        verified = False
                        if result['exit_code'] == 0 and artifact.is_file() and not artifact.is_symlink() and artifact.stat().st_size < 100000:
                            try:
                                with zipfile.ZipFile(artifact) as z:
                                    verified = z.namelist() == ['calculator.py'] and z.read('calculator.py') == b'def add(a, b):\n    return a + b\n'
                            except (OSError, zipfile.BadZipFile): pass
                        status = 'passed' if verified else 'inconclusive' if result['timeout'] or result['exit_code'] in (None, 125, 126, 127, 137) else 'failed'
                        run['task'] = {"status": status, "artifact_verified": verified, "evidence": result}
                finally:
                    cleanup = command(['docker','rm','-f', name])
                    run['cleanup_ok'] = cleanup['exit_code'] == 0
                    if not run['cleanup_ok']: run['cleanup_error'] = cleanup['stderr']
                report['runs'].append(run)
    return summarize(report)

def demo(contract):
    validate_contract(contract)
    report = base_report(contract, 'demo')
    report['environment'] = {"image_id": "synthetic — no container executed", "network": "simulated"}
    for profile in PROFILES:
        for iteration in range(1, contract.get('repeats', 3)+1):
            checks = {k: {"status": 'passed' if k == 'workspace_write' else 'blocked', "evidence": {"stdout": "Synthetic fixture; not measured", "exit_code": None, "duration_ms": 0}} for k in CHECKS}
            if profile == 'permissive':
                for k in CHECKS[1:]: checks[k]['status'] = 'violated'
            if profile == 'restricted': checks['workspace_write']['status'] = 'blocked'
            report['runs'].append({"profile": profile, "iteration": iteration, "checks": checks, "task": {"status": 'failed' if profile == 'restricted' else 'passed', "artifact_verified": False, "evidence": {"stdout": "Illustrative result only", "duration_ms": 0}}})
    return summarize(report)
