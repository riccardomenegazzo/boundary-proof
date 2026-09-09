"""Command-line interface; reports are portable and never uploaded automatically."""
import argparse
import functools
import http.server
import json
import pathlib
import sys
from .core import validate_contract, validate_report
from .runner import demo, execute

def main():
    parser = argparse.ArgumentParser(description='Verify useful work and explicit permission boundaries.')
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('run', 'demo'):
        p = sub.add_parser(name)
        p.add_argument('--contract', default='boundary.json' if name == 'run' else 'examples/contract.json')
        p.add_argument('--output', default=f'reports/{name}.json')
        if name == 'run':
            p.add_argument('--image', default='python:3.12-alpine')
            p.add_argument('--repo', default='.')
    p = sub.add_parser('validate'); p.add_argument('path')
    p = sub.add_parser('verify'); p.add_argument('path')
    p = sub.add_parser('compare'); p.add_argument('baseline'); p.add_argument('current')
    p = sub.add_parser('serve'); p.add_argument('--port', type=int, default=8080); p.add_argument('--directory', default=None); p.add_argument('--repo'); p.add_argument('--contract', default='boundary.json'); p.add_argument('--state', default=str(pathlib.Path.home()/'.boundary-proof'/'reports'))
    p = sub.add_parser('init'); p.add_argument('--output', default='boundary.json'); p.add_argument('--name', default='Repository evaluation')
    sub.add_parser('doctor')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            from .contracts import starter
            path=pathlib.Path(args.output)
            if path.exists(): raise ValueError('Contract already exists; refusing to overwrite')
            path.write_text(json.dumps(starter(args.name),indent=2)+'\n')
            print(f'Created {path}. Set workflow steps and an immutable /reference acceptance script before running.')
        elif args.command == 'doctor':
            from .runner import command
            import shutil
            result={'python':sys.version.split()[0], 'git':bool(shutil.which('git')), 'docker_cli':bool(shutil.which('docker'))}
            if result['docker_cli']: result['docker_daemon']=command(['docker','info'])['exit_code']==0
            print(json.dumps(result,indent=2))
            return 0 if result.get('docker_daemon') and result['git'] else 2
        elif args.command == 'serve':
            directory = pathlib.Path(args.directory or (pathlib.Path(__file__).parent/'dashboard' if (pathlib.Path(__file__).parent/'dashboard').exists() else 'dist')).resolve()
            if not (directory/'index.html').is_file(): raise ValueError('Dashboard directory must contain index.html')
            if args.repo:
                from .service import serve
                serve(args.repo,json.loads(pathlib.Path(args.contract).read_text()),args.state,directory,args.port)
                return 0
            handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
            print(f'Dashboard: http://127.0.0.1:{args.port} (Ctrl-C to stop)')
            with http.server.ThreadingHTTPServer(('127.0.0.1', args.port), handler) as server: server.serve_forever()
        elif args.command in ('validate', 'verify'):
            data = json.loads(pathlib.Path(args.path).read_text())
            (validate_contract if args.command == 'validate' else validate_report)(data)
            print('Valid ' + ('contract' if args.command == 'validate' else 'report; checksum is not a signature or proof of execution'))
        elif args.command == 'compare':
            a, b = [validate_report(json.loads(pathlib.Path(p).read_text())) for p in (args.baseline, args.current)]
            if a['contract_digest'] != b['contract_digest'] or a['source'] != b['source'] or a.get('environment') != b.get('environment'):
                raise ValueError('Reports are not comparable: contract, source or environment differs')
            lost = sorted(set(a['candidates'])-set(b['candidates']))
            print(json.dumps({'lost_candidates': lost, 'regression': bool(lost)}, indent=2))
            return 1 if lost else 0
        else:
            contract = validate_contract(json.loads(pathlib.Path(args.contract).read_text()))
            if args.command == 'run' and contract['schema_version']=='2.0':
                from .repository import run
                report=run(contract,args.repo,progress=lambda s: print(s,flush=True))
            else:
                report = execute(contract, args.image) if args.command == 'run' else demo(contract)
            path = pathlib.Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2)+'\n')
            print(f'{report["source"].upper()} report: {path}\nCandidates: {", ".join(report["candidates"]) or "none"}')
            return 0 if report['candidates'] else 1
    except KeyboardInterrupt: return 130
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as e:
        print(f'boundary-proof: {e}', file=sys.stderr); return 2
    return 0
