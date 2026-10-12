"""Neutral offline reproductions of the c3e66c7 audit; all IO uses temporary homes."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ez.audit import merge_repeated, plain, statements
from ez.cli import compact, close_candidates, narrow_search_advice, recall_project
from ez.contracts import ContractError
from ez.state import atomic_json


class AuditRegressions(unittest.TestCase):
    def test_H1_context_and_passage_identity(self):
        refs = [{'source_id': s, 'page': 2, 'cited_text': 'Literal passage',
                 'source': {'source_id': s, 'title': s}} for s in ('a', 'b')]
        claim = {'id': 'q1', 'text': 'Observed difference', 'context': 'Solo adultos', 'references': refs}
        shown = compact({'claims': [claim]})['claims'][0]
        self.assertEqual(shown['context'], 'Solo adultos')
        self.assertEqual([r['source_id'] for r in shown['passage_sources']], ['a', 'b'])

    def test_H2_context_quantity_negation_not_merged(self):
        text = 'The measured response in participants after the observation period was 10 units above baseline.'
        def claim(i, context, text=text):
            return dict(id=i, text=text, context=context, scope_ids=['s'], question_id='q',
                        citation_numbers=[1], references=[{'source_id': 'shared', 'cited_text': text}])
        cases = [(claim('a', 'Grupo A'), claim('b', 'Grupo B')),
                 (claim('a', 'Study A'), claim('b', 'Study B')),
                 (claim('a', 'Adults'), claim('b', 'Adults', text.replace('10', '20'))),
                 (claim('a', 'Adults'), claim('b', 'Adults', text.replace('was', 'was not'))),
                 (claim('a', 'Adults', 'Measured value: 10 mM'), claim('b', 'Adults', 'Measured value: 10 mm')),
                 (claim('a', 'Adults', 'Measured value > 10 units'), claim('b', 'Adults', 'Measured value < 10 units'))]
        for pair in cases:
            with self.subTest(pair=pair):
                self.assertEqual(len(merge_repeated(pair)), 2)

    def test_H3_numbered_plain_label_and_indented_continuation(self):
        for answer in ('1. Solo adultos:\n\t- Outcome increased over the observation period [1].',
                       '- **Solo adultos:**\n    Outcome increased over the observation period [1].',
                       'Solo **adultos**:\n    Outcome increased over the observation period [1].'):
            with self.subTest(answer=answer):
                rows = list(statements(answer))
                self.assertEqual(rows[-1][1], 'Solo adultos')

    def test_H3_cited_heading_is_substantive(self):
        self.assertTrue(list(statements('## Response increased over the observation period [1].')))
        rows = list(statements('## Previous study\n## New study reported a response [1].\n  - Dose: 10 units [1].'))
        self.assertEqual(rows[0][1], '')
        self.assertEqual(rows[1][1], 'New study reported a response.')

    def test_H3_unsafe_math_preserved(self):
        expr = r'$\frac{a_{b}}{c}$'
        self.assertIn(expr, plain('Ratio ' + expr + ' [1]'))
        expr = r'\(\frac{a_{b}}{c}\)'
        self.assertIn(expr, plain('Ratio ' + expr + ' [1]'))
        self.assertEqual(plain(r'$10\text{ }\mu\text{g/ml}$ [1]'), '10 µg/ml')
        self.assertEqual(plain(r'$x^{a+b}$'), r'$x^{a+b}$')

    def test_H4_cache_rejects_changed_deleted_pdf(self):
        from hashlib import sha256
        from ez.vault import page_cache
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pdf = root / 'document.pdf'
            pdf.write_bytes(b'original')
            source = {'pdf_path': str(pdf), 'content_sha256': sha256(b'original').hexdigest()}
            atomic_json(root / 'cache/pages' / (source['content_sha256'] + '.json'),
                        {'sha256': source['content_sha256'], 'pages': ['Old evidence']})
            for data in (b'changed', None):
                if data is None:
                    pdf.unlink()
                else:
                    pdf.write_bytes(data)
                with self.subTest(data=data), self.assertRaisesRegex(ContractError, 'integrity'):
                    page_cache(root / 'runs', source)

    def test_H5_references_end_at_appendix(self):
        from ez.vault import pdf_chunks
        source = dict(source_id='s', content_sha256='a'*64, title='Study')
        pages = ['Body outcome.\n7. References:\nCitation list.', 'Appendix A\nSupplementary result.']
        with patch('ez.vault.page_cache', return_value=pages):
            chunks = pdf_chunks(Path('unused'), 'p', [source])
        self.assertEqual([(c['text'], c['in_references']) for c in chunks],
                         [('Body outcome.', False), ('7. References: Citation list.', True),
                          ('Appendix A Supplementary result.', False)])

    def test_H6_short_lowercase_names_and_balanced_doi(self):
        from ez.vault import named_works
        for question, source in [('li 2020', {'authors': ['Li J'], 'year': 2020}),
                                 ('de la Cruz y col. 2021', {'authors': ['de la Cruz ABCD'], 'year': 2021}),
                                 ('10.1234/item(2020)', {'doi': '10.1234/item(2020)'})]:
            with self.subTest(question=question):
                works = named_works(question)
                self.assertTrue(works)
                self.assertTrue(any(matches(source) for _, matches in works))

    def test_H7_coverage_is_not_sufficiency_or_language_detection(self):
        from ez.vault import recall
        row = dict(key='r/a', text='duración adultos', context=None, passages=[], delivery='direct')
        with patch('ez.vault.records', return_value=[row]), patch('ez.library.project_sources', return_value=[]):
            result = recall(Path('unused'), 'p', 'duración adultos')
        self.assertEqual(result['coverage'], 1)
        self.assertNotEqual(result['evidence'], 'sufficient')
        self.assertIsNone(result['query_language_mismatch'])

    def test_H8_structured_authors(self):
        from ez.presenter import short_citation
        self.assertEqual(short_citation({'authors': [{'given': 'Ana', 'family': 'de la Cruz'}], 'year': 2020}),
                         'de la Cruz, 2020')
        self.assertEqual(short_citation({'authors': [{'literal': 'Council, Research Division'}], 'year': 2020}),
                         'Council, Research Division, 2020')

    def test_H9_second_move_and_nonstandard_root(self):
        from ez.setup import prepare
        from ez.workspace import projects_home
        for name in ('runs', 'researches'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                root, a, b = base / name, base / 'A', base / 'B'
                with patch('ez.setup.executable', return_value=None):
                    prepare(root, projects_dir=a)
                    (a / 'p').mkdir()
                    (a / 'p/evidence.txt').write_text('preserve')
                    prepare(root, projects_dir=b)
                self.assertEqual(projects_home(root), b.resolve())
                self.assertEqual((b / 'p/evidence.txt').read_text(), 'preserve')

    def test_H11_mcp_full(self):
        from ez.mcp_server import ez_recall
        with patch('ez.mcp_server.ez', return_value={}) as call:
            ez_recall('whole question', 'p', full=True)
        self.assertIn('--full', call.call_args.args)

    def test_H12_invalid_listing_never_ready(self):
        from ez.setup import start_login
        from ez.process import Result
        for raw in ('{}', '<html/>', '{"notebooks":[{}]}'):
            with tempfile.TemporaryDirectory() as temp, patch('ez.setup.executable', return_value='fake'), \
                    patch('ez.setup.notebooklm_python', return_value='fake'), \
                    patch('ez.setup.run', return_value=Result(0, raw, '', None)), \
                    patch('ez.setup.LOGIN_STATUS', Path(temp) / 'login.json'), patch('subprocess.Popen'):
                self.assertNotEqual(start_login()['login_status'], 'ready')

    def test_H13_single_term_protection_and_binomial_advice(self):
        candidate = {'source_id': 'a', 'title': 'Photosynthesis measured'}
        self.assertEqual(close_candidates([candidate], [{'text': 'photosynthesis'}]), [candidate])
        short = {'source_id': 'b', 'title': 'DNA measured'}
        self.assertEqual(close_candidates([short], [{'text': 'DNA'}]), [short])
        advice = narrow_search_advice(['Pinus sylvestris drought', 'Pinus sylvestris water stress'])
        # The shared core stays flagged (it caused the 2026-10-11 losses) but says a binomial can be the scope itself.
        self.assertTrue(any('es el alcance acordado' in a for a in advice))
        self.assertFalse(narrow_search_advice(['alpha OR beta', 'alpha']))

    def test_H14_do_not_consume_question_word(self):
        with patch('ez.workspace.project_names', return_value={'adultos'}):
            result = recall_project(Path('unused'), SimpleNamespace(question=['adultos', 'respuesta'], project=None))
        self.assertEqual(result, ('adultos', 'adultos respuesta'))



if __name__ == '__main__':
    unittest.main()
