"""Refactor v6: verified claims stand on their own, review slips are corrected, project notebooks are reused."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.contracts import digest
from ez.engine import NOTEBOOK_SOURCE_LIMIT, Engine
from ez.process import Result
from ez.state import Store, lock, read_json
import test_engine
import test_phase1


class RuleTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine
    review = test_engine.EngineTests.review
    add_source = test_phase1.Phase1Tests.add_source

    def test_verification_may_cite_another_verified_source_of_the_corpus(self):
        self.add_source('s2')
        self.run_engine()
        def other_source(args, **kwargs):
            if args[1] == 'ask' and 'Evalúa si las fuentes' in args[-2]:
                answer = 'EZ_VERDICT c1: supported\nEZ_RATIONALE c1: Lo dice la otra fuente [1].'
                return Result(0, json.dumps({'answer': answer, 'references': [{'source_id': 'remote2', 'citation_number': 1,
                                             'cited_text': 'Pasaje de la segunda fuente.'}]}), '', None)
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(self.folder, runner=other_source).execute(self.review()), 0)
        claim = read_json(self.folder / 'answer.json')['claims'][0]
        self.assertEqual([(r['role'], r['source']['source_id']) for r in claim['references']],
                         [('qa', 's1'), ('verification', 's2')])

    def test_review_slips_are_corrected_and_recorded(self):
        self.run_engine()
        review = self.review()
        review['claims'][0].update(scope_ids=['sq1', 'sq2'], citation_numbers=[1, 2])
        self.assertEqual(self.run_engine(review)[0], 0)
        report = read_json(self.folder / 'answer.json')
        self.assertEqual(report['claims'][0]['scope_ids'], ['sq1'])
        self.assertEqual(report['claims'][0]['citation_numbers'], [1])
        self.assertEqual(report['review_adjustments'], [
            {'claim_id': 'c1', 'field': 'scope_ids', 'from': ['sq1', 'sq2'], 'to': ['sq1']},
            {'claim_id': 'c1', 'field': 'citation_numbers', 'from': [1, 2], 'to': [1]}])

    def test_a_claim_without_any_cited_passage_is_still_rejected(self):
        self.run_engine()
        review = self.review()
        review['claims'][0]['citation_numbers'] = [5]
        code, state = self.run_engine(review)
        self.assertEqual((code, state['legacy_signals']), (2, ['review_invalid']))


class NotebookReuseTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine

    def library(self, notebook_id='old'):
        from ez.state import atomic_json
        path = Path(self.temp.name) / 'projects' / 'general' / 'notebooks.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(path, {'schema_version': '1.0', 'notebooks': [{'notebook_id': notebook_id, 'created_by_run': 'x', 'runs': ['x'], 'sources': {}}]})
        return path

    def runner(self, listing):
        def run(args, **kwargs):
            if args[1:3] == ['source', 'list'] and args[args.index('--notebook') + 1] == 'old':
                return listing()
            return self.service(args, **kwargs)
        return run

    def execute(self, runner):
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            return Engine(self.folder, runner=runner).execute()

    def test_a_project_notebook_with_room_receives_only_the_missing_pdfs(self):
        self.library()
        other = [{'id': 'x%d' % i, 'title': 'src-%d-aaaaaaaaaaaa.pdf' % i, 'status': 'ready'} for i in range(3)]
        def listing():
            return Result(0, json.dumps({'sources': other + self.service.sources}), '', None)
        self.assertEqual(self.execute(self.runner(listing)), 2)
        self.assertEqual((self.service.create_count, self.service.upload_count), (0, 1))
        state = read_json(self.folder / 'run-state.json')
        self.assertEqual((state['notebook_id'], state['notebook_shared']), ('old', True))
        # Every question starts a fresh conversation.
        self.assertTrue(all('--new' in a for a in self.service.calls if a[1] == 'ask'))

    def test_a_full_or_missing_project_notebook_is_replaced(self):
        for name, listing in (('full', lambda: Result(0, json.dumps({'sources': [
                                  {'id': 'x%d' % i, 'title': 't%d.pdf' % i, 'status': 'ready'} for i in range(NOTEBOOK_SOURCE_LIMIT)]}), '', None)),
                              ('deleted', lambda: Result(1, '', 'Notebook not found', None))):
            with self.subTest(name):
                self.setUp()
                self.library()
                self.assertEqual(self.execute(self.runner(listing)), 2)
                self.assertEqual(self.service.create_count, 1)
                library = read_json(Path(self.temp.name) / 'projects' / 'general' / 'notebooks.json')
                self.assertEqual([n['notebook_id'] for n in library['notebooks']], ['old', 'nb1'])


ANSWER = ('**Resultado:** la fuente describe un resultado experimental concreto [1].\n'
          '* Esta oración no tiene cita y señala un límite del corpus disponible.')


class DirectDeliveryTests(unittest.TestCase):
    run_engine = test_engine.EngineTests.run_engine

    def setUp(self):
        test_engine.EngineTests.setUp(self)
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            contract = read_json(self.folder / 'research-contract.json')
            contract['plan']['delivery'] = 'direct'
            state['contract_hash'] = digest(contract)
            store.commit(state, {'research-contract.json': contract})
        service = self.service
        def answering(args, **kwargs):
            result = service(args, **kwargs)
            if args[1] == 'ask' and 'Evalúa si las fuentes' not in args[-2]:
                value = json.loads(result.stdout); value['answer'] = ANSWER
                return Result(0, json.dumps(value), '', None)
            return result
        answering.calls = service.calls
        self.service = answering

    def cli(self, *arguments):
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main(['--root', self.temp.name, *arguments, '--json'])
        return code, json.loads(output.getvalue())

    def test_direct_delivery_needs_no_review_and_no_second_query(self):
        code, state = self.run_engine()
        self.assertEqual(code, 0)
        self.assertEqual(state['answer'], {'status': 'partial', 'scope_ids': ['sq1']})
        report = read_json(self.folder / 'answer.json')
        self.assertEqual((report['delivery'], report['support_protocol']), ('direct', 'ez-direct-v1'))
        claim = report['claims'][0]
        self.assertEqual((claim['id'], claim['text'], claim['citation_numbers']),
                         ('qa1-1', 'Resultado: la fuente describe un resultado experimental concreto.', [1]))
        self.assertEqual([(r['role'], r['source']['source_id']) for r in claim['references']], [('qa', 's1')])
        self.assertEqual([n['text'] for n in report['uncited_statements']],
                         ['Esta oración no tiene cita y señala un límite del corpus disponible.'])
        self.assertEqual(sum(a[1] == 'ask' for a in self.service.calls), 1)
        text = (self.folder / 'report.md').read_text(encoding='utf-8')
        self.assertIn('Cómo se obtuvo', text)
        self.assertIn('Lo que NotebookLM dijo sin citar', text)
        from ez.metrics import collect
        from ez.presenter import render
        self.assertIn('describe un resultado experimental', render(report))
        self.assertEqual(collect(self.folder)['claims_with_traceability'], 1)
        self.assertTrue((self.folder / 'review-request.json').exists())
        self.assertEqual(self.cli('draft', str(self.folder))[1]['claims'][0]['marker'], '[EZ:qa1-1]')
        self.assertEqual(self.run_engine()[0], 0)
        self.assertEqual(sum(a[1] == 'ask' for a in self.service.calls), 1)

    def test_a_person_can_withdraw_a_direct_claim(self):
        self.run_engine()
        with patch('ez.engine.Engine.__init__.__defaults__', (self.service,)), patch('ez.engine.executable', return_value='notebooklm'):
            code, _ = self.cli('verify', str(self.folder), '--claim', 'qa1-1', '--judgement', 'unsupported')
        self.assertEqual(code, 0)
        answer = read_json(self.folder / 'answer.json')
        self.assertEqual((answer['claims'], answer['withheld_claims'][0]['reason']), ([], 'human_rejected'))

    def test_a_review_switches_the_run_to_verified_delivery(self):
        self.run_engine()
        review = test_engine.EngineTests.review(self)
        review['claims'][0]['text'] = 'La fuente describe un resultado experimental concreto.'
        code, _ = self.run_engine(review)
        self.assertEqual(code, 0)
        report = read_json(self.folder / 'answer.json')
        self.assertEqual((report.get('delivery'), report['support_protocol']), (None, 'ez-verdict-v5-grounded'))
        self.assertEqual(sum('Evalúa si las fuentes' in a[-2] for a in self.service.calls if a[1] == 'ask'), 1)
        # A later continue keeps the reviewed answer instead of returning to direct delivery.
        self.assertEqual(self.run_engine()[0], 0)
        self.assertEqual(read_json(self.folder / 'answer.json')['support_protocol'], 'ez-verdict-v5-grounded')


class SpeedTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def processing(self, polls):
        state = {'lists': 0}
        def run(args, **kwargs):
            result = self.service(args, **kwargs)
            if args[1:3] == ['source', 'list'] and self.service.sources:
                state['lists'] += 1
                value = json.loads(result.stdout)
                if state['lists'] <= polls:
                    value['sources'] = [dict(s, status='processing') for s in value['sources']]
                return Result(0, json.dumps(value), '', None)
            return result
        return run

    def test_ez_waits_for_processing_inside_the_same_call(self):
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'), \
                patch('ez.engine.time.sleep') as sleep:
            self.assertEqual(Engine(self.folder, runner=self.processing(2)).execute(), 2)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(read_json(self.folder / 'run-state.json')['phase'], 'audit')

    def test_processing_beyond_the_wait_still_pauses(self):
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'), \
                patch('ez.engine.READINESS_WAIT_SECONDS', 0):
            self.assertEqual(Engine(self.folder, runner=self.processing(99)).execute(), 3)
        self.assertEqual(read_json(self.folder / 'run-state.json')['legacy_signals'], ['waiting_on_processing'])

    def test_downloads_run_in_parallel_and_are_journaled_in_order(self):
        import threading
        from ez.state import Store as S
        with lock(self.folder):
            store = S(self.folder); state = store.state()
            sources = read_json(self.folder / 'sources.json')
            sources += [{'source_id': 'p%d' % i, 'title': 'Pendiente %d' % i, 'acquisition_status': 'pending', 'screening': 'include',
                         'validation_status': 'unknown', 'identity_status': 'unknown', 'notebook_status': 'pending'} for i in range(4)]
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})
        barrier = threading.Barrier(4, timeout=5)
        def run(args, **kwargs):
            if args[1:3] == ['-m', 'ez.acquisition']:
                barrier.wait()  # Fails unless the four downloads are in flight together.
                return Result(1, '', '', 'routes_exhausted')
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            Engine(self.folder, runner=run).execute()
        sources = {s['source_id']: s for s in read_json(self.folder / 'sources.json')}
        self.assertEqual({sources['p%d' % i]['failure_code'] for i in range(4)}, {'routes_exhausted'})


class SentenceTests(unittest.TestCase):
    def test_species_abbreviations_and_trailing_markers_stay_in_their_sentence(self):
        from ez.audit import plain, sentences
        text = ('* **Blanco:** en *C. glutamicum* el etambutol inhibe EmbC (Radmacher et al. 2005) [1, 2]. '
                'Se observó hinchazón polar. [3]\n1. Ver Fig. 2 para M. tuberculosis [4].')
        self.assertEqual([plain(s) for s in sentences(text)],
                         ['Blanco: en C. glutamicum el etambutol inhibe EmbC (Radmacher et al. 2005).',
                          'Se observó hinchazón polar.', 'Ver Fig. 2 para M. tuberculosis.'])


if __name__ == '__main__':
    unittest.main()
