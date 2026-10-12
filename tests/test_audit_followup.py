"""Second review of the audit fixes: regressions the first layer introduced, reproduced before fixing."""
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ez.cli import narrow_search_advice
from ez.contracts import ContractError
from ez.state import atomic_json


class NamedWorksIgnoreTimeExpressions(unittest.TestCase):
    def test_a_preposition_or_month_before_a_year_is_not_a_work(self):
        from ez.vault import named_works
        for question in ('¿Qué pasó en pacientes tratados en 2019?', 'efectos observados durante 2020',
                         'trials published after 2015', 'dosis usadas hasta 2018', 'resultados de 2019',
                         'datos de marzo 2021', 'in the year 2020', 'estudios posteriores a 2019, antes de 2022'):
            with self.subTest(question=question):
                self.assertEqual([label for label, _ in named_works(question)], [])
        self.assertEqual([label for label, _ in named_works('Smith 2019 dosis')], ['Smith 2019'])

    def test_an_unresolved_name_adds_to_the_hint_instead_of_replacing_it(self):
        from ez.cli import recall_command
        result = {'claims_in_project': 1, 'hits': [{'text': 'x', 'passages': []}], 'coverage': 1.0,
                  'evidence': 'needs_judgment', 'missing_words': [], 'pdf_passages': [], 'pdf_coverage': 0.0,
                  'pdfs_searched': 0, 'named_works_absent': [], 'named_works_unresolved': ['Smith 2019'],
                  'integrity_issues': [], 'low_lexical_overlap': False}
        shown = {}
        args = SimpleNamespace(question=['Smith 2019 dosis'], project='p', limit=8, json=True)
        with patch('ez.cli.recall_project', return_value=('p', 'Smith 2019 dosis')), \
                patch('ez.vault.recall', return_value=result), patch('ez.cli.emit', lambda value, _: shown.update(value)):
            recall_command(Path('unused'), args)
        self.assertIn('Smith 2019', shown['next_action'])
        self.assertIn('Se recuperaron coincidencias', shown['next_action'])


class IntegrityFollowsTheBytes(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.sha = sha256(b'pdf bytes').hexdigest()
        pdf = self.temp / 'old' / 'runs' / 'ez-1' / 'acquisition' / 'src-a' / (self.sha + '.pdf')
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b'pdf bytes')
        self.source = {'source_id': 'a', 'pdf_path': str(pdf), 'content_sha256': self.sha}
        self.claim = {'id': 'q1', 'text': 'Outcome', 'references': [{'source': self.source, 'cited_text': 'Passage'}]}

    def move_runs(self):
        new = self.temp / 'new' / 'runs'
        new.parent.mkdir()
        (self.temp / 'old' / 'runs').rename(new)
        return new

    def test_a_moved_runs_folder_keeps_delivered_claims(self):
        from ez.vault import check_claim_pdfs, records
        runs = self.move_runs()
        check_claim_pdfs(self.claim, runs)
        row = dict(path=str(runs / 'ez-1'), question='q', updated_at='2026-01-01')
        issues = []
        with patch('ez.context.history', return_value=[row]), \
                patch('ez.vault.valid_answer', return_value=({'claims': [self.claim]}, {'run_id': 'ez-1'})):
            self.assertEqual(len(records(runs, 'p', issues)), 1)
        self.assertEqual(issues, [])

    def test_a_moved_pdf_with_other_bytes_is_still_rejected(self):
        from ez.vault import check_claim_pdfs, page_cache
        runs = self.move_runs()
        (runs / 'ez-1' / 'acquisition' / 'src-a' / (self.sha + '.pdf')).write_bytes(b'other bytes')
        atomic_json(runs.parent / 'cache' / 'pages' / (self.sha + '.json'), {'sha256': self.sha, 'pages': ['Old']})
        with self.assertRaisesRegex(ContractError, 'integrity'):
            check_claim_pdfs(self.claim, runs)
        with self.assertRaisesRegex(ContractError, 'integrity'):
            page_cache(runs, self.source)

    def test_each_pdf_is_hashed_once_per_call_however_many_claims_cite_it(self):
        import hashlib
        from ez.vault import check_claim_pdfs
        with patch('ez.library.sha256', wraps=hashlib.sha256) as hashed:
            for _ in range(30):
                check_claim_pdfs(self.claim, self.temp / 'old' / 'runs')
        self.assertEqual(hashed.call_count, 1)


class RecallStatesWhatItKnows(unittest.TestCase):
    def recall(self, rows, pages):
        from ez.vault import recall
        source = {'source_id': 's1', 'content_sha256': 'ab' * 32, 'title': 'T', 'authors': ['Kim J'], 'year': 2020}
        with patch('ez.vault.records', return_value=rows), patch('ez.library.project_sources', return_value=[source]), \
                patch('ez.vault.page_cache', return_value=pages):
            return recall(Path('unused'), 'p', 'growth rate medium')

    def test_matches_need_judgment_and_nothing_found_is_none(self):
        row = dict(key='r/a', text='growth rate in medium', context='', passages=[])
        self.assertEqual(self.recall([row], [])['evidence'], 'needs_judgment')
        self.assertEqual(self.recall([], ['The growth rate in this medium was lower.'])['evidence'], 'needs_judgment')
        self.assertEqual(self.recall([], [])['evidence'], 'none')


class CommonCoreAdviceSurvivesQuerySyntax(unittest.TestCase):
    def test_and_and_parentheses_still_count_as_containment(self):
        advice = narrow_search_advice(['(compound alpha) AND resistance', 'compound alpha resistance mechanism'])
        self.assertTrue(any('contiene todos los términos' in a for a in advice))
        self.assertTrue(narrow_search_advice(['"compound alpha"[tiab] AND resistance', 'compound alpha resistance']))

    def test_or_queries_are_not_read_as_intersections(self):
        self.assertFalse(narrow_search_advice(['aspirin OR ibuprofen', 'aspirin ibuprofen dose']))

    def test_a_shared_core_says_how_to_widen_unless_it_is_the_scope(self):
        advice = ' '.join(narrow_search_advice(['compound alpha resistance', 'compound alpha tolerance']))
        self.assertIn('compound alpha', advice)
        self.assertIn('saque uno', advice)
        self.assertIn('alcance', advice)


class DisplayNamesStillGiveASurname(unittest.TestCase):
    """OpenAlex and Semantic Scholar send «Ana M. Lopez»: keeping the whole name cited every such work as «Ana M. Lopez»."""
    def test_display_names_cite_by_surname_with_its_particles(self):
        from ez.presenter import surname
        for name, expected in [('Ana M. Lopez', 'Lopez'), ('Jean de la Fontaine', 'de la Fontaine'),
                               ('Ludwig van Beethoven', 'van Beethoven'), ('Garcia EMJH', 'Garcia'),
                               ('World Health Organization', 'World Health Organization'),
                               ('Research Council', 'Research Council'), ('Lopez, Ana M.', 'Lopez')]:
            with self.subTest(name=name):
                self.assertEqual(surname(name), expected)

    def test_citation_and_key_of_a_display_name_list(self):
        from ez.deliver import citation_key
        from ez.presenter import short_citation
        source = {'authors': ['Eva Garcia', 'Ana Lopez', 'Jun Kim'], 'year': 2017}
        self.assertEqual(short_citation(source), 'Garcia et al., 2017')
        self.assertEqual(citation_key(source, set()), 'garcia2017')


if __name__ == '__main__':
    unittest.main()
