"""Offline integration: actual checkpoints, CLI contracts, source bytes and QA.

The service double models NotebookLM's documented JSON envelope, not real auth.
"""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PyPDF2 import PdfWriter

from ez.cli import create_run
from ez.contracts import ContractError, draft, digest
from ez.engine import Engine
from ez.doctor import diagnose
from ez.process import Result
from ez.state import Store, atomic_json, lock, read_json


class Service:
    def __init__(self):
        self.calls = []
        self.sources = []
        self.create_count = 0
        self.upload_count = 0
        self.wrong_citation = False
        self.verdict = 'supported'
        self.interrupt_upload = False
        self.interrupt_create = False
        self.notebooks = []
        self.discovery_records = []

    def __call__(self, args, **kwargs):
        self.calls.append(args)
        if args[1:3] == ['-m', 'ez.discovery']:
            atomic_json(args[args.index('--output') + 1], {'candidates': self.discovery_records, 'status': 'complete'})
            value = {}
        elif args[1] == 'create':
            self.create_count += 1
            self.notebooks.append({'id': 'nb1', 'title': args[2]})
            if self.interrupt_create:
                self.interrupt_create = False
                return Result(124, '', '', 'deadline_exceeded')
            value = {'notebook': {'id': 'nb1'}}
        elif args[1] == 'list':
            value = {'notebooks': self.notebooks}
        elif args[1:3] == ['source', 'add']:
            self.upload_count += 1
            # The real CLI's file upload uses the filename even with --title.
            title = Path(args[-2]).name
            self.sources.append({'id': 'remote1', 'title': title, 'status': 'ready'})
            if self.interrupt_upload:
                self.interrupt_upload = False
                return Result(124, '', '', 'deadline_exceeded')
            value = {'source': {'id': 'remote1'}}
        elif args[1:3] == ['source', 'list']:
            value = {'sources': self.sources}
        elif args[1] == 'ask':
            verification = 'Evalúa si las fuentes' in args[-2]
            answer = json.dumps({'verdict': self.verdict, 'rationale': 'Soporte del corpus [1]'}) if verification else 'Resultado de la fuente [1].'
            value = {'answer': answer, 'conversation_id': 'chat1', 'turn_number': 1, 'is_follow_up': False,
                     'references': [{'source_id': 'foreign' if self.wrong_citation else 'remote1', 'citation_number': 1,
                                     'cited_text': 'Pasaje de prueba, sin contenido académico real.'}]}
        else:
            raise AssertionError(args)
        return Result(0, json.dumps(value), '', None)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        contract = draft('Pregunta de prueba', {})
        contract['scope'].append({'id': 'sq2', 'question': 'Otra pregunta', 'central': True})
        contract['source_policies'] = [{'source_id': 'missing', 'policy': 'hard_block', 'scope_ids': ['sq2'],
                                       'rationale': 'Obligación explícita', 'locked_by_user': True}]
        contract['plan'] = {'status': 'ready', 'queries': [{'id': 'q1', 'text': 'query', 'provider': 'crossref', 'scope_ids': ['sq1', 'sq2']}],
                            'notebook_questions': [{'id': 'qa1', 'text': 'Pregunta', 'scope_ids': ['sq1']},
                                                   {'id': 'qa2', 'text': 'Otra', 'scope_ids': ['sq2']}], 'stop_rule': 'Una ronda, luego revisar cobertura'}
        self.folder, state = create_run(Path(self.temp.name), 'Pregunta de prueba', {}, contract)
        pdf = self.folder / 'source.pdf'
        writer = PdfWriter(); writer.add_blank_page(width=72, height=72)
        with pdf.open('wb') as f:
            writer.write(f)
        self.sources = [{'source_id': 's1', 'title': 'Fuente de prueba', 'pdf_path': str(pdf),
                         'content_sha256': sha256(pdf.read_bytes()).hexdigest(), 'validation_status': 'valid',
                         'identity_status': 'verified', 'notebook_status': 'pending', 'acquisition_status': 'downloaded'}]
        state.update(discovery_complete=True, sources_hash=digest(self.sources))
        with lock(self.folder):
            Store(self.folder).commit(state, {'sources.json': self.sources})
        self.service = Service()

    def run_engine(self, review=None):
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            engine = Engine(self.folder, runner=self.service)
            code = engine.execute(review)
        return code, engine.state

    def review(self):
        state = Store(self.folder).state()
        return {'schema_version': '2.0', 'contract_hash': state['contract_hash'], 'corpus_hash': state['corpus_hash'],
                'reviewer': {'kind': 'host_agent', 'name': 'EZ'},
                'coverage': [{'scope_id': 'sq1', 'status': 'sufficient', 'rationale': 'QA citada revisada', 'limitations': []},
                             {'scope_id': 'sq2', 'status': 'insufficient', 'rationale': 'Falta fuente requerida', 'limitations': ['Fuente requerida ausente']}],
                'claims': [{'id': 'c1', 'text': 'Afirmación de prueba', 'scope_ids': ['sq1'], 'question_id': 'qa1', 'citation_numbers': [1]}]}

    def test_partial_delivery_and_resume_do_not_duplicate_remote_work(self):
        code, state = self.run_engine()
        self.assertEqual(code, 2)
        self.assertEqual(state['answer']['status'], 'unavailable')
        code, state = self.run_engine(self.review())
        self.assertEqual(code, 0)
        self.assertEqual(state['answer'], {'status': 'partial', 'scope_ids': ['sq1']})
        self.assertIn('NEEDS_SOURCE_RESCUE', state['legacy_signals'])
        report = read_json(self.folder / 'answer.json')
        self.assertEqual(len(report['claims']), 1)
        self.assertFalse(report['release_validation'])
        asks_before = sum(args[1] == 'ask' for args in self.service.calls)
        code, state = self.run_engine()
        self.assertEqual(code, 0)
        self.assertEqual(asks_before, sum(args[1] == 'ask' for args in self.service.calls))
        self.assertEqual(self.service.create_count, 1)
        self.assertEqual(self.service.upload_count, 1)

    def test_discovery_accepts_pending_null_pdf_without_erasing_prior_import(self):
        self.service.discovery_records = [{'title': 'New metadata', 'doi': '10.1234/new', 'pdf_path': None, 'pdf_url': None,
                                           'sources': ['crossref'], 'queries': ['query'], 'pmid': None, 'pmcid': None}]
        with lock(self.folder):
            store = Store(self.folder); state = store.state(); state['discovery_complete'] = False; store.update(state)
            engine = Engine(self.folder, runner=self.service)
            engine.discover()
            self.assertEqual(len(engine.sources), 2)
            self.assertEqual(engine.sources[0]['source_id'], 's1')
            self.assertIsNone(engine.sources[1]['pdf_path'])
            self.assertTrue(engine.state['discovery_complete'])

    def test_require_complete_preserves_partial_answer_but_signals_pending_work(self):
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            state['require_complete'] = True
            store.update(state)
        self.run_engine()
        code, state = self.run_engine(self.review())
        self.assertEqual(code, 2)
        self.assertEqual(state['answer']['status'], 'partial')
        self.assertEqual(len(read_json(self.folder / 'answer.json')['claims']), 1)
        self.assertEqual(self.run_engine()[0], 2)

    def test_explicit_doi_is_acquired_even_when_discovery_finds_nothing(self):
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            contract = read_json(self.folder / 'research-contract.json')
            contract['source_policies'][0].update(doi='10.1234/required', title='Required source')
            state.update(contract_hash=digest(contract), discovery_complete=False)
            store.commit(state, {'research-contract.json': contract})
            engine = Engine(self.folder, runner=self.service)
            engine.discover()
            required = next(s for s in engine.sources if s['source_id'] == 'missing')
            self.assertEqual(required['doi'], '10.1234/required')
            self.assertEqual(required['acquisition_status'], 'pending')
            self.assertEqual(required['discovery_origin'], 'explicit_contract_requirement')

    def test_interrupted_upload_reconciles_by_title_without_reupload(self):
        self.service.interrupt_upload = True
        code, state = self.run_engine()
        self.assertEqual(code, 3)
        self.assertEqual(self.run_engine()[0], 2)
        self.assertEqual(self.service.upload_count, 1)
        self.assertEqual(self.service.create_count, 1)

    def test_lost_create_response_reconciles_without_another_notebook(self):
        self.service.interrupt_create = True
        code, state = self.run_engine()
        self.assertEqual(code, 3)
        self.assertEqual(state['pending_operation'], 'create_notebook')
        self.assertEqual(self.run_engine()[0], 2)
        self.assertEqual(self.service.create_count, 1)
        self.assertEqual(self.service.upload_count, 1)

    def test_structural_citation_resolution_keeps_raw_text_and_detects_tampering(self):
        self.run_engine()
        quote = 'This synthetic source reports a specific change to the documented research procedure.'
        response = {'answer': '"' + quote + '" [1]', 'references': [
            {'source_id': 'remote1', 'citation_number': 1, 'cited_text': None}]}
        calls = []
        def fulltext(args, **kwargs):
            calls.append(args)
            self.assertEqual(args[1:4], ['source', 'fulltext', 'remote1'])
            return Result(0, json.dumps({'source_id': 'remote1', 'content': quote}), '')
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            engine = Engine(self.folder, runner=fulltext)
            resolved = engine.resolve_citations(response)
            self.assertEqual(resolved['references'][0]['cited_text'], quote)
            self.assertEqual(engine.resolve_citations(response), resolved)
            self.assertEqual(len(calls), 1)
        receipt = next((self.folder / 'citation-resolution').glob('*.json'))
        self.assertIsNone(read_json(receipt)['raw_response']['references'][0]['cited_text'])
        receipt.write_text('{}', encoding='utf-8')
        self.assertFalse(diagnose(self.folder)['healthy'])

    def test_unknown_remote_envelope_waits_without_duplicate_create_or_traceback(self):
        def wrong_list(args, **kwargs):
            if args[1:3] == ['source', 'list']:
                return Result(0, '{"sources": [null]}', '')
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            engine = Engine(self.folder, runner=wrong_list)
            self.assertEqual(engine.execute(), 3)
            self.assertEqual(engine.state['legacy_signals'], ['invalid_notebooklm_output'])
        self.assertEqual(self.run_engine()[0], 2)
        self.assertEqual(self.service.create_count, 1)

    def test_expired_auth_does_not_leave_a_false_pending_create(self):
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            engine = Engine(self.folder, runner=lambda *a, **k: Result(1, '', 'Authentication expired', ''))
            self.assertEqual(engine.execute(), 2)
            self.assertIsNone(engine.state.get('pending_operation'))
        self.assertEqual(self.run_engine()[0], 2)
        self.assertEqual(self.service.create_count, 1)

    def test_foreign_citation_blocks_delivery(self):
        self.service.wrong_citation = True
        self.run_engine()
        code, state = self.run_engine(self.review())
        self.assertEqual(code, 4)
        self.assertEqual(state['answer']['status'], 'unavailable')
        self.assertFalse((self.folder / 'answer.json').exists())

    def test_unsupported_claim_cannot_be_delivered_as_complete(self):
        self.run_engine()
        self.service.verdict = 'unsupported'
        code, state = self.run_engine(self.review())
        self.assertEqual(code, 2)
        self.assertEqual(state['answer']['status'], 'unavailable')
        self.assertEqual(read_json(self.folder / 'answer.json')['claims'], [])

    def test_empty_review_cannot_claim_coverage(self):
        self.run_engine()
        review = self.review(); review['claims'] = []
        self.assertEqual(self.run_engine(review)[0], 4)

    def test_doctor_detects_changed_pdf_without_altering_the_run(self):
        self.run_engine()
        self.assertTrue(diagnose(self.folder)['healthy'])
        (self.folder / 'source.pdf').write_bytes(b'changed')
        journal_before = (self.folder / 'events.jsonl').read_bytes()
        report = diagnose(self.folder)
        self.assertFalse(report['healthy'])
        self.assertIn('pdf_changed', [f['code'] for f in report['findings']])
        self.assertEqual(journal_before, (self.folder / 'events.jsonl').read_bytes())

    def test_answer_delivery_rechecks_pdf_and_preserves_tampered_bytes(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from ez.cli import main
        self.run_engine()
        self.run_engine(self.review())
        pdf = self.folder / 'source.pdf'
        pdf.write_bytes(b'changed')
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main(['status', str(self.folder), '--answer', '--json'])
        self.assertEqual(code, 4)
        self.assertEqual(json.loads(output.getvalue())['answer']['status'], 'unavailable')
        self.assertEqual(pdf.read_bytes(), b'changed')

    def test_reuse_preserves_origin_and_creates_a_separate_remote_corpus(self):
        from ez.context import reuse_sources
        self.run_engine()
        before = {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob('*') if p.is_file()}
        contract = read_json(self.folder / 'research-contract.json')
        contract['plan'].update(discovery_mode='reuse_only', queries=[])
        destination, _ = create_run(Path(self.temp.name), 'Pregunta de prueba', {}, contract)
        reuse_sources(self.folder, destination)
        sources = read_json(destination / 'sources.json')
        self.assertNotIn('notebook_source_id', sources[0])
        self.assertEqual(sources[0]['reused_from']['notebook_source_id'], 'remote1')
        self.assertEqual(sources[0]['notebook_status'], 'pending')
        self.assertTrue(Path(sources[0]['pdf_path']).is_relative_to(destination))
        new_service = Service()
        with lock(destination), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(destination, runner=new_service).execute(), 2)
        self.assertEqual(new_service.create_count, 1)
        self.assertEqual(new_service.upload_count, 1)
        self.assertFalse(any(c[1:3] == ['-m', 'ez.discovery'] for c in new_service.calls))
        self.assertEqual(before, {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob('*') if p.is_file()})

    def test_reuse_rejects_changed_evidence_and_does_not_create_sources(self):
        from ez.context import reuse_sources
        (self.folder / 'source.pdf').write_bytes(b'changed')
        destination, _ = create_run(Path(self.temp.name), 'Nueva', {})
        with self.assertRaises(ContractError):
            reuse_sources(self.folder, destination)
        self.assertFalse((destination / 'sources.json').exists())

    def test_metrics_are_local_and_do_not_claim_human_or_authenticated_validation(self):
        from ez.metrics import collect
        self.run_engine()
        self.run_engine(self.review())
        metrics = collect(self.folder)
        self.assertEqual(metrics['delivered_claim_count'], 1)
        self.assertEqual(metrics['claims_with_traceability'], 1)
        self.assertIsNone(metrics['human_citation_review'])
        self.assertIsNone(metrics['authenticated_e2e_verified'])
        self.assertFalse(metrics['sent_remotely'])
        serialized = json.dumps(metrics)
        self.assertNotIn('Pregunta', serialized)
        self.assertNotIn('Afirmación', serialized)
        self.assertNotIn(str(self.folder), serialized)

    def test_qa_tamper_and_stale_contract_fail_closed(self):
        self.run_engine()
        review = self.review()
        review['contract_hash'] = '0' * 64
        self.assertEqual(self.run_engine(review)[0], 4)
        qa = read_json(self.folder / 'qa/manifest.json')['answers'][0]
        (self.folder / qa['path']).write_text('{}')
        self.assertEqual(self.run_engine(self.review())[0], 4)


