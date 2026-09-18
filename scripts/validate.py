"""Offline validation. Does not initialize user configuration or contact services."""
from pathlib import Path
import argparse
import compileall
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path, help='Optional local JSON evidence file (never implies authenticated E2E).')
    args = parser.parse_args()
    report = {'at': datetime.now(timezone.utc).isoformat(), 'python': sys.version, 'kind': 'offline',
              'authenticated_e2e': False, 'suites': [], 'status': 'running'}
    env = os.environ.copy()
    env['PYTHONPATH'] = os.pathsep.join([str(ROOT / 'packages'), str(ROOT / 'packages/paper_search'), env.get('PYTHONPATH', '')])
    code = 1
    try:
        for folder in ('packages', 'notebooklm/scripts', 'scripts'):
            if not compileall.compile_dir(str(ROOT / folder), quiet=1):
                report['status'] = 'compile_failed'
                return code
        for folder in ('packages/paper_search/tests', 'notebooklm/tests', 'tests'):
            if (ROOT / folder).is_dir():
                started = time.monotonic()
                result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / folder)], env=env, timeout=180,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8', errors='replace')
                print(result.stdout, end='', flush=True)
                count = re.search(r'Ran (\d+) tests?', result.stdout)
                report['suites'].append({'suite': folder, 'exit_code': result.returncode, 'tests': int(count[1]) if count else None,
                                         'elapsed_seconds': time.monotonic() - started, 'output_sha256': sha256(result.stdout.encode()).hexdigest()})
                if result.returncode:
                    report['status'] = 'failed'
                    return result.returncode
        report['status'] = 'passed'
        code = 0
        return code
    finally:
        if args.report:
            paths = [p for folder in ('packages', 'scripts', 'notebooklm/scripts', 'tests', 'notebooklm/tests') for p in (ROOT / folder).rglob('*')
                     if p.is_file() and p.suffix in ('.py', '.ps1', '.json') and '__pycache__' not in p.parts]
            paths.extend([ROOT / 'pyproject.toml', ROOT / 'requirements.lock', ROOT / '.github/workflows/ci.yml'])
            report['source_hashes'] = {str(p.relative_to(ROOT)).replace('\\', '/'): sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
