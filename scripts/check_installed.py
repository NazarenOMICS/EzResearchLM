"""Exercise installed resources and the offline CLI outside the checkout.

Run with the candidate environment's python -I. No provider or login calls.
"""
import argparse
from contextlib import redirect_stdout
from hashlib import sha256
from importlib import metadata, resources
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    import ez
    import search_topic
    from ez.cli import main as cli
    from ez.paths import runtime_root
    from ez.state import read_json

    prefix = Path(sys.prefix).resolve()
    assert Path(ez.__file__).resolve().is_relative_to(prefix), 'EZ did not load from candidate environment'
    assert Path(search_topic.__file__).resolve().is_relative_to(prefix), 'Search did not load from candidate environment'
    for schema in ('research-contract', 'qa-review', 'run-state', 'source-manifest'):
        json.loads(resources.files('ez').joinpath('schemas', schema + '.json').read_text(encoding='utf-8'))
    guide = runtime_root() / 'docs/ez-host-operator.md'
    assert guide.is_file(), 'Installed host guide is missing'
    assert (runtime_root() / 'docs/ez-user-guide.md').is_file(), 'Installed user guide is missing'
    assert (runtime_root() / 'SETUP.md').is_file(), 'Installed setup reference is missing'
    assert (runtime_root() / 'scripts/run_external.py').is_file(), 'Installed supervisor is missing'

    def invoke(argv, expected):
        output = StringIO()
        with redirect_stdout(output):
            code = cli(argv)
        assert code == expected, output.getvalue()
        return json.loads(output.getvalue())

    with tempfile.TemporaryDirectory(prefix='ez-installed-') as temp:
        root = Path(temp) / 'runs'
        flags = ['--root', str(root), '--json']
        assert invoke(flags, 0)['kind'] == 'welcome'
        user_guide = invoke(['--guide', *flags], 0)
        assert '## Primer uso' in user_guide['text']
        assert not root.exists(), 'Welcome/guide must not create research data'
        invoke(['context', '--project', 'smoke', '--set', 'discipline', 'Prueba técnica', *flags], 0)
        run = invoke(['research', 'Pregunta de instalación', '--project', 'smoke', '--plan-only', *flags], 0)
        contract = read_json(Path(run['path']) / 'research-contract.json')
        assert contract['context']['discipline'] == 'Prueba técnica'
        waiting = invoke(['continue', run['path'], *flags], 2)
        assert waiting['legacy_signals'] == ['NEEDS_PLAN']
        assert invoke(['doctor', run['path'], *flags], 0)['healthy']

    report = {'status': 'passed', 'version': metadata.version('ezresearchlm'), 'python': sys.version,
              'isolated_python': bool(sys.flags.isolated), 'installed_module': str(Path(ez.__file__).resolve()),
              'host_guide_sha256': sha256(guide.read_bytes()).hexdigest(),
              'checks': ['installed_imports', 'four_schemas', 'host_guide', 'welcome', 'offline_user_guide', 'supervisor', 'context', 'research', 'continue_needs_plan', 'doctor'],
              'authenticated_e2e': False, 'clean_windows_machine': False}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