class TransactionTests(unittest.TestCase):
    def test_crash_between_projections_recovers_one_commit(self):
        with tempfile.TemporaryDirectory() as folder, lock(folder):
            store = Store(folder)
            store.commit({'revision': 1}, {'contract.json': {'v': 1}, 'sources.json': []})
            real = atomic_json
            def fail_second(path, value):
                if Path(path).name == 'sources.json':
                    raise OSError('simulated power loss')
                return real(path, value)
            with patch('ez.state.atomic_json', side_effect=fail_second):
                with self.assertRaises(OSError):
                    store.commit({'revision': 2}, {'contract.json': {'v': 2}, 'sources.json': ['new']})
            self.assertEqual(store.state()['revision'], 2)
            self.assertEqual(store.recover(), ['sources.json'])
            store.recover(repair=True)
            self.assertEqual(read_json(Path(folder) / 'sources.json'), ['new'])
            self.assertEqual(len(store.events()), 2)

    def test_user_edit_is_preserved_during_recovery(self):
        with tempfile.TemporaryDirectory() as folder, lock(folder):
            store = Store(folder)
            store.commit({'v': 1}, {'contract.json': {'v': 1}})
            path = Path(folder) / 'contract.json'
            atomic_json(path, {'user_edit': True})
            with self.assertRaises(ContractError):
                store.recover(repair=True)
            self.assertEqual(read_json(path), {'user_edit': True})
