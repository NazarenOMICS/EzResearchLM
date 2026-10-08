"""Round 7: open access in screening, early PDF requests, pages, bibliography export, estimates and onboarding."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.engine import Engine
from ez.state import Store, lock, read_json
import test_engine
import test_screening


class OpenAccessTests(unittest.TestCase):
    setUp = test_screening.ScreeningTests.setUp
    setUp_base = test_engine.EngineTests.setUp

    def test_screening_candidates_say_whether_they_are_open_access(self):
        self.service.discovery_records = [{'title': 'Abierto', 'doi': '10.1/aoa'}, {'title': 'Pago', 'doi': '10.1/paid'}]
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(self.folder, runner=self.service).execute(), 2)
        request = read_json(self.folder / 'screening-request.json')
        self.assertEqual({c['doi']: c['open_access'] for c in request['candidates']}, {'10.1/aoa': 'yes', '10.1/paid': 'no'})
        self.assertEqual(request['sources_hash'], Store(self.folder).state()['sources_hash'])
        lookups = sum(a[1:3] == ['-m', 'ez.openaccess'] for a in self.service.calls)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            Engine(self.folder, runner=self.service).execute()
        self.assertEqual(sum(a[1:3] == ['-m', 'ez.openaccess'] for a in self.service.calls), lookups)


    def test_openalex_batches_are_parsed_and_failures_stay_unknown(self):
        from ez.openaccess import lookup
        class Response:
            status_code = 200
            def json(self):
                return {'results': [{'doi': 'https://doi.org/10.1/A', 'open_access': {'is_oa': True, 'oa_status': 'green'}}]}
        class Session:
            urls = []
            def get(self, url, **kwargs):
                self.urls.append(url)
                return Response()
        session = Session()
        self.assertEqual(lookup(['10.1/a', '10.1/b'], session), {'10.1/a': {'is_oa': True, 'oa_status': 'green'}})
        self.assertEqual(len(session.urls), 1)


class PageTests(unittest.TestCase):
    def test_a_passage_is_found_on_its_page_despite_hyphenation_and_spacing(self):
        from ez.pages import find_page, page_text
        pages = [page_text(text) for text in (
            'Introduction. Corynebacterium glutamicum is a model organism.',
            'Results. Ethambutol treatment led to an increased L-gluta-\nmate efflux in CGXII medium after 2 h.')]
        self.assertEqual(find_page('Ethambutol treatment led to an increased L-glutamate efflux in CGXII medium', pages), 2)
        self.assertEqual(find_page('increased L-glutamate efflux in CGXII medium after', pages), 2)
        self.assertIsNone(find_page('Nothing like this appears anywhere in the document text', pages))
        self.assertIsNone(find_page('demasiado corto', pages))

    def test_the_report_shows_the_page_next_to_the_source_number(self):
        from ez.deliver import report_markdown
        claim = {'id': 'qa1-1', 'text': 'Afirmación.', 'scope_ids': ['sq1'],
                 'references': [{'source_id': 'r1', 'cited_text': 'pasaje', 'role': 'qa', 'page': 7}]}
        text = report_markdown({'answer': {'status': 'complete'}, 'claims': [claim], 'contract_hash': 'c', 'corpus_hash': 'k',
                                'delivery': 'direct'}, {'question': {'original': 'P'}, 'scope': [{'id': 'sq1', 'question': 'P'}]},
                               {'run_id': 'r'})
        self.assertIn('[1, p. 7]: «pasaje»', text)


class ExportTests(unittest.TestCase):
    def test_bibtex_and_ris_carry_only_recorded_metadata(self):
        from ez.deliver import export_bibliography
        sources = [{'source_id': 's1', 'title': 'Ethambutol elicits L-glutamate efflux', 'authors': ['Radmacher E', 'Stansen KC'],
                    'year': 2005, 'journal': 'Microbiology', 'doi': '10.1099/mic.0.27804-0', 'pmid': '15870446'},
                   {'source_id': 's2', 'title': 'Otro', 'authors': 'Radmacher, Eva', 'year': 2005}]
        bib = export_bibliography(sources)
        self.assertIn('@article{radmacher2005,', bib)
        self.assertIn('@article{radmacher2005a,', bib)
        self.assertIn('  doi = {10.1099/mic.0.27804-0}', bib)
        self.assertIn('  author = {Radmacher E and Stansen KC}', bib)
        ris = export_bibliography(sources, 'ris')
        self.assertIn('DO  - 10.1099/mic.0.27804-0', ris)
        self.assertEqual(ris.count('ER  - '), 2)

    def test_export_command_writes_the_cited_sources(self):
        engine_case = test_engine.EngineTests('run_engine')
        engine_case.setUp()
        self.addCleanup(engine_case.temp.cleanup)
        engine_case.run_engine(); engine_case.run_engine(engine_case.review())
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main(['--root', engine_case.temp.name, 'export', str(engine_case.folder), '--json'])
        result = json.loads(output.getvalue())
        self.assertEqual((code, result['sources']), (0, 1))
        self.assertIn('Fuente de prueba', Path(result['path']).read_text(encoding='utf-8'))


class EstimateTests(unittest.TestCase):
    def test_estimate_follows_the_measured_minute_per_question(self):
        from ez.contracts import estimate
        contract = {'plan': {'notebook_questions': [{}] * 4}}
        fresh, reused = estimate(contract), estimate(contract, reused=True)
        self.assertEqual(fresh['notebooklm_questions'], 4)
        self.assertEqual(fresh['minutes'], [6, 11])
        self.assertLess(reused['minutes'][1], fresh['minutes'][1])
        self.assertIn('alrededor de un minuto', fresh['text'])


class OnboardingTests(unittest.TestCase):
    def test_setup_lists_the_first_use_steps_and_the_next_one(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=False):
            for key in ('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL', 'UNPAYWALL_EMAIL'):
                os.environ.pop(key, None)
            output = StringIO()
            with redirect_stdout(output), patch('ez.cli.load_environment'), patch('ez.setup.executable', return_value=None):
                main(['--root', str(Path(temp) / 'runs'), 'setup', '--check', '--json'])
            value = json.loads(output.getvalue())
        self.assertEqual([s['id'] for s in value['onboarding']],
                         ['notebooklm_installed', 'notebooklm_login', 'unpaywall_email', 'first_question'])
        self.assertEqual((value['next_step']['id'], value['next_step']['who']), ('notebooklm_installed', 'EZ'))
        from ez.presenter import render
        self.assertIn('1. [pendiente]', render(value))


class ScorerTests(unittest.TestCase):
    def test_the_gold_set_scorer_reads_a_run_and_reports_only_ids_and_counts(self):
        import importlib.util
        path = Path(__file__).resolve().parents[1] / 'gold_set_benchmark' / 'puntuar.py'
        spec = importlib.util.spec_from_file_location('puntuar', path)
        puntuar = importlib.util.module_from_spec(spec); spec.loader.exec_module(puntuar)
        case = test_engine.EngineTests('run_engine')
        case.setUp()
        self.addCleanup(case.temp.cleanup)
        case.run_engine(); case.run_engine(case.review())
        with lock(case.folder):
            store = Store(case.folder); state = store.state()
            sources = read_json(case.folder / 'sources.json')
            sources[0]['doi'] = '10.1099/mic.0.27804-0'
            from ez.contracts import digest
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})
        result = puntuar.score(case.folder, 'M2')
        radmacher = next(a for a in result['articles'] if a[0] == '10.1099/mic.0.27804-0')
        self.assertEqual(radmacher[2], 'en el corpus, no citado')
        self.assertEqual(len(result['articles']), 10)
        self.assertEqual(result['operation']['afirmaciones entregadas'], 1)
        text = puntuar.markdown(result, 'M2', 'r')
        self.assertNotIn('Afirmación de prueba', text)


if __name__ == '__main__':
    unittest.main()
