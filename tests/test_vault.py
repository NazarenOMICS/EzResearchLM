"""The project's evidence memory: notes rebuilt from delivered claims, recall without NotebookLM, run-qualified markers."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.deliver import check_draft
from ez.state import Store
import test_v6_rules


class VaultTests(unittest.TestCase):
    def setUp(self):
        self.case = test_v6_rules.DirectDeliveryTests('test_direct_delivery_needs_no_review_and_no_second_query')
        self.case.setUp()
        self.addCleanup(self.case.temp.cleanup)
        self.assertEqual(self.case.run_engine()[0], 0)
        self.root = Path(self.case.temp.name).resolve()
        self.run_id = Store(self.case.folder).state()['run_id']

    def cli(self, *arguments):
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main(['--root', str(self.root), *arguments, '--json'])
        return code, json.loads(output.getvalue())

    def test_each_delivery_rebuilds_the_project_notes(self):
        notes = self.root / 'projects' / 'general' / 'notes'
        [source] = sorted((notes / 'sources').glob('*.md'))
        [research] = sorted((notes / 'researches').glob('*.md'))
        text = source.read_text(encoding='utf-8')
        self.assertIn('## Pasajes citados por NotebookLM', text)
        self.assertIn(f'[EZ:{self.run_id}/qa1-1]', text)
        self.assertIn('[[' + research.stem + ']]', text)
        self.assertIn('[[' + source.stem + ']]', research.read_text(encoding='utf-8'))
        self.assertEqual(Store(self.case.folder).state()['workspace']['notes'], str(notes))

    def test_recall_answers_from_delivered_claims_without_notebooklm(self):
        calls = len(self.case.service.calls)
        code, value = self.cli('recall', '¿Qué resultado experimental describe la fuente?')
        self.assertEqual((code, value['evidence']), (0, 'sufficient'))
        self.assertEqual(value['hits'][0]['marker'], f'[EZ:{self.run_id}/qa1-1]')
        self.assertTrue(value['hits'][0]['passages'])
        self.assertEqual(len(self.case.service.calls), calls)
        code, value = self.cli('recall', 'estructura cristalográfica del transportador')
        self.assertEqual((value['evidence'], value['hits']), ('insufficient', []))
        self.assertIn('ez ask', value['next_action'])

    def test_a_draft_may_cite_claims_of_other_researches_of_the_project(self):
        draft = self.root / 'draft.md'
        draft.write_text(f'La fuente describe un resultado experimental [EZ:{self.run_id}/qa1-1]. '
                         'Otra frase cita algo inexistente [EZ:ez-0000000000000000/qa1-1].', encoding='utf-8')
        code, value = self.cli('draft', str(self.case.folder), '--check', str(draft))
        self.assertEqual(code, 4)
        self.assertEqual(value['claims_used'], [f'{self.run_id}/qa1-1'])
        self.assertEqual(value['unknown_markers'], ['ez-0000000000000000/qa1-1'])

    def test_local_markers_still_resolve_against_the_run(self):
        answer = {'claims': [{'id': 'qa1-1'}], 'withheld_claims': [{'id': 'qa2-1'}]}
        result = check_draft(answer, 'Uno [EZ:qa1-1]. Dos [EZ:qa2-1]. Tres [EZ:ez-x/qa1-1].', lambda run: {'claims': [{'id': 'qa1-1'}]})
        self.assertEqual((result['claims_used'], result['withheld_markers'], result['unknown_markers']),
                         (['ez-x/qa1-1', 'qa1-1'], ['qa2-1'], []))


if __name__ == '__main__':
    unittest.main()
