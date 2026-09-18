from hashlib import sha256
from pathlib import Path
import tempfile
import unittest

from ez.contracts import ContractError
from ez.legacy import migrate, preview
from ez.state import atomic_json, read_json


class MigrationTests(unittest.TestCase):
    def fixture(self, root, version=None):
        folder = root / 'legacy'; folder.mkdir()
        state = {'goal': 'Pregunta heredada', 'notebook_id': 'nb-old', 'vault_slug': 'external/project',
                 'stop_if_missing_must_have': False, 'allow_anna_fallback': True}
        if version:
            state['must_have_gate_version'] = version
        atomic_json(folder / 'run-state.json', state)
        atomic_json(folder / 'source-rescue.json', {'sources': [{'target_id': 'doi:10.1234/a', 'doi': '10.1234/a',
                                                              'title': 'Fuente sintética', 'required': True, 'status': 'manual_needed'}]})
        return folder

    def test_sidecar_preserves_bytes_notebook_and_historical_effective_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); folder = self.fixture(root)
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            plan = preview(folder)
            result = migrate(folder, root / 'v2', plan['preview_hash'])
            contract = read_json(Path(result['path']) / 'research-contract.json')
            self.assertEqual(contract['source_policies'][0]['policy'], 'hard_block')
            self.assertTrue(contract['source_policies'][0]['locked_by_user'])
            self.assertFalse(contract['acquisition']['anna_enabled'])
            self.assertEqual(result['notebook_id'], 'nb-old')
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})

    def test_new_switch_false_is_preserved_and_preview_detects_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); folder = self.fixture(root, 2)
            plan = preview(folder)
            self.assertEqual(plan['legacy_effective_gate'], 'report_missing')
            atomic_json(folder / 'questions-x.json', {'notebook_id': 'different'})
            with self.assertRaisesRegex(ContractError, 'cambió'):
                migrate(folder, root / 'v2', plan['preview_hash'])
            with self.assertRaisesRegex(ContractError, 'conflictos'):
                migrate(folder, root / 'v2', preview(folder)['preview_hash'])
            self.assertFalse((root / 'v2').exists())

    def test_unknown_formats_and_duplicate_sources_are_not_migrated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); folder = self.fixture(root)
            state = read_json(folder / 'run-state.json')
            for field, value in [('schema_version', '3.0'), ('must_have_gate_version', 3)]:
                with self.subTest(field=field):
                    atomic_json(folder / 'run-state.json', dict(state, **{field: value}))
                    with self.assertRaises(ContractError):
                        preview(folder)
            atomic_json(folder / 'run-state.json', state)
            source = read_json(folder / 'source-rescue.json')['sources'][0]
            atomic_json(folder / 'source-rescue.json', {'sources': [source, source]})
            with self.assertRaisesRegex(ContractError, 'duplicadas'):
                migrate(folder, root / 'v2', preview(folder)['preview_hash'])
            self.assertFalse((root / 'v2').exists())
