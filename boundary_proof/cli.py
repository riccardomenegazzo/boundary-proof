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
        p.add_argument('--contract', default='examples/contract.json')
        p.add_argument('--output', default=f'reports/{name}.json')
        if name == 'run': p.add_argument('--image', default='python:3.12-alpine')
    p = sub.add_parser('validate'); p.add_argument('path')
    p = sub.add_parser('verify'); p.add_argument('path')
    p = sub.add_parser('compare'); p.add_argument('baseline'); p.add_argument('current')
    p = sub.add_parser('serve'); p.add_argument('--port', type=int, default=8080); p.add_argument('--directory', default='dist')
    args = parser.parse_args()
    try:
        if args.command == 'serve':
            directory = pathlib.Path(args.directory).resolve()
            if not (directory/'index.html').is_file(): raise ValueError('Dashboard directory must contain index.html')
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
            report = execute(contract, args.image) if args.command == 'run' else demo(contract)
            path = pathlib.Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2)+'\n')
            print(f'{report["source"].upper()} report: {path}\nCandidates: {", ".join(report["candidates"]) or "none"}')
            return 0 if report['candidates'] else 1
    except KeyboardInterrupt: return 130
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as e:
        print(f'boundary-proof: {e}', file=sys.stderr); return 2
    return 0
