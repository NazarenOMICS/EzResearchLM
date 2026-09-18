import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SHELL = shutil.which('powershell.exe') or shutil.which('pwsh')
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(SHELL, 'PowerShell is not installed on this host')
class PowerShellGateTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Legacy answer wrapper requires Windows')
    def test_answer_recall_reaches_bounded_runner_before_corpus_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            scripts = path / 'scripts'
            scripts.mkdir()
            wrapper = scripts / 'run_hermes_answer.ps1'
            shutil.copyfile(ROOT / 'scripts/run_hermes_answer.ps1', wrapper)
            # Substitute the external boundary, not the wrapper's initialization.
            # Empty recall must still reach the runner with its explicit deadline.
            (scripts / 'run_external.py').write_text(
                'import json, os, pathlib, sys\n'
                'pathlib.Path(os.environ["EZ_TEST_CALL"]).write_text(json.dumps(sys.argv[1:]))\n',
                encoding='utf-8')
            (scripts / 'qmd.ps1').write_text('throw "External calls belong to the runner"\n')
            receipt = path / 'recall.json'
            env = {**os.environ, 'EZRESEARCH_ROOT': str(path), 'EZRESEARCH_VAULT': str(path),
                   'EZRESEARCH_PYTHON': sys.executable, 'EZ_TEST_CALL': str(receipt),
                   'PATH': str(scripts) + os.pathsep + os.environ.get('PATH', '')}
            result = subprocess.run([SHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                     str(wrapper), '-Question', 'Synthetic recall check', '-Slug', 'recall-test'],
                                    env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn('NEEDS_CORPUS', result.stdout)
            self.assertEqual(json.loads(receipt.read_text()),
                             ['--timeout', '120', '--', 'qmd', 'search', 'Synthetic recall check', '-c', 'notes', '-n', '8'])

    def test_real_powershell_switch_and_inheritance_matrix(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / 'legacy.json').write_text(json.dumps({'stop_if_missing_must_have': False}))
            (path / 'new.json').write_text(json.dumps({'must_have_gate_version': 2, 'stop_if_missing_must_have': False}))
            script = path / 'check.ps1'
            helper = str(ROOT / 'scripts/resolve_must_have_gate.ps1').replace("'", "''")
            script.write_text(". '" + helper + "'\n" + '''$values = @(
    (Resolve-EzMustHaveGate -ExplicitlySet $false -RequestedValue $false),
    (Resolve-EzMustHaveGate -ExplicitlySet $true -RequestedValue $true),
    (Resolve-EzMustHaveGate -ExplicitlySet $true -RequestedValue $false -StatePath "$PSScriptRoot/legacy.json"),
    (Resolve-EzMustHaveGate -ExplicitlySet $false -RequestedValue $false -StatePath "$PSScriptRoot/legacy.json"),
    (Resolve-EzMustHaveGate -ExplicitlySet $false -RequestedValue $true -StatePath "$PSScriptRoot/new.json")
)
ConvertTo-Json -InputObject $values -Compress
''', encoding='utf-8')
            result = subprocess.run([SHELL, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), [False, True, False, True, False])
