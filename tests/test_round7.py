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


class KeyPdfTests(unittest.TestCase):
    setUp = test_screening.ScreeningTests.setUp
    setUp_base = test_engine.EngineTests.setUp
    runner = test_screening.ScreeningTests.runner

    def screen(self, key_doi):
        self.service.discovery_records = [{'title': 'Artículo abierto', 'doi': '10.1/aoa'},
                                          {'title': 'Artículo central pago', 'doi': '10.1/paid', 'year': 2005}]
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            Engine(self.folder, runner=self.runner).execute()
        request = read_json(self.folder / 'screening-request.json')
        decisions = [{'source_id': c['source_id'], 'decision': 'include', 'reason': 'Pertinente', 'key': c['doi'] == key_doi}
                     for c in request['candidates']]
        screening = {'schema_version': '2.0', 'sources_hash': request['sources_hash'], 'decisions': decisions}
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            return Engine(self.folder, runner=self.runner).execute(screening=screening)

    def test_a_closed_key_work_is_requested_before_any_download(self):
        self.assertEqual(self.screen('10.1/paid'), 2)
        state = read_json(self.folder / 'run-state.json')
        self.assertEqual(state['legacy_signals'], ['NEEDS_KEY_PDFS'])
        text = (self.folder / 'key-pdfs.md').read_text(encoding='utf-8')
        self.assertIn('**Artículo central pago**', text)
        self.assertIn('**Artículo central pago** (2005) — DOI [10.1/paid](https://doi.org/10.1/paid)', text)
        self.assertEqual(state['missing_pdfs'][0]['doi_url'], 'https://doi.org/10.1/paid')
        self.assertEqual([c['label'] for c in state['choices']][:2], ['Ya dejé los PDFs en la bandeja', 'Seguir sin ellos'])
        self.assertIn('préstamo interbibliotecario', text)
        self.assertEqual(self.acquired, [])
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'), \
                patch('ez.engine.Engine.__init__.__defaults__', (self.runner,)), patch('ez.engine.executable', return_value='notebooklm'):
            main(['--root', self.temp.name, 'continue', str(self.folder), '--skip-missing', '--json'])
        state = read_json(self.folder / 'run-state.json')
        self.assertTrue(state['key_pdfs_acknowledged'])
        self.assertFalse(state.get('missing_pdfs_acknowledged'))
        self.assertEqual(len(self.acquired), 2)

    def test_open_key_works_do_not_stop_the_run(self):
        self.screen('10.1/aoa')
        self.assertNotIn('NEEDS_KEY_PDFS', read_json(self.folder / 'run-state.json')['legacy_signals'])
        self.assertFalse((self.folder / 'key-pdfs.md').exists())
        self.assertEqual(len(self.acquired), 2)


class WorkspaceTests(unittest.TestCase):
    setUp = test_screening.ScreeningTests.setUp
    setUp_base = test_engine.EngineTests.setUp
    runner = test_screening.ScreeningTests.runner
    screen = KeyPdfTests.screen

    def test_each_project_gets_an_inbox_reports_and_an_index(self):
        state = Store(self.folder).state()
        inbox = Path(state['workspace']['inbox'])
        self.assertEqual(inbox, Path(self.temp.name).resolve() / 'projects' / 'general' / 'inbox')
        self.assertTrue((inbox / 'README.md').exists())
        self.assertTrue(state['workspace']['inbox_link'].startswith('file://'))
        self.assertIn('Inbox for your PDFs', (inbox.parent / 'README.md').read_text(encoding='utf-8'))

    def test_a_pdf_left_in_the_inbox_is_taken_before_downloading(self):
        from PyPDF2 import PdfWriter
        inbox = Path(Store(self.folder).state()['workspace']['inbox'])
        writer = PdfWriter(); writer.add_blank_page(width=90, height=90)
        with (inbox / 'articulo-central.pdf').open('wb') as stream:
            writer.write(stream)
        verified = lambda path, record, provider=None: 'verified' if record.get('doi') == '10.1/paid' else 'needs_review'
        with patch('ez.acquisition.verify_identity', verified):
            self.screen('10.1/paid')
        state = read_json(self.folder / 'run-state.json')
        self.assertNotIn('NEEDS_KEY_PDFS', state['legacy_signals'])
        self.assertEqual([i['file'] for i in state['inbox_import']['imported']], ['articulo-central.pdf'])
        paid = next(s for s in read_json(self.folder / 'sources.json') if s.get('doi') == '10.1/paid')
        self.assertEqual((paid['identity_status'], paid['provenance']['origin']), ('verified', 'project inbox'))
        self.assertEqual(len(self.acquired), 1)
        self.assertTrue((inbox / 'articulo-central.pdf').exists())

    def test_an_uncertain_inbox_match_asks_for_identity_confirmation(self):
        from PyPDF2 import PdfWriter
        inbox = Path(Store(self.folder).state()['workspace']['inbox'])
        writer = PdfWriter(); writer.add_blank_page(width=91, height=91)
        with (inbox / '10.1_paid.pdf').open('wb') as stream:
            writer.write(stream)
        with patch('ez.acquisition.verify_identity', lambda *a, **k: 'needs_review'):
            self.screen('10.1/paid')
        state = read_json(self.folder / 'run-state.json')
        self.assertEqual(state['legacy_signals'], ['NEEDS_IDENTITY_CONFIRMATION'])
        self.assertIn('Artículo central pago', state['next_action'])
        self.assertEqual(self.acquired, [])


