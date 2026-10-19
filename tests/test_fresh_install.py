"""A clean install of 2026-10-19: EZ's NotebookLM had Playwright but not the Chromium its version needs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez.process import Result


class InstallBringsTheLoginBrowser(unittest.TestCase):
    def test_installing_notebooklm_also_downloads_chromium(self):
        from ez.setup import prepare
        calls = []

        def run(argv, timeout=60, **_):
            calls.append([str(a) for a in argv])
            return Result(0, '', '', None)

        with tempfile.TemporaryDirectory() as temp, patch('pathlib.Path.home', return_value=Path(temp)), \
                patch('ez.setup.run', side_effect=run), patch('ez.setup.executable', return_value=None):
            prepare(Path(temp) / 'runs', install_notebooklm=True)
        self.assertTrue(any(c[1:] == ['-m', 'playwright', 'install', 'chromium'] for c in calls), calls)

    def test_a_failed_browser_download_is_named_and_retryable(self):
        from ez.setup import prepare

        def run(argv, timeout=60, **_):
            failed = [str(a) for a in argv][1:3] == ['-m', 'playwright']
            return Result(1 if failed else 0, '', 'ECONNRESET' if failed else '', None)

        with tempfile.TemporaryDirectory() as temp, patch('pathlib.Path.home', return_value=Path(temp)), \
                patch('ez.setup.run', side_effect=run), patch('ez.setup.executable', return_value=None), \
                self.assertRaisesRegex(OSError, 'navegador'):
            prepare(Path(temp) / 'runs', install_notebooklm=True)


class MissingChromiumIsDetected(unittest.TestCase):
    def test_playwright_without_its_browser_counts_as_missing(self):
        from ez.setup import login_browser_missing
        with tempfile.TemporaryDirectory() as temp:
            absent, present = Path(temp) / 'chrome-missing.exe', Path(temp) / 'chrome.exe'
            present.write_text('')
            for path, missing in ((absent, True), (present, False)):
                with self.subTest(path=path.name), patch('ez.setup.notebooklm_python', return_value='py'), \
                        patch('ez.setup.run', return_value=Result(0, str(path) + '\n', '', None)):
                    self.assertEqual(login_browser_missing('notebooklm'), missing)

    def test_the_login_window_names_a_missing_browser(self):
        from ez.notebook_login import outcome_of
        error = Exception("BrowserType.launch_persistent_context: Executable doesn't exist at C:\\ms-playwright\\chrome.exe")
        self.assertEqual(outcome_of(error), 'browser_missing')
        self.assertEqual(outcome_of(Exception('Target page, context or browser has been closed')), 'browser_closed')

    def test_start_login_says_how_to_install_the_browser(self):
        import ez.setup
        from ez.state import atomic_json
        with tempfile.TemporaryDirectory() as temp:
            status = Path(temp) / 'login.json'

            def popen(*args, **kwargs):
                atomic_json(status, {'state': 'browser_missing', 'finished_at': 'now'})

            with patch('ez.setup.executable', return_value='notebooklm'), patch('ez.setup.notebooklm_python', return_value='py'), \
                    patch('ez.setup.run', return_value=Result(1, '', 'not authenticated', None)), \
                    patch('ez.setup.LOGIN_STATUS', status), patch('subprocess.Popen', side_effect=popen):
                value = ez.setup.start_login(wait_seconds=2)
        self.assertEqual(value['login_status'], 'browser_missing')
        self.assertIn('ez setup --install-notebooklm', value['next_action'])
        self.assertNotIn('pide a la persona', value['next_action'])


class SetupCommandsDoNotDependOnTheFolder(unittest.TestCase):
    def test_setup_creates_the_environment_inside_the_clone(self):
        # The agent ran clone, venv and pip from the parent folder: the venv landed in Documents\.venv.
        text = (Path(__file__).resolve().parents[1] / 'SETUP.md').read_text(encoding='utf-8')
        self.assertIn('Set-Location', text)
        self.assertIn('300 s', text)


if __name__ == '__main__':
    unittest.main()
