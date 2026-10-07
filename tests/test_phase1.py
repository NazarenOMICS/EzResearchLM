"""Evidence delivery: versioned reviews, batch verification, bibliography and recorded gaps."""
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
import unittest
from unittest.mock import patch

from PyPDF2 import PdfWriter

from ez.cli import main
from ez.contracts import digest, draft
from ez.engine import Engine
from ez.policies import evaluate
from ez.presenter import render
from ez.process import Result
from ez.state import Store, lock, read_json
import test_engine


class Phase1Tests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine
    review = test_engine.EngineTests.review

    def add_source(self, source_id, identity='verified', doi=None):
        pdf = self.folder / (source_id + '.pdf')
        writer = PdfWriter(); writer.add_blank_page(width=72 + len(source_id), height=72)
        with pdf.open('wb') as stream:
            writer.write(stream)
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            sources = read_json(self.folder / 'sources.json')
            sources.append({'source_id': source_id, 'title': 'Fuente ' + source_id, 'doi': doi, 'pdf_path': str(pdf),
                            'content_sha256': sha256(pdf.read_bytes()).hexdigest(), 'validation_status': 'valid',
                            'identity_status': identity, 'notebook_status': 'pending', 'acquisition_status': 'downloaded'})
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})

    def test_review_template_follows_the_corpus_and_stale_review_waits(self):
        self.run_engine()
        first = read_json(self.folder / 'review-request.json')
        stale = self.review()
        self.add_source('s2')
        code, state = self.run_engine()
        self.assertEqual(code, 2)
        current = read_json(self.folder / 'review-request.json')
        self.assertNotEqual(current['corpus_hash'], first['corpus_hash'])
        self.assertEqual(current['corpus_hash'], state['corpus_hash'])
        self.assertEqual(read_json(self.folder / ('review-request-' + first['corpus_hash'][:12] + '.json')), first)
        code, state = self.run_engine(stale)
        self.assertEqual(code, 2)
        self.assertEqual(state['legacy_signals'], ['review_outdated'])
        self.assertEqual(state['integrity']['status'], 'pending')
        self.assertEqual(self.run_engine(self.review())[0], 0)

    def test_delivered_claims_carry_bibliography_and_record_skipped_questions(self):
        self.run_engine()
        self.assertEqual(self.run_engine(self.review())[0], 0)
        report = read_json(self.folder / 'answer.json')
        self.assertEqual(report['schema_version'], '2.1')
        source = report['claims'][0]['references'][0]['source']
        self.assertEqual((source['source_id'], source['title']), ('s1', 'Fuente de prueba'))
        self.assertEqual(len(source['content_sha256']), 64)
        self.assertEqual(report['skipped_questions'], [{'question_id': 'qa2', 'scope_ids': ['sq2'],
                                                        'reason': 'required_source_missing', 'source_ids': ['missing']}])
        text = render(report)
        self.assertIn('Fuente de prueba', text)
        self.assertNotIn('Fuente NotebookLM: remote1', text)
        self.assertIn('Preguntas no consultadas', text)

    def test_one_batch_verifies_several_claims_and_records_each_withheld_claim(self):
        self.run_engine()
        review = self.review()
        review['claims'].append({'id': 'c2', 'text': 'Otra afirmación', 'scope_ids': ['sq1'], 'question_id': 'qa1', 'citation_numbers': [1]})
        calls = []
        def mixed(args, **kwargs):
            calls.append(args)
            if args[1] == 'ask' and 'Evalúa si las fuentes' in args[-2]:
                answer = ('EZ_VERDICT c1: supported\nEZ_RATIONALE c1: "Pasaje de prueba" [1].\n'
                          'EZ_VERDICT c2: partial\nEZ_RATIONALE c2: Solo en parte [1].')
                return Result(0, json.dumps({'answer': answer, 'references': [{'source_id': 'remote1', 'citation_number': 1,
                                             'cited_text': 'Pasaje de prueba, sin contenido académico real.'}]}), '', None)
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(self.folder, runner=mixed).execute(review), 2)
        self.assertEqual(sum(a[1] == 'ask' for a in calls), 1)
        report = read_json(self.folder / 'answer.json')
        self.assertEqual(report['claims'], [])
        self.assertEqual({c['id']: c['reason'] for c in report['withheld_claims']},
                         {'c2': 'verdict_partial', 'c1': 'scope_not_sufficient'})
        self.assertIn('No se pudo afirmar', render(report))

    def test_sources_left_out_of_the_corpus_are_reported_before_review(self):
        self.add_source('s3', identity='needs_review')
        code, state = self.run_engine()
        self.assertEqual(code, 2)
        self.assertEqual(state['corpus_exclusions'], [{'source_id': 's3', 'title': 'Fuente s3', 'reason': 'identity_unconfirmed'}])
        self.assertIn('1 fuentes quedaron fuera del corpus', state['next_action'])
        self.assertIn('falta confirmar qué artículo', render(state))

    def test_quota_exhaustion_waits_without_leaving_an_uncertain_upload(self):
        def quota(args, **kwargs):
            if args[1:3] == ['source', 'add']:
                return Result(1, '', 'Error: 429 Too Many Requests (quota exceeded)', None)
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            engine = Engine(self.folder, runner=quota)
            self.assertEqual(engine.execute(), 3)
            self.assertEqual(engine.state['legacy_signals'], ['quota_exhausted'])
            self.assertEqual(engine.state['execution']['status'], 'waiting_service')
        self.assertFalse(read_json(self.folder / 'sources.json')[0]['upload_pending'])
        self.assertEqual(self.run_engine()[0], 2)
        self.assertEqual(self.service.upload_count, 1)

    def cli(self, *arguments):
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main([*arguments, '--json'])
        return code, json.loads(output.getvalue())

    def test_check_validates_proposals_and_reviews_without_writing(self):
        self.run_engine()
        before = {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob('*') if p.is_file() and p.name != '.ez.lock'}
        review_path = self.folder.parent / 'review.json'
        review_path.write_text(json.dumps(self.review()), encoding='utf-8')
        code, result = self.cli('continue', str(self.folder), '--review', str(review_path), '--check')
        self.assertEqual((code, result['valid'], result['claims']), (0, True, 1))
        bad = self.review(); bad['claims'][0]['citation_numbers'] = [7]
        review_path.write_text(json.dumps(bad), encoding='utf-8')
        code, result = self.cli('continue', str(self.folder), '--review', str(review_path), '--check')
        self.assertEqual(code, 4)
        self.assertIn('c1', result['next_action'])
        proposal = read_json(self.folder / 'research-contract.json')
        proposal['plan']['stop_rule'] = ''
        contract_path = self.folder.parent / 'proposal.json'
        contract_path.write_text(json.dumps(proposal), encoding='utf-8')
        code, result = self.cli('continue', str(self.folder), '--contract', str(contract_path), '--check')
        self.assertEqual((code, result['valid'], result['ready']), (0, True, False))
        after = {p.relative_to(self.folder): p.read_bytes() for p in self.folder.rglob('*') if p.is_file() and p.name != '.ez.lock'}
        self.assertEqual(before, after)
        self.assertEqual(sum(a[1] == 'ask' for a in self.service.calls), 1)


class SignalTests(unittest.TestCase):
    def test_more_qa_is_not_requested_for_a_scope_held_by_a_missing_required_source(self):
        contract = draft('Pregunta', {})
        contract['scope'].append({'id': 'sq2', 'question': 'Otra', 'central': True})
        contract['source_policies'] = [{'source_id': 'req', 'policy': 'hard_block', 'scope_ids': ['sq2'],
                                        'rationale': 'Obligatoria', 'locked_by_user': True}]
        sources = [{'source_id': 's1', 'notebook_status': 'ready', 'validation_status': 'valid', 'identity_status': 'verified'}]
        result = evaluate(contract, sources, {'sq1': 'sufficient', 'sq2': 'insufficient'}, 'pass')
        self.assertEqual(result['answer']['status'], 'partial')
        self.assertEqual(result['legacy_signals'], ['NEEDS_SOURCE_RESCUE'])
        result = evaluate(contract, sources, {'sq1': 'insufficient', 'sq2': 'insufficient'}, 'pass')
        self.assertEqual(result['legacy_signals'], ['NEEDS_MORE_QA', 'NEEDS_SOURCE_RESCUE'])


if __name__ == '__main__':
    unittest.main()
