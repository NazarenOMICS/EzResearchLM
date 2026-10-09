from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.presenter import render


class PresentationTests(unittest.TestCase):
    def test_welcome_and_guide_are_offline_and_do_not_create_a_run(self):
        with tempfile.TemporaryDirectory() as temp, patch('ez.cli.load_environment'), patch('ez.cli.prepare') as setup:
            root = Path(temp) / 'runs'
            for options, kind in (([], 'welcome'), (['--guide'], 'user_guide')):
                output = StringIO()
                with redirect_stdout(output):
                    code = main([*options, '--root', str(root), '--json'])
                self.assertEqual(code, 0)
                result = json.loads(output.getvalue())
                self.assertEqual(result['kind'], kind)
                if kind == 'user_guide':
                    self.assertIn('## Primer uso', result['text'])
            setup.assert_not_called()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_partial_answer_keeps_citations_passages_and_gaps_without_dumping_json(self):
        report = {'answer': {'status': 'partial'}, 'integrity': {'status': 'pass'},
                  'claims': [{'text': 'Afirmación sintética', 'question_id': 'q1', 'citation_numbers': [2],
                              'references': [{'citation_number': 2, 'source_id': 'remote-1', 'cited_text': 'Pasaje sintético de prueba.'}]}],
                  'coverage': [{'scope_id': 'sq2', 'status': 'insufficient', 'rationale': 'Falta la comparación', 'limitations': ['No generalizar a B']}],
                  'blockers': [{'source_id': 'missing', 'scope_ids': ['sq2'], 'reason': 'missing_source', 'policy': 'hard_block'}]}
        original = deepcopy(report)
        output = render(report)
        for text in ('Respuesta parcial', '[q1:2]', 'remote-1', 'Pasaje sintético', 'Falta la comparación', 'No generalizar a B', 'Esa parte queda pendiente'):
            self.assertIn(text, output)
        self.assertEqual(output.count('Afirmación sintética'), 1)
        self.assertNotIn('"claims"', output)
        self.assertEqual(report, original)

    def test_rescue_lists_missing_identity_and_remote_tasks_separately(self):
        output = render({'sources': [
            {'source_id': 'identity', 'title': 'PDF por revisar', 'validation_status': 'valid', 'identity_status': 'needs_review'},
            {'source_id': 'upload', 'title': 'PDF para subir', 'validation_status': 'valid', 'identity_status': 'verified'},
            {'source_id': 'ready', 'validation_status': 'valid', 'identity_status': 'verified', 'notebook_status': 'ready'}],
            'unresolved_requirements': [{'source_id': 'absent', 'title': 'Artículo faltante'}]})
        self.assertIn('pendientes: 3', output)
        self.assertIn('confirmar qué artículo', output)
        self.assertIn('incorporación a NotebookLM', output)
        self.assertIn('Artículo faltante', output)
        self.assertNotIn('(ready)', output)

    def test_diagnosis_shows_all_findings_and_does_not_hide_waiting_state(self):
        output = render({'run_id': 'ez-test', 'execution': {'status': 'waiting_service'},
                         'answer': {'status': 'unavailable'}, 'integrity': {'status': 'fail'},
                         'findings': [{'message': 'Cambió el PDF'}, {'message': 'Falta una cita'}],
                         'next_action': 'Revisar el documento original', 'snapshot_only': True})
        for text in ('En espera del servicio', 'Cambió el PDF', 'Falta una cita', 'no se consultó el servicio', 'Siguiente paso'):
            self.assertIn(text, output)
        self.assertNotIn('Respuesta completa', output)

    def test_setup_and_context_show_user_information_instead_of_internal_keys(self):
        output = render({'can_notebook_qa': True, 'can_recall': False, 'configuration_exists': False, 'runs_root': 'X:/runs'})
        self.assertIn('acceso comprobado', output)
        self.assertIn('pendiente', output)
        self.assertIn('puedes investigar con fuentes nuevas', output)
        self.assertNotIn('can_recall', output)
        output = render({'project': 'tesis', 'revision': 1, 'discipline': 'Biología',
                         'research_history': [{'question': 'Pregunta anterior', 'run_id': 'ez-old'}]})
        for text in ('tesis', 'Biología', 'Pregunta anterior', 'ez-old', 'evidencia debe revisarse'):
            self.assertIn(text, output)
