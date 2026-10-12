"""Evidence must retain scope, attribution and integrity through the entire offline flow."""
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from ez.state import atomic_json, read_json, Store, lock


class EvidenceFlowTests(unittest.TestCase):
    def test_context_survives_delivery_memory_draft_status_and_mcp(self):
        import test_v6_rules
        from ez.audit import verification_prompt
        from ez.contracts import digest
        from ez.cli import main
        from ez.mcp_server import ez_recall
        from ez.vault import records
        case = test_v6_rules.DirectDeliveryTests('test_direct_delivery_needs_no_review_and_no_second_query')
        case.setUp()
        self.addCleanup(case.temp.cleanup)
        with lock(case.folder):
            store = Store(case.folder)
            sources = read_json(case.folder / 'sources.json')
            sources[0].update(authors=['Li J'], year=2020)
            state = store.state()
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})
        with patch('test_v6_rules.ANSWER', '1. Solo adultos:\n\t- La fuente describe un resultado experimental concreto [1].'):
            self.assertEqual(case.run_engine()[0], 0)
        answer = read_json(case.folder / 'answer.json')
        self.assertEqual(answer['claims'][0]['context'], 'Solo adultos')
        self.assertIn('Solo adultos', (case.folder / 'report.md').read_text(encoding='utf-8'))
        self.assertIn('Solo adultos', verification_prompt(answer['claims']))
        self.assertEqual(records(case.folder.parent, 'general')[0]['context'], 'Solo adultos')
        for extra in ([], ['--full']):
            code, shown = case.cli('status', str(case.folder), '--answer', *extra)
            self.assertEqual(code, 0)
            self.assertEqual(shown['claims'][0]['context'], 'Solo adultos')
        self.assertEqual(case.cli('draft', str(case.folder))[1]['claims'][0]['context'], 'Solo adultos')
        def invoke(*args, **kwargs):
            output = StringIO()
            with patch('ez.cli.load_environment'), redirect_stdout(output):
                code = main(['--root', str(case.folder.parent), *args, '--json'])
            self.assertEqual(code, 0)
            return json.loads(output.getvalue())
        with patch('ez.mcp_server.ez', side_effect=invoke):
            compact = ez_recall('resultado experimental', 'general')
            full = ez_recall('resultado experimental', 'general', full=True)
        self.assertEqual(compact['hits'][0]['context'], 'Solo adultos')
        self.assertEqual(full['hits'][0]['context'], 'Solo adultos')
        self.assertIsInstance(full['hits'][0]['passages'], list)
        self.assertEqual(full['hits'][0]['passages'][0]['source']['source_id'], 's1')
        # Follow-up response has a resolvable, run-qualified marker and author-year citation.
        with patch('ez.engine.Engine.__init__.__defaults__', (case.service,)), patch('ez.engine.executable', return_value='fake'):
            code, followup = case.cli('ask', 'Otra pregunta neutral', '--project', 'general')
        self.assertEqual(code, 0)
        self.assertEqual(followup['claims'][0]['citation'], '(Li, 2020)')
        self.assertIn('/ask1-', followup['claims'][0]['marker'])
        # A saved delivery must not become a bypass around the PDF integrity gate.
        Path(sources[0]['pdf_path']).write_bytes(b'changed after delivery')
        code, rejected = case.cli('draft', str(case.folder))
        self.assertNotEqual(code, 0)
        self.assertNotIn('claims', rejected)

    def test_recall_retains_identical_text_different_context_and_sources(self):
        from ez.vault import recall
        rows = [dict(key=f'r/{i}', run_id='r', claim_id=str(i), text='Response increased 10 units', context=c,
                     passages=[], delivery='direct') for i, c in enumerate(('Grupo A', 'Grupo B', 'Estudio C'))]
        with patch('ez.vault.records', return_value=rows), patch('ez.library.project_sources', return_value=[]):
            result = recall(Path('unused'), 'p', 'response increased')
        self.assertEqual([h['context'] for h in result['hits']], ['Grupo A', 'Grupo B', 'Estudio C'])

    def test_shared_pdf_changes_replacement_and_deletion_are_explicit(self):
        from ez.contracts import ContractError
        from ez.library import adopt
        from ez.imports import import_pdf, INBOX_ORIGIN
        from ez.vault import page_cache, recall
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / 'imported.pdf'
            original.write_bytes(b'original bytes')
            source = dict(source_id='s', _run_id='first')
            # Exercise real import copying; only PDF structural validation is simulated.
            with patch('ez.imports.validate_pdf_bounded', return_value={
                    'status': 'valid', 'sha256': sha256(original.read_bytes()).hexdigest()}):
                import_pdf(root, Mock(), source, original, INBOX_ORIGIN)
            second = root / 'second'
            second.mkdir()
            shared = adopt(second, source)
            cache = root / 'cache/pages' / (source['content_sha256'] + '.json')
            atomic_json(cache, {'sha256': source['content_sha256'], 'pages': ['Response increased 10 units']})
            before = cache.read_bytes()
            for action in ('modify', 'replace', 'delete'):
                target = Path(shared['pdf_path'])
                if action == 'modify':
                    target.write_bytes(b'changed')
                elif action == 'replace':
                    target.unlink()
                    target.write_bytes(b'replacement')
                else:
                    target.unlink()
                with self.subTest(action=action), self.assertRaisesRegex(ContractError, 'integrity'):
                    page_cache(root / 'runs', shared)
                with patch('ez.vault.records', return_value=[]), patch('ez.library.project_sources', return_value=[shared]):
                    result = recall(root / 'runs', 'p', 'Response increased')
                self.assertEqual(result['pdf_passages'], [])
                self.assertTrue(result['integrity_issues'])
                self.assertEqual(cache.read_bytes(), before)
                self.assertEqual(original.read_bytes(), b'original bytes')

    def test_changed_pdf_with_delivered_claim_is_not_returned(self):
        from ez.vault import records
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            pdf = folder / 'a.pdf'
            pdf.write_bytes(b'changed')
            source = dict(pdf_path=str(pdf), content_sha256=sha256(b'original').hexdigest())
            claim = dict(id='q1', text='Outcome', references=[dict(source=source, cited_text='Old evidence')])
            answer = {'claims': [claim]}
            row = dict(path=str(folder), question='q', updated_at='2026-01-01')
            issues = []
            with patch('ez.context.history', return_value=[row]), patch('ez.vault.valid_answer', return_value=(answer, {'run_id': 'r'})):
                self.assertEqual(records(folder, 'p', issues), [])
            self.assertTrue(issues)

    def test_named_work_gate_has_high_coverage_and_language_is_unknown(self):
        from ez.vault import recall
        row = dict(key='r/a', text='growth medium outcome response', context='', passages=[])
        with patch('ez.vault.records', return_value=[row]), patch('ez.library.project_sources', return_value=[]):
            result = recall(Path('unused'), 'p', 'growth medium outcome response 10.1234/absent')
        self.assertGreaterEqual(result['coverage'], .6)
        self.assertEqual(result['named_works_absent'], ['10.1234/absent'])
        self.assertFalse(result['answer_assessed'])
        self.assertNotEqual(result['evidence'], 'sufficient')
        for query in ('li 2020', 'PCR 2020', 'photosynthesis 2020'):
            with patch('ez.vault.records', return_value=[]), patch('ez.library.project_sources', return_value=[]):
                result = recall(Path('unused'), 'p', query)
            self.assertEqual(result['named_works_absent'], [])
            self.assertTrue(result['named_works_unresolved'])
            self.assertIsNone(result['query_language_mismatch'])


if __name__ == '__main__':
    unittest.main()
