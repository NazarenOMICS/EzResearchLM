"""Regression tests for persistent paths and interrupted NotebookLM operations."""
import json
import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez.process import Result
from ez.state import read_json


class PersistenceAuditTests(unittest.TestCase):
    def test_projects_move_twice_for_standard_and_arbitrary_runs_roots(self):
        from ez.setup import prepare
        from ez.workspace import projects_home

        for root_name in ('runs', 'researches'):
            with self.subTest(root_name=root_name), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                root, first, second = base / root_name, base / 'A', base / 'B'
                registry = root / 'projects' / 'project' / 'notebooks.json'
                registry.parent.mkdir(parents=True)
                registry.write_text('{"notebooks": []}', encoding='utf-8')
                # Model the rename restriction between volumes; migration must use copying.
                with patch('ez.setup.executable', return_value=None), \
                        patch('pathlib.Path.rename', side_effect=OSError(errno.EXDEV, 'cross-device link')):
                    prepare(root, projects_dir=first)
                    (first / 'project').mkdir(exist_ok=True)
                    (first / 'project' / 'evidence.txt').write_text('source remains', encoding='utf-8')
                    prepare(root, projects_dir=second)

                self.assertEqual(projects_home(root), second.resolve())
                self.assertEqual((second / 'project' / 'evidence.txt').read_text(encoding='utf-8'), 'source remains')
                self.assertEqual((first / 'project' / 'evidence.txt').read_text(encoding='utf-8'), 'source remains')
                config_root = base if root_name == 'runs' else root
                config = read_json(config_root / 'ez-config.json')
                self.assertEqual(Path(config['projects_dir']), second.resolve())
                self.assertEqual(Path(config['runs_root']).resolve(), root.resolve())
                self.assertEqual(read_json(registry), {'notebooks': []})

    def test_project_move_collision_preserves_origin_and_config(self):
        from ez.setup import prepare
        from ez.workspace import projects_home

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, first, second = base / 'runs', base / 'A', base / 'B'
            with patch('ez.setup.executable', return_value=None):
                prepare(root, projects_dir=first)
                (first / 'project').mkdir()
                (first / 'project' / 'source.txt').write_text('keep', encoding='utf-8')
                (second / 'project').mkdir(parents=True)
                (second / 'project' / 'destination.txt').write_text('do not replace', encoding='utf-8')
                with self.assertRaises(ValueError):
                    prepare(root, projects_dir=second)

            self.assertEqual(projects_home(root), first.resolve())
            self.assertEqual((first / 'project' / 'source.txt').read_text(encoding='utf-8'), 'keep')
            self.assertEqual((second / 'project' / 'destination.txt').read_text(encoding='utf-8'), 'do not replace')

    def test_project_copy_failure_preserves_origin_and_configuration(self):
        from ez.setup import prepare
        from ez.workspace import projects_home

        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root, first, second = base / 'runs', base / 'A', base / 'B'
            with patch('ez.setup.executable', return_value=None):
                prepare(root, projects_dir=first)
                (first / 'project').mkdir()
                source = first / 'project' / 'source.txt'
                source.write_text('keep', encoding='utf-8')
                def fail_after_partial_copy(original, destination):
                    destination = Path(destination)
                    destination.mkdir()
                    (destination / 'partial.txt').write_text('partial', encoding='utf-8')
                    raise OSError('simulated copy failure')

                with patch('ez.workspace.shutil.copytree', side_effect=fail_after_partial_copy):
                    with self.assertRaisesRegex(OSError, 'simulated copy failure'):
                        prepare(root, projects_dir=second)

            self.assertEqual(projects_home(root), first.resolve())
            self.assertEqual(source.read_text(encoding='utf-8'), 'keep')
            self.assertFalse((second / 'project').exists())

    def test_interrupted_notebook_create_is_adopted_registered_and_reused(self):
        # Use the documented offline NotebookLM service double from the engine integration tests.
        from tests.test_engine import EngineTests
        from ez.cli import create_run
        from ez.context import reuse_sources
        from ez.engine import Engine
        from ez.state import Store, lock

        fixture = EngineTests()
        fixture.setUp()
        self.addCleanup(fixture.temp.cleanup)
        fixture.service.interrupt_create = True
        self.assertEqual(fixture.run_engine()[0], 3)
        self.assertEqual(fixture.run_engine()[0], 2)
        state = Store(fixture.folder).state()
        self.assertTrue(state.get('notebook_shared'))
        library = read_json(fixture.folder.parent / 'projects' / 'general' / 'notebooks.json')
        self.assertEqual(library['notebooks'][0]['notebook_id'], state['notebook_id'])
        self.assertIn(state['run_id'], library['notebooks'][0]['runs'])

        contract = read_json(fixture.folder / 'research-contract.json')
        contract['plan'].update(discovery_mode='reuse_only', queries=[])
        destination, _ = create_run(fixture.folder.parent, 'Otra pregunta', {'project': 'general'}, contract)
        reuse_sources(fixture.folder, destination)
        counts = fixture.service.create_count, fixture.service.upload_count
        with lock(destination), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(destination, runner=fixture.service).execute(), 2)
        self.assertEqual((fixture.service.create_count, fixture.service.upload_count), counts)

    def test_login_requires_a_valid_notebook_listing_in_both_paths(self):
        from ez.setup import run_login, start_login

        with tempfile.TemporaryDirectory() as temporary:
            status = Path(temporary) / 'login.json'
            with patch('ez.setup.executable', return_value='notebooklm'), \
                    patch('ez.setup.notebooklm_python', return_value='python'), \
                    patch('ez.setup.LOGIN_STATUS', status), patch('ez.setup.run', return_value=Result(0, '{}', '', None)), \
                    patch('subprocess.Popen'):
                self.assertNotEqual(start_login()['login_status'], 'ready')

            responses = [Result(0, json.dumps({'outcome': 'signed_in'}), '', None),
                         Result(0, '', '', None), Result(0, '{}', '', None)]
            with patch('ez.setup.executable', return_value='notebooklm'), \
                    patch('ez.setup.notebooklm_python', return_value='python'), \
                    patch('ez.setup.LOGIN_STATUS', status), patch('subprocess.run', side_effect=responses):
                self.assertEqual(run_login(), 'saved_session_invalid')


if __name__ == '__main__':
    unittest.main()
