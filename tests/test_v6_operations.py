"""Refactor v6, operations: download diagnostics, Unpaywall setup, batch PDF import and background jobs."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.contracts import digest
from ez.engine import Engine
from ez.process import Result
from ez.state import Store, atomic_json, lock, read_json
import test_engine
import test_phase1


class DownloadDiagnosticsTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def test_failed_downloads_report_each_route_tried(self):
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            sources = read_json(self.folder / 'sources.json')
            sources.append({'source_id': 'paid', 'title': 'Artículo pago', 'doi': '10.1/paid', 'acquisition_status': 'pending',
                            'screening': 'include', 'validation_status': 'unknown', 'identity_status': 'unknown',
                            'notebook_status': 'pending'})
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})
        def run(args, **kwargs):
            if args[1:3] == ['-m', 'ez.acquisition']:
                record = read_json(args[args.index('--record') + 1])
                atomic_json(args[args.index('--output') + 1], dict(
                    record, acquisition_status='manual_needed', validation_status='unknown', failure_code='routes_exhausted',
                    acquisition_input_hash=digest(record),
                    attempts=[{'provider': 'doi', 'result': 'failed', 'failure_code': 'http_403'},
                              {'provider': 'unpaywall', 'result': 'skipped', 'failure_code': 'missing_email'},
                              {'provider': 'openalex', 'result': 'failed', 'failure_code': 'html_instead_of_pdf'}]))
                return Result(0, '', '', None)
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(self.folder, runner=run).execute(), 2)
        # EZ first asks for the PDFs it could not download, before uploading anything.
        state = read_json(self.folder / 'run-state.json')
        self.assertEqual(state['legacy_signals'], ['NEEDS_USER_PDFS'])
        self.assertIn('https://doi.org/10.1/paid', (self.folder / 'pdf-request.md').read_text(encoding='utf-8'))
        self.assertEqual(self.service.upload_count, 0)
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'), \
                patch('ez.engine.Engine.__init__.__defaults__', (run,)), patch('ez.engine.executable', return_value='notebooklm'):
            main(['--root', self.temp.name, 'continue', str(self.folder), '--skip-missing', '--json'])
        self.assertEqual(self.service.upload_count, 1)
        exclusion = next(e for e in read_json(self.folder / 'run-state.json')['corpus_exclusions'] if e['source_id'] == 'paid')
        self.assertEqual(exclusion['routes'], [{'provider': 'doi', 'failure_code': 'http_403'},
                                               {'provider': 'unpaywall', 'failure_code': 'missing_email'},
                                               {'provider': 'openalex', 'failure_code': 'html_instead_of_pdf'}])
        from ez.metrics import collect
        self.assertEqual(collect(self.folder)['download_routes_failed']['unpaywall:missing_email'], 1)

    def test_indexes_without_any_open_location_are_named(self):
        from ez.engine import routes_tried
        source = {'attempts': [{'provider': 'core', 'result': 'failed', 'failure_code': 'rate_limited'}],
                  'routes_consulted': {'openalex': 0, 'unpaywall': 0, 'core': 0, 'europepmc': 2}}
        self.assertEqual(routes_tried(source), [{'provider': 'core', 'failure_code': 'rate_limited'},
                                                {'provider': 'openalex', 'failure_code': 'no_open_access_location'},
                                                {'provider': 'unpaywall', 'failure_code': 'no_open_access_location'}])


class UnpaywallSetupTests(unittest.TestCase):
    def test_setup_saves_the_contact_email_and_later_commands_load_it(self):
        import tempfile
        from ez.paths import load_user_config
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {}, clear=False):
            for key in ('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL', 'UNPAYWALL_EMAIL'):
                os.environ.pop(key, None)
            root = Path(temp) / 'runs'
            output = StringIO()
            with redirect_stdout(output), patch('ez.cli.load_environment'), patch('ez.setup.executable', return_value=None):
                self.assertEqual(main(['--root', str(root), 'setup', '--unpaywall-email', 'tesista@example.org', '--json']), 0)
            self.assertTrue(json.loads(output.getvalue())['unpaywall_configured'])
            self.assertEqual(read_json(Path(temp) / 'ez-config.json')['unpaywall_email'], 'tesista@example.org')
            os.environ.pop('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL')
            load_user_config(root)
            self.assertEqual(os.environ['PAPER_SEARCH_MCP_UNPAYWALL_EMAIL'], 'tesista@example.org')
            with redirect_stdout(StringIO()), patch('ez.cli.load_environment'), patch('ez.setup.executable', return_value=None):
                self.assertEqual(main(['--root', str(root), 'setup', '--unpaywall-email', 'no-es-un-correo', '--json']), 1)


class BatchImportTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    add_source = test_phase1.Phase1Tests.add_source

    def cli(self, *arguments):
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main(['--root', self.temp.name, *arguments, '--json'])
        return code, json.loads(output.getvalue())

    def test_a_folder_of_pdfs_is_matched_to_the_missing_sources(self):
        from PyPDF2 import PdfWriter
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            sources = read_json(self.folder / 'sources.json')
            sources += [{'source_id': sid, 'title': 'Artículo ' + sid, 'doi': '10.1/' + sid, 'acquisition_status': 'manual_needed',
                         'screening': 'include', 'validation_status': 'unknown', 'identity_status': 'unknown',
                         'notebook_status': 'pending'} for sid in ('p1', 'p2')]
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})
        library = Path(self.temp.name) / 'mis-pdfs'
        library.mkdir()
        for index, name in enumerate(('p1.pdf', 'otro.pdf', '10.1_p2.pdf')):
            writer = PdfWriter(); writer.add_blank_page(width=80 + index, height=80)
            with (library / name).open('wb') as stream:
                writer.write(stream)
        fake = lambda path, record, provider=None: 'verified' if Path(path).stem == record['source_id'] else 'needs_review'
        with patch('ez.acquisition.verify_identity', fake):
            code, result = self.cli('rescue', str(self.folder), '--import-folder', str(library))
        self.assertEqual(code, 0)
        summary = result['import_folder']
        self.assertEqual(([i['source_id'] for i in summary['imported']], summary['unmatched_files']), (['p1'], ['otro.pdf']))
        # A DOI in the filename imports the PDF but leaves its identity for a quick confirmation.
        self.assertEqual([i['source_id'] for i in summary['needs_identity_confirmation']], ['p2'])
        self.assertEqual(summary['still_missing'], [])
        p2 = next(s for s in read_json(self.folder / 'sources.json') if s['source_id'] == 'p2')
        self.assertEqual((p2['validation_status'], p2['identity_status']), ('valid', 'needs_review'))
        p1 = next(s for s in read_json(self.folder / 'sources.json') if s['source_id'] == 'p1')
        self.assertEqual((p1['validation_status'], p1['identity_status']), ('valid', 'verified'))

    def test_several_identities_are_confirmed_at_once(self):
        self.add_source('s2', identity='needs_review')
        self.add_source('s3', identity='needs_review')
        code, _ = self.cli('rescue', str(self.folder), '--source', 's2,s3', '--confirm-identity', '--reviewer', 'host_agent')
        self.assertEqual(code, 0)
        status = {s['source_id']: s['identity_status'] for s in read_json(self.folder / 'sources.json')}
        self.assertEqual((status['s2'], status['s3']), ('verified', 'verified'))
        self.assertEqual(self.cli('rescue', str(self.folder), '--source', 's2,s3', '--retry')[0], 4)


if __name__ == '__main__':
    unittest.main()