class PublishTests(unittest.TestCase):
    def test_each_delivery_lands_in_the_project_reports_with_its_bibliography_and_index(self):
        import test_v6_rules
        case = test_v6_rules.DirectDeliveryTests('test_direct_delivery_needs_no_review_and_no_second_query')
        case.setUp()
        self.addCleanup(case.temp.cleanup)
        self.assertEqual(case.run_engine()[0], 0)
        project = Path(case.temp.name).resolve() / 'projects' / 'general'
        reports = sorted((project / 'reports').glob('*.md'))
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0].read_text(encoding='utf-8'), (case.folder / 'report.md').read_text(encoding='utf-8'))
        self.assertTrue(reports[0].with_suffix('.bib').exists())
        index = (project / 'README.md').read_text(encoding='utf-8')
        self.assertIn('[open](' + reports[0].as_uri() + ')', index)
        self.assertIn('Pregunta de prueba', index)
        self.assertEqual(Store(case.folder).state()['workspace']['report_link'], reports[0].as_uri())


class ProjectLibraryTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine

    def second_run(self, plan=None):
        from ez.cli import create_run
        from ez.contracts import digest
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            sources = read_json(self.folder / 'sources.json')
            sources[0]['doi'] = '10.1/s1'
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})
        self.run_engine()
        contract = read_json(self.folder / 'research-contract.json')
        contract['plan'].update(plan or {})
        folder, _ = create_run(Path(self.temp.name), 'Otra pregunta del mismo proyecto', {}, contract)
        return folder

    def execute(self, folder, screening=None):
        with lock(folder), patch('ez.engine.executable', return_value='notebooklm'):
            return Engine(folder, runner=self.service).execute(screening=screening)

    def test_a_work_already_verified_in_the_project_is_copied_not_downloaded(self):
        folder = self.second_run()
        self.service.discovery_records = [{'title': 'Fuente de prueba', 'doi': '10.1/s1'}]
        self.assertEqual(self.execute(folder), 2)
        request = read_json(folder / 'screening-request.json')
        self.assertTrue(request['candidates'][0]['in_project'])
        screening = {'schema_version': '2.0', 'sources_hash': request['sources_hash'],
                     'decisions': [{'source_id': request['candidates'][0]['source_id'], 'decision': 'include', 'reason': 'Clave'}]}
        self.execute(folder, screening)
        source = read_json(folder / 'sources.json')[0]
        self.assertEqual((source['identity_status'], source['reused_from']['project_library']), ('verified', True))
        self.assertTrue(Path(source['pdf_path']).is_relative_to(folder))
        self.assertFalse(any(a[1:3] == ['-m', 'ez.acquisition'] for a in self.service.calls))
        self.assertEqual(self.service.upload_count, 1)

    def test_a_reuse_only_plan_answers_from_the_project_library(self):
        folder = self.second_run({'discovery_mode': 'reuse_only', 'queries': []})
        self.assertEqual(self.execute(folder), 2)
        sources = read_json(folder / 'sources.json')
        self.assertEqual([s['doi'] for s in sources], ['10.1/s1'])
        self.assertEqual(Store(folder).state()['phase'], 'audit')

    def test_a_follow_up_question_is_answered_from_the_project_library(self):
        import test_v6_rules
        self.second_run()
        service = self.service
        def answering(args, **kwargs):
            result = service(args, **kwargs)
            if args[1] == 'ask':
                value = json.loads(result.stdout); value['answer'] = test_v6_rules.ANSWER
                from ez.process import Result
                return Result(0, json.dumps(value), '', None)
            return result
        uploads = self.service.upload_count
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'), \
                patch('ez.engine.Engine.__init__.__defaults__', (answering,)), patch('ez.engine.executable', return_value='notebooklm'):
            code = main(['--root', self.temp.name, 'ask', '¿Qué dice la fuente?', '--json'])
        value = json.loads(output.getvalue())
        self.assertEqual((code, value['kind'], value['claims'][0]['marker']), (0, 'ask', '[EZ:ask1-1]'))
        self.assertEqual(self.service.upload_count, uploads)
        self.assertFalse(any(a[1:3] in (['-m', 'ez.discovery'], ['-m', 'ez.acquisition']) for a in self.service.calls[-6:]))
        self.assertEqual([c['label'] for c in value['choices']][0], 'Verificar lo central para redactar')

    def test_projects_are_listed_and_ranked_against_a_new_question(self):
        self.second_run()
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            main(['--root', self.temp.name, 'projects', '--suggest', 'Pregunta de prueba sobre fuentes', '--json'])
        value = json.loads(output.getvalue())
        row = value['projects'][0]
        self.assertEqual((row['project'], row['researches'], row['library_pdfs']), ('general', 2, 1))
        self.assertGreaterEqual(row['relatedness'], 0.3)
        self.assertIn('parece parte del proyecto «general»', value['next_action'])


class MigrationTests(unittest.TestCase):
    def test_spanish_folders_of_earlier_versions_are_renamed_in_place(self):
        import tempfile
        from ez.workspace import ensure
        with tempfile.TemporaryDirectory() as temp:
            old = Path(temp) / 'proyectos' / 'tesis'
            (old / 'bandeja').mkdir(parents=True); (old / 'informes').mkdir()
            (old / 'bandeja' / 'mio.pdf').write_bytes(b'%PDF-1.4')
            (old / 'LEEME.md').write_text('viejo', encoding='utf-8')
            paths = ensure(Path(temp) / 'runs', 'tesis')
            new = Path(temp).resolve() / 'projects' / 'tesis'
            self.assertEqual(Path(paths['inbox']), new / 'inbox')
            self.assertTrue((new / 'inbox' / 'mio.pdf').exists())
            self.assertTrue((new / 'README.md').exists())
            self.assertFalse((Path(temp) / 'proyectos').exists())


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
