import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from ez.contracts import ContractError, draft, validate, require_ready
from ez.legacy import inspect_run
from ez.policies import evaluate, legacy_gate
from ez.state import Store, lock, atomic_json
from ez.process import run
from ez.pdf import validate_pdf


class CoreTests(unittest.TestCase):
    def test_contract_rejects_future_and_unknown_scope(self):
        contract = draft('Pregunta', {})
        validate(contract)
        contract['schema_version'] = '3.0'
        with self.assertRaises(ContractError):
            validate(contract)
        contract['schema_version'] = '2.0'
        contract['plan']['queries'] = [{'id': 'q', 'provider': 'crossref', 'text': 'x', 'scope_ids': ['wrong']}]
        with self.assertRaises(ContractError):
            validate(contract)

    def test_draft_does_not_pretend_host_planned_it(self):
        with self.assertRaises(ContractError):
            require_ready(draft('Pregunta', {}))

    def test_policy_scope_and_integrity(self):
        contract = draft('Pregunta', {})
        contract['scope'].append({'id': 'sq2', 'question': 'Otra', 'central': True})
        contract['source_policies'] = [{'source_id': 'missing', 'policy': 'hard_block', 'scope_ids': ['sq2']}]
        sources = [{'source_id': 'ok', 'notebook_status': 'ready', 'identity_status': 'verified', 'validation_status': 'valid'}]
        result = evaluate(contract, sources, {'sq1': 'sufficient', 'sq2': 'sufficient'}, 'pass')
        self.assertEqual(result['answer'], {'status': 'partial', 'scope_ids': ['sq1']})
        self.assertEqual(evaluate(contract, sources, {'sq1': 'sufficient'}, 'unknown')['answer']['status'], 'unavailable')
        contract['source_policies'][0]['policy'] = 'historical'
        self.assertEqual(evaluate(contract, sources, {'sq1': 'sufficient', 'sq2': 'sufficient'}, 'pass')['answer']['status'], 'complete')

    def test_legacy_switch_matrix(self):
        self.assertFalse(legacy_gate())
        self.assertTrue(legacy_gate(True))
        self.assertFalse(legacy_gate(False, continuing=True))
        self.assertTrue(legacy_gate(continuing=True))
        self.assertFalse(legacy_gate(continuing=True, persisted=False))

    def test_all_five_policies_apply_only_to_their_scopes(self):
        contract = draft('Pregunta', {})
        contract['scope'].append({'id': 'sq2', 'question': 'Otra', 'central': True})
        sources = [{'source_id': 'available', 'notebook_status': 'ready', 'identity_status': 'verified', 'validation_status': 'valid'}]
        for policy, expected in [('hard_block', 'partial'), ('soft_block', 'complete'), ('contextual', 'partial'),
                                 ('historical', 'complete'), ('optional', 'complete')]:
            with self.subTest(policy=policy):
                contract['source_policies'] = [{'source_id': 'missing', 'policy': policy, 'scope_ids': ['sq2']}]
                result = evaluate(contract, sources, {'sq1': 'sufficient', 'sq2': 'sufficient'}, 'pass')
                self.assertEqual(result['answer']['status'], expected)
                self.assertIn('sq1', result['answer']['scope_ids'])
                if policy == 'contextual':
                    self.assertIn('NEEDS_SOURCE_REVIEW', result['legacy_signals'])
        contract['source_policies'][0].update(policy='contextual', effective_policy='soft_block')
        result = evaluate(contract, sources, {'sq1': 'sufficient', 'sq2': 'sufficient'}, 'pass')
        self.assertEqual(result['answer']['status'], 'complete')
        self.assertIn('NEEDS_SOURCE_RESCUE', result['legacy_signals'])

    def test_journal_recovers_torn_tail_and_projection(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            with lock(folder):
                store.update({'phase': 'plan'})
                with store.journal.open('ab') as stream:
                    stream.write(b'{"interrupted":')
                self.assertEqual(store.state()['phase'], 'plan')
                store.update({'phase': 'discover'})
            self.assertEqual(len(store.events()), 2)
            self.assertTrue(list(Path(folder).glob('interrupted-*.bin')))
            (Path(folder) / 'run-state.json').write_text('broken')
            self.assertEqual(store.state()['phase'], 'discover')
            with lock(folder):
                with self.assertRaises(ContractError):
                    with lock(folder):
                        pass

    def test_journal_tampering_is_not_repaired_silently(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            with lock(folder):
                store.update({'phase': 'plan'})
            store.journal.write_text(store.journal.read_text().replace('plan', 'done'))
            with self.assertRaises(ContractError):
                store.state()

    def test_legacy_false_retains_historical_gate_and_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            atomic_json(Path(folder) / 'run-state.json', {'stop_if_missing_must_have': False, 'vault_slug': 'old'})
            atomic_json(Path(folder) / 'questions-x.json', {'vault_slug': 'new'})
            result = inspect_run(folder)
            self.assertEqual(result['legacy_effective_gate'], 'block_all_required')
            self.assertEqual(result['conflicts'][0]['field'], 'vault_slug')

    def test_process_deadline_and_output_limit(self):
        result = run([sys.executable, '-c', 'import time; time.sleep(20)'], .2)
        self.assertEqual(result.reason, 'deadline_exceeded')
        result = run([sys.executable, '-c', 'print("x" * 20000)'], 5, max_output_bytes=1000)
        self.assertEqual(result.reason, 'output_limit')

    def test_process_descendants_die_on_deadline_and_normal_parent_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            for keep_parent_alive in (False, True):
                marker = Path(folder) / str(keep_parent_alive)
                child = 'import time; from pathlib import Path; time.sleep(1); Path(' + repr(str(marker)) + ').write_text("orphan")'
                parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); '
                if keep_parent_alive:
                    parent += 'time.sleep(30)'
                result = run([sys.executable, '-c', parent], .5 if keep_parent_alive else 5)
                self.assertEqual(result.reason, 'deadline_exceeded' if keep_parent_alive else '')
                time.sleep(1.2)
                self.assertFalse(marker.exists(), 'A descendant outlived its operation')

    def test_pdf_valid_and_fake(self):
        from PyPDF2 import PdfWriter
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'x.pdf'
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            with path.open('wb') as stream:
                writer.write(stream)
            self.assertEqual(validate_pdf(path)['status'], 'valid')
            path.write_bytes(b'%PDF-1.4\n' + b'x' * 2048)
            self.assertEqual(validate_pdf(path)['reason'], 'corrupt_pdf')
