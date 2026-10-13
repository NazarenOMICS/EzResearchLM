"""Failures of the live test of 2026-10-12, reproduced offline before fixing them (docs/evaluation/prueba-en-vivo-2026-10-12.md)."""
from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.contracts import digest
from ez.engine import Engine, Pause
from ez.process import Result
from ez.state import Store, atomic_json, lock, read_json
import test_engine


def call(*argv, env=None):
    output = StringIO()
    with redirect_stdout(output), patch('ez.cli.load_environment'), patch.dict(os.environ, env or {}):
        code = main([*argv, '--json'])
    return code, json.loads(output.getvalue().strip().splitlines()[-1])


def pdf_with_quirks():
    """A one-page PDF with a repeated /MediaBox key, as a publisher's PDF in the live test had."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /MediaBox [0 0 612 792] >>']
    data, offsets = bytearray(b'%PDF-1.4\n'), []
    for number, body in enumerate(objects, 1):
        offsets.append(len(data))
        data += b'%d 0 obj\n' % number + body + b'\nendobj\n'
    xref = len(data)
    data += b'xref\n0 4\n0000000000 65535 f \n' + b''.join(b'%010d 00000 n \n' % o for o in offsets)
    data += b'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % xref
    return bytes(data)


class PublisherPdfsAreValid(unittest.TestCase):
    def test_a_readable_pdf_with_spec_quirks_is_valid_and_garbage_is_not(self):
        from ez.pdf import validate_pdf
        with tempfile.TemporaryDirectory() as temp:
            quirky, broken = Path(temp) / 'quirky.pdf', Path(temp) / 'broken.pdf'
            quirky.write_bytes(pdf_with_quirks())
            broken.write_bytes(b'%PDF-1.4\nnot really a pdf at all\n')
            self.assertEqual(validate_pdf(quirky)['status'], 'valid')
            self.assertEqual(validate_pdf(broken)['status'], 'invalid')


class RateLimitedHostsAreSharedAcrossSources(unittest.TestCase):
    def test_a_429_from_core_stops_the_next_source_from_asking_again(self):
        from ez.acquisition import Retriever

        class Response:
            status_code, headers = 429, {'Retry-After': 'later', 'Content-Type': 'text/html'}
            def iter_content(self, size):
                return iter([b'slow down'])
            def close(self):
                pass

        class Session:
            def __init__(self):
                self.headers, self.calls = {}, 0
            def get(self, *args, **kwargs):
                self.calls += 1
                return Response()

        with tempfile.TemporaryDirectory() as temp:
            url = 'https://api.core.ac.uk/v3/search/works/?q=x'
            first = Session()
            Retriever(Path(temp) / 'acquisition' / 's1', 's1', session=first, check_url=lambda u: None).request(url, 'core')
            second = Session()
            again = Retriever(Path(temp) / 'acquisition' / 's2', 's2', session=second, check_url=lambda u: None)
            self.assertEqual(again.request(url, 'core'), (None, None))
            self.assertEqual((first.calls, second.calls), (1, 0))
            self.assertEqual(again.history[-1]['failure_code'], 'circuit_open')


class MissingPdfsOnlyStopForKeyWorks(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def add_paid(self, key):
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            sources = read_json(self.folder / 'sources.json')
            sources.append({'source_id': 'paid', 'title': 'Artículo pago', 'doi': '10.1/paid', 'acquisition_status': 'pending',
                            'screening': 'include', 'validation_status': 'unknown', 'identity_status': 'unknown',
                            'notebook_status': 'pending', **({'key': True} if key else {})})
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})

    def run_with_failed_download(self):
        def run(args, **kwargs):
            if args[1:3] == ['-m', 'ez.acquisition']:
                record = read_json(args[args.index('--record') + 1])
                atomic_json(args[args.index('--output') + 1], dict(
                    record, acquisition_status='manual_needed', validation_status='unknown', failure_code='routes_exhausted',
                    acquisition_input_hash=digest(record)))
                return Result(0, '', '', None)
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            Engine(self.folder, runner=run).execute()
        return read_json(self.folder / 'run-state.json')

    def test_a_missing_ordinary_work_is_listed_but_does_not_stop_the_research(self):
        # The live test stopped for 21 PDFs and turned the person into the downloader.
        self.add_paid(key=False)
        state = self.run_with_failed_download()
        self.assertNotIn('NEEDS_USER_PDFS', state['legacy_signals'])
        self.assertGreater(self.service.upload_count, 0)
        self.assertIn('https://doi.org/10.1/paid', (self.folder / 'pdf-request.md').read_text(encoding='utf-8'))

    def test_a_missing_key_work_still_asks_the_person(self):
        self.add_paid(key=True)
        state = self.run_with_failed_download()
        self.assertEqual(state['legacy_signals'], ['NEEDS_USER_PDFS'])
        self.assertEqual(self.service.upload_count, 0)


class LongCommandsOutliveTheAgentsTerminal(unittest.TestCase):
    def test_continue_runs_in_a_detached_worker_and_reports_its_result(self):
        from ez.cli import create_run
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'runs'
            folder, _ = create_run(root, 'Pregunta sin plan', {}, None)
            env = {'EZRESEARCH_FOREGROUND': ''}
            with patch('ez.cli.spawn_worker', wraps=__import__('ez.cli', fromlist=['spawn_worker']).spawn_worker) as spawned:
                code, value = call('--root', str(root), 'continue', str(folder), env=env)
            self.assertEqual(spawned.call_count, 1)
            self.assertEqual(code, 2)
            self.assertIn('NEEDS_PLAN', value['legacy_signals'])

    def test_a_worker_still_busy_returns_at_once_and_says_how_to_wait(self):
        import ez.cli

        class Busy:
            pid, returncode = 4242, None
            def poll(self):
                return None

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'runs'
            folder, _ = ez.cli.create_run(root, 'Pregunta', {}, None)
            with patch('ez.cli.spawn_worker', return_value=(Busy(), Path(temp) / 'w.log')), patch('ez.cli.FOREGROUND_SECONDS', 0):
                code, value = call('--root', str(root), 'continue', str(folder), env={'EZRESEARCH_FOREGROUND': ''})
            self.assertEqual((code, value['running']), (0, True))
            self.assertIn('ez wait', value['next_action'])
            self.assertIn('no cierres', value['next_action'])


class DeadRunsAreNamed(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def mark_running(self):
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            state.update(phase='qa', execution={'status': 'running'})
            store.update(state)

    def test_wait_and_status_say_the_process_stopped(self):
        # Eleven hours after the process died, ez wait still said «quedan 4 preguntas».
        self.mark_running()
        code, waited = call('--root', self.temp.name, 'wait', str(self.folder), '--seconds', '1')
        self.assertTrue(waited['stopped'])
        self.assertIn('ez continue', waited['next_action'])
        code, status = call('--root', self.temp.name, 'status', str(self.folder))
        self.assertTrue(status['stopped'])
        self.assertIn('ez continue', status['next_action'])


class ReadsDoNotNeedTheWriterLock(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def test_status_answer_and_draft_report_a_busy_run_instead_of_failing(self):
        with lock(self.folder):
            code, status = call('--root', self.temp.name, 'status', str(self.folder), '--answer')
            self.assertEqual((code, status['running']), (0, True))
            self.assertIn('ez wait', status['next_action'])
            code, drafted = call('--root', self.temp.name, 'draft', str(self.folder))
            self.assertIn('ez wait', drafted['next_action'])
            self.assertNotIn('escritor activo', drafted['next_action'])

    def test_the_lock_message_says_to_wait_not_that_something_broke(self):
        from ez.contracts import ContractError
        with lock(self.folder), self.assertRaisesRegex(ContractError, 'ez wait'):
            with lock(self.folder):
                pass


class RunIdsResolveUnderTheRoot(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def test_wait_finds_the_run_by_id_from_any_folder_and_creates_nothing(self):
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        before = os.getcwd()
        os.chdir(elsewhere.name)
        self.addCleanup(os.chdir, before)
        code, value = call('--root', self.temp.name, 'wait', self.folder.name, '--seconds', '1')
        self.assertEqual(Path(value['run']), self.folder)
        self.assertEqual(os.listdir(elsewhere.name), [])

    def test_probing_a_missing_folder_does_not_create_it(self):
        from ez.cli import run_busy
        missing = Path(self.temp.name) / 'ez-nope'
        run_busy(missing)
        self.assertFalse(missing.exists())


class NotebookSessionRenewsItself(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def test_an_expired_session_is_renewed_once_and_the_call_retried(self):
        replies = [Result(1, '', 'Error: not authenticated', None), Result(0, json.dumps({'notebooks': []}), '', None)]
        engine = Engine(self.folder, runner=lambda args, **kw: replies.pop(0))
        with patch('ez.engine.executable', return_value='notebooklm'), patch('ez.setup.renew_session', return_value=True) as renewed:
            self.assertEqual(engine.notebook(['list']), {'notebooks': []})
        self.assertEqual(renewed.call_count, 1)

    def test_a_session_that_cannot_be_renewed_asks_for_the_login(self):
        engine = Engine(self.folder, runner=lambda args, **kw: Result(1, '', 'Error: not authenticated', None))
        with patch('ez.engine.executable', return_value='notebooklm'), patch('ez.setup.renew_session', return_value=False), \
                self.assertRaises(Pause) as raised:
            engine.notebook(['list'])
        self.assertEqual(raised.exception.reason, 'auth_required')
        self.assertIn('ez setup --login', str(raised.exception.args))

    def test_a_login_that_finishes_by_itself_is_reported_as_renewed(self):
        import ez.setup
        with tempfile.TemporaryDirectory() as temp:
            status = Path(temp) / 'login.json'

            def popen(*args, **kwargs):
                atomic_json(status, {'state': 'ready', 'finished_at': 'now'})

            with patch('ez.setup.executable', return_value='notebooklm'), patch('ez.setup.notebooklm_python', return_value='py'), \
                    patch('ez.setup.run', return_value=Result(1, '', 'not authenticated', None)), \
                    patch('ez.setup.LOGIN_STATUS', status), patch('subprocess.Popen', side_effect=popen):
                value = ez.setup.start_login(wait_seconds=2)
        self.assertEqual(value['login_status'], 'ready')
        self.assertIn('sin que', value['next_action'])

    def test_check_does_not_report_an_old_ready_login_as_current(self):
        from ez.setup import prepare
        with tempfile.TemporaryDirectory() as temp:
            status = Path(temp) / 'login.json'
            atomic_json(status, {'state': 'ready', 'finished_at': 'yesterday'})
            with patch('ez.setup.LOGIN_STATUS', status), patch('ez.setup.executable', return_value='notebooklm'), \
                    patch('ez.setup.run', return_value=Result(1, '', 'not authenticated', None)), \
                    patch('ez.setup.notebooklm_python', return_value='py'), patch('ez.setup.login_browser_missing', return_value=False):
                checks = prepare(Path(temp) / 'runs', check=True)
        self.assertEqual(checks['login_status'], 'expired')


class EzUsesItsOwnNotebookLM(unittest.TestCase):
    def test_another_programs_notebooklm_is_not_taken_as_installed(self):
        from ez.setup import prepare
        with tempfile.TemporaryDirectory() as temp, patch('ez.setup.executable', return_value='C:/other/venv/Scripts/notebooklm.exe'), \
                patch('ez.setup.isolated_notebooklm', return_value=None), \
                patch('ez.setup.run', return_value=Result(0, json.dumps({'notebooks': []}), '', None)), \
                patch('ez.setup.notebooklm_python', return_value='py'), patch('ez.setup.login_browser_missing', return_value=False):
            checks = prepare(Path(temp) / 'runs', check=True)
        self.assertEqual(checks['notebooklm_foreign'], 'C:/other/venv/Scripts/notebooklm.exe')
        step = next(s for s in checks['onboarding'] if s['id'] == 'notebooklm_installed')
        self.assertFalse(step['done'])


class ResumingDoesNotRewriteEverySource(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def test_a_second_upload_pass_over_uploaded_sources_commits_nothing_per_source(self):
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            engine = Engine(self.folder, runner=self.service)
            engine.upload()
            before = len(Store(self.folder).events())
            Engine(self.folder, runner=self.service).upload()
        transactions = [e for e in Store(self.folder).events()[before:] if e['kind'] == 'transaction']
        self.assertLessEqual(len(transactions), 1)

    def test_a_grown_journal_verifies_only_its_new_events(self):
        import ez.state
        store = Store(self.folder)
        store.events()
        with lock(self.folder):
            store.append('decision', {'kind': 'x'})
        with patch('ez.state.digest', wraps=ez.state.digest) as hashed:
            events = store.events()
        self.assertEqual(hashed.call_count, 1)
        self.assertEqual(events[-1]['payload'], {'kind': 'x'})


class IonChargesBecomeText(unittest.TestCase):
    def test_charges_and_subscripts_are_converted(self):
        from ez.audit import plain
        b = chr(92)
        self.assertEqual(plain(b + '(Fe^{3+}' + b + ')'), 'Fe³⁺')
        self.assertEqual(plain(b + '(Fe^{2+}' + b + ') y ' + b + '(FeCl_3' + b + ')'), 'Fe²⁺ y FeCl₃')
        self.assertEqual(plain(b + '(SO_{4}^{2-}' + b + ')'), 'SO₄²⁻')


class EstimatesCountDownloadsAndUpload(unittest.TestCase):
    def test_a_search_estimate_includes_getting_and_loading_pdfs(self):
        from ez.contracts import draft, estimate
        contract = draft('Pregunta', {})
        contract['plan']['notebook_questions'] = [{'id': f'qa{i}', 'text': 'x', 'scope_ids': ['sq1']} for i in range(5)]
        value = estimate(contract)
        # The live test: about 5 min of downloads and 7 min of upload for 18 PDFs, plus 5 questions.
        self.assertGreaterEqual(value['minutes'][1], 20)
        self.assertIn('PDF', value['text'])


class FirstQuestionGetsTime(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def test_notebooklm_questions_wait_at_least_five_minutes(self):
        timeouts = []

        def runner(args, **kwargs):
            if len(args) > 1 and args[1] == 'ask':
                timeouts.append(kwargs.get('timeout'))
            return self.service(args, **kwargs)

        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            Engine(self.folder, runner=runner).execute()
        self.assertTrue(timeouts)
        self.assertGreaterEqual(min(timeouts), 300)


class GuideKeepsTheAgentInsideEZ(unittest.TestCase):
    def test_the_guide_forbids_ending_the_turn_and_the_notebooklm_web(self):
        root = Path(__file__).resolve().parents[1]
        guide = (root / 'docs' / 'ez-host-operator.md').read_text(encoding='utf-8')
        agents = (root / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('No cierres tu turno', guide)
        self.assertIn('web de NotebookLM', guide)
        self.assertIn('yield_time_ms', agents)
        self.assertIn('never through its web page', agents)


if __name__ == '__main__':
    unittest.main()
