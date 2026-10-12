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
        output = render({'can_notebook_qa': True, 'configuration_exists': False, 'runs_root': 'X:/runs'})
        self.assertIn('acceso comprobado', output)
        self.assertIn('pendiente', output)
        self.assertNotIn('can_notebook_qa', output)
        output = render({'project': 'tesis', 'revision': 1, 'discipline': 'Biología',
                         'research_history': [{'question': 'Pregunta anterior', 'run_id': 'ez-old'}]})
        for text in ('tesis', 'Biología', 'Pregunta anterior', 'ez-old', 'evidencia debe revisarse'):
            self.assertIn(text, output)


class CitationTests(unittest.TestCase):
    def test_short_citation_reads_the_author_formats_the_indexes_return(self):
        from ez.presenter import short_citation
        cases = {('Garcia E',): 'Garcia, 2020', ('Ana M. Lopez',): 'Lopez, 2020', ('Lopez, Ana M.',): 'Lopez, 2020',
                 ('van der Berg JH',): 'van der Berg, 2020', ('Garcia E', 'Lopez A'): 'Garcia y Lopez, 2020',
                 ('Garcia E', 'Lopez A', 'Kim J'): 'Garcia et al., 2020'}
        for authors, expected in cases.items():
            self.assertEqual(short_citation({'authors': list(authors), 'year': 2020}), expected)
        self.assertEqual(short_citation({'authors': 'Garcia E; Lopez A; Kim J', 'year': 2021}), 'Garcia et al., 2021')
        self.assertIsNone(short_citation({'title': 'Sin autores'}))

    def test_citation_keys_and_notes_take_the_first_author(self):
        # Authors joined by «;» in one string named a note and a BibTeX key after the last author (2026-10-11).
        from ez.deliver import citation_key
        from ez.vault import note_header
        joined = {'authors': 'Eva Garcia; Ana Lopez; Jun Kim', 'year': 2017, 'title': 'Un trabajo'}
        self.assertEqual(citation_key(joined, set()), 'garcia2017')
        for authors, key in ((['Garcia E', 'Kim J'], 'garcia2020'), (['Garcia, Eva'], 'garcia2020'),
                             (['van der Berg JH'], 'vanderberg2020')):
            self.assertEqual(citation_key({'authors': authors, 'year': 2020}, set()), key)
        self.assertEqual(citation_key({'authors': 'Meniche X, Otal I, Kim JH.', 'year': 2008}, set()), 'meniche2008')
        self.assertEqual(citation_key({'authors': ['Haußmann U'], 'year': 2009}, set()), 'haussmann2009')
        from ez.presenter import short_citation
        self.assertEqual(short_citation({'authors': 'Meniche X, Otal I, Kim JH', 'year': 2008}), 'Meniche et al., 2008')
        self.assertEqual(short_citation({'authors': 'Lopez, Ana M.', 'year': 2008}), 'Lopez, 2008')
        header = '\n'.join(note_header(joined))
        self.assertIn('citation: "Garcia et al., 2017"', header)
        self.assertIn('  - "Jun Kim"', header)
        self.assertIn('Garcia et al., 2017. Eva Garcia, Ana Lopez, Jun Kim.', header)

    def test_claim_citation_lists_each_source_once_and_the_report_shows_it(self):
        from ez.presenter import claim_citation
        a = {'source_id': 's1', 'authors': ['Garcia E', 'Lopez A', 'Kim J'], 'year': 2021, 'title': 'Uno'}
        b = {'source_id': 's2', 'title': 'Fuente sin autores'}
        claim = {'id': 'qa1-1', 'references': [{'source': a}, {'source': b}, {'source': a}]}
        self.assertEqual(claim_citation(claim), '(Garcia et al., 2021)')
        self.assertEqual(claim_citation({'references': [{'source': b}]}), '')
