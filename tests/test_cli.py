from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.setup import prepare
from ez.state import read_json


class CliTests(unittest.TestCase):
    def invoke(self, args):
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            result = main(args)
        return result, json.loads(output.getvalue())

    def test_context_is_preserved_in_contract_and_machine_output_is_single_json(self):
        with tempfile.TemporaryDirectory() as folder:
            root = str(Path(folder) / 'runs')
            code, context = self.invoke(['--root', root, 'context', '--project', 'thesis', '--set', 'discipline', 'Biología', '--json'])
            self.assertEqual(code, 0)
            code, result = self.invoke(['research', 'Pregunta natural', '--project', 'thesis', '--plan-only', '--root', root, '--json'])
            self.assertEqual(code, 0)
            contract = read_json(Path(result['path']) / 'research-contract.json')
            self.assertEqual(contract['context']['discipline'], 'Biología')
            self.assertEqual(contract['operator']['backend'], 'host_agent')
            self.assertEqual(contract['plan']['status'], 'needs_host_plan')
            code, waiting = self.invoke(['continue', result['path'], '--json'])
            self.assertEqual(code, 2)
            self.assertEqual(waiting['legacy_signals'], ['NEEDS_PLAN'])
            code, context = self.invoke(['context', '--project', 'thesis', '--root', root, '--json'])
            self.assertEqual(code, 0)
            self.assertEqual(context['research_history'][0]['run_id'], result['run_id'])
            self.assertTrue(context['research_history'][0]['evidence_must_be_rechecked'])

    def test_pdf_import_keeps_origin_and_requires_identity_decision(self):
        from PyPDF2 import PdfWriter
        from ez.cli import create_run
        from ez.contracts import draft
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            contract = draft('Pregunta', {})
            contract['source_policies'] = [{'source_id': 'manual1', 'policy': 'hard_block', 'scope_ids': ['sq1'],
                                           'rationale': 'Fuente solicitada', 'locked_by_user': True, 'title': 'Fuente sintética'}]
            folder, _ = create_run(root / 'runs', 'Pregunta', {}, contract)
            pdf = root / 'user.pdf'; writer = PdfWriter(); writer.add_blank_page(width=72, height=72)
            with pdf.open('wb') as stream:
                writer.write(stream)
            code, status = self.invoke(['rescue', str(folder), '--source', 'manual1', '--import', str(pdf),
                                   '--origin-provider', 'institution', '--origin', 'Biblioteca del usuario', '--source-version', 'accepted', '--json'])
            self.assertEqual(code, 0)
            self.assertEqual(status['execution']['status'], 'waiting_user')
            self.assertEqual(status['integrity']['status'], 'pending')
            self.assertEqual(status['phase'], 'acquire')
            source = read_json(folder / 'sources.json')[0]
            self.assertEqual(source['identity_status'], 'needs_review')
            self.assertEqual(source['provenance']['source_version'], 'accepted')
            self.assertEqual(source['provenance']['origin_provider'], 'institution')
            code, _ = self.invoke(['rescue', str(folder), '--source', 'manual1', '--confirm-identity', '--json'])
            self.assertEqual(code, 0)
            self.assertEqual(read_json(folder / 'sources.json')[0]['identity_status'], 'verified')

    def test_setup_check_is_read_only_and_optional_recall_does_not_gate_qa(self):
        from ez.process import Result
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'runs'
            with patch('ez.setup.executable', side_effect=lambda name: name if name == 'notebooklm' else None), patch('ez.setup.run', return_value=Result(0, '{"notebooks": []}', '')):
                checks = prepare(root, check=True)
                self.assertTrue(checks['can_notebook_qa'])
                self.assertFalse(checks['can_recall'])
                self.assertEqual(list(Path(folder).iterdir()), [])
                prepare(root)
                config = root.parent / 'ez-config.json'
                before = config.read_bytes()
                prepare(root)
                self.assertEqual(config.read_bytes(), before)

    def test_setup_missing_notebooklm_has_action_without_false_readiness(self):
        with tempfile.TemporaryDirectory() as folder, patch('ez.setup.executable', return_value=None):
            checks = prepare(Path(folder) / 'runs', check=True)
            self.assertTrue(checks['can_plan'])
            self.assertFalse(checks['can_notebook_qa'])
            self.assertIn('--install-notebooklm', checks['next_action'])

    def test_setup_rejects_success_exit_with_unknown_notebook_envelope(self):
        from ez.process import Result
        for payload in ('{}', '<html>login</html>', '{"notebooks": [null]}', '{"notebooks": [{"id": "a"}, {"id": "a"}]}'):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as folder:
                with patch('ez.setup.executable', return_value='notebooklm'), patch('ez.setup.run', return_value=Result(0, payload, '')):
                    checks = prepare(Path(folder) / 'runs', check=True)
                self.assertFalse(checks['can_notebook_qa'])
                self.assertEqual(checks['notebooklm_failure'], 'invalid_notebooklm_output')
