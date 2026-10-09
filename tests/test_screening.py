"""Phase 2: screening before acquisition, source cap, duplicates, gap causes and query counts."""
from contextlib import redirect_stdout
from hashlib import sha256
from io import StringIO
import json
import unittest
from unittest.mock import patch

from PyPDF2 import PdfWriter

from ez.cli import main
from ez.contracts import digest
from ez.engine import Engine
from ez.process import Result
from ez.state import Store, atomic_json, lock, read_json
import search_topic
import test_engine


class ScreeningTests(unittest.TestCase):
    setUp_base = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine
    review = test_engine.EngineTests.review

    def setUp(self):
        self.setUp_base()
        self.acquired = []
        self.service.discovery_records = [{'title': 'Relevant work', 'doi': '10.1/rel'}, {'title': 'Off topic work', 'doi': '10.1/off'}]
        with lock(self.folder):
            store = Store(self.folder); state = store.state(); state['discovery_complete'] = False; store.update(state)

    def runner(self, args, **kwargs):
        if args[1:3] == ['-m', 'ez.acquisition']:
            record = read_json(args[args.index('--record') + 1])
            self.acquired.append(record['source_id'])
            pdf = self.folder / ('acq-' + record['source_id'] + '.pdf')
            writer = PdfWriter(); writer.add_blank_page(width=72, height=72)  # identical bytes on purpose
            with pdf.open('wb') as stream:
                writer.write(stream)
            atomic_json(args[args.index('--output') + 1], dict(record, pdf_path=str(pdf), content_sha256=sha256(pdf.read_bytes()).hexdigest(),
                        validation_status='valid', identity_status='verified', acquisition_status='downloaded',
                        acquisition_input_hash=digest(record)))
            return Result(0, '', '', None)
        return self.service(args, **kwargs)

    def execute(self, screening=None):
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            engine = Engine(self.folder, runner=self.runner)
            return engine.execute(None, screening), engine

    def decisions(self, rows):
        request = read_json(self.folder / 'screening-request.json')
        ids = {c['title']: c['source_id'] for c in request['candidates']}
        return dict(request, decisions=[{'source_id': ids[title], 'decision': d, 'reason': 'motivo ' + d} for title, d in rows])

    def test_candidates_wait_for_screening_and_only_included_ones_are_acquired(self):
        code, engine = self.execute()
        self.assertEqual((code, engine.state['legacy_signals']), (2, ['NEEDS_SCREENING']))
        self.assertEqual(self.acquired, [])
        request = read_json(self.folder / 'screening-request.json')
        self.assertEqual(sorted(c['title'] for c in request['candidates']), ['Off topic work', 'Relevant work'])
        code, engine = self.execute(self.decisions([('Relevant work', 'include'), ('Off topic work', 'exclude')]))
        self.assertEqual(code, 2)
        self.assertEqual(len(self.acquired), 1)
        excluded = [e for e in engine.state['corpus_exclusions'] if e['reason'] == 'excluded_by_screening']
        self.assertEqual([(e['title'], e['detail']) for e in excluded], [('Off topic work', 'motivo exclude')])
        self.assertTrue(any(e['reason'] == 'duplicate_content' for e in engine.state['corpus_exclusions']))

    def test_screening_respects_the_source_limit_and_the_current_candidates(self):
        self.execute()
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            contract = read_json(self.folder / 'research-contract.json'); contract['budgets']['max_sources'] = 1
            state['contract_hash'] = digest(contract)
            store.commit(state, {'research-contract.json': contract})
        code, engine = self.execute(self.decisions([('Relevant work', 'include'), ('Off topic work', 'include')]))
        self.assertEqual((code, engine.state['legacy_signals'], engine.state['integrity']['status']), (2, ['screening_invalid'], 'pending'))
        stale = dict(self.decisions([('Relevant work', 'exclude')]), sources_hash='0' * 64)
        code, engine = self.execute(stale)
        self.assertEqual(engine.state['legacy_signals'], ['screening_outdated'])
        self.assertEqual(self.acquired, [])

    def test_check_validates_screening_without_writing(self):
        self.execute()
        path = self.folder.parent / 'screening.json'
        path.write_text(json.dumps(self.decisions([('Relevant work', 'include')])), encoding='utf-8')
        before = (self.folder / 'events.jsonl').read_bytes()
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main(['continue', str(self.folder), '--screening', str(path), '--check', '--json'])
        self.assertEqual((code, json.loads(output.getvalue())['decisions']), (0, 1))
        self.assertEqual(before, (self.folder / 'events.jsonl').read_bytes())


class GapAndMetricTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine
    review = test_engine.EngineTests.review

    def test_answer_explains_why_each_missing_scope_is_missing_and_counts_questions(self):
        from ez.metrics import collect
        from ez.presenter import render
        self.run_engine()
        self.assertEqual(self.run_engine(self.review())[0], 0)
        report = read_json(self.folder / 'answer.json')
        self.assertEqual(report['gaps'], [{'scope_id': 'sq2', 'question': 'Otra pregunta',
                                           'causes': [{'cause': 'required_source_not_found', 'source_id': 'missing'}]}])
        self.assertIn('Qué falta y por qué', render(report))
        self.assertEqual(collect(self.folder)['notebooklm_questions'], 2)


class DedupeTests(unittest.TestCase):
    def test_dedupe_is_transitive_and_independent_of_arrival_order(self):
        rows = [{'title': 'FAIR', 'doi': '10.1038/X'}, {'title': 'FAIR', 'pmid': '261'},
                {'title': 'FAIR', 'doi': 'https://doi.org/10.1038/x', 'pmid': 'PMID: 261'}, {'title': 'Other', 'pmcid': '5'}]
        results = []
        for order in ([0, 1, 2, 3], [3, 2, 1, 0], [1, 3, 0, 2]):
            merged = search_topic.dedupe_records([dict(rows[i]) for i in order])
            results.append(sorted(json.dumps(r, sort_keys=True) for r in merged))
        self.assertEqual(len(results[0]), 2)
        self.assertTrue(all(r == results[0] for r in results))
        self.assertTrue(search_topic.same_identity({'pmcid': '5'}, {'pmcid': 'PMC5'}))


if __name__ == '__main__':
    unittest.main()
