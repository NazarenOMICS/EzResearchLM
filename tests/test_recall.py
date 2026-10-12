"""Recall beyond keywords (citation expansion) and when a follow-up question needs new sources."""
import unittest

from ez.cli import sufficiency
from ez.citations import expand, text_of
from ez.state import Store, atomic_json, lock, read_json
import test_screening


class FakeResponse:
    def __init__(self, value, status=200):
        self.value, self.status_code = value, status

    def json(self):
        return self.value


class FakeSession:
    def __init__(self, routes):
        self.routes, self.urls = routes, []

    def get(self, url, timeout=None):
        self.urls.append(url)
        for fragment, value in self.routes.items():
            if fragment in url:
                return FakeResponse(value) if value is not None else FakeResponse({}, 503)
        return FakeResponse({}, 404)


class CitationModuleTests(unittest.TestCase):
    def test_references_and_citations_come_from_europepmc_and_openalex(self):
        session = FakeSession({
            'MED/111/references': {'referenceList': {'reference': [{'id': '222', 'source': 'MED', 'title': 'Cited work.', 'pubYear': '2001'}]}},
            'MED/111/citations': {'citationList': {'citation': [{'id': '333', 'source': 'MED', 'title': 'Citing work', 'pubYear': '2020'}]}},
            'works/doi:10.1/seed': {'id': 'https://openalex.org/W1', 'referenced_works': ['https://openalex.org/W2']},
            'openalex_id:W2': {'results': [{'id': 'W2', 'doi': 'https://doi.org/10.1/ref', 'title': 'Referenced by DOI',
                                            'publication_year': 1999, 'ids': {'pmid': 'https://pubmed.ncbi.nlm.nih.gov/444'},
                                            'abstract_inverted_index': {'world': [1], 'Hello': [0]}}]},
            'cites:W1': None,
        })
        records, failures = expand([{'source_id': 's1', 'pmid': '111', 'doi': '10.1/seed'}], session)
        self.assertEqual([(r['title'], r['links'][0]['relation']) for r in records],
                         [('Cited work', 'cited_by_seed'), ('Citing work', 'cites_seed'), ('Referenced by DOI', 'cited_by_seed')])
        self.assertEqual((records[2]['doi'], records[2]['pmid'], records[2]['abstract']), ('10.1/ref', '444', 'Hello world'))
        self.assertEqual(failures, 1)

    def test_abstracts_are_rebuilt_in_word_order(self):
        self.assertEqual(text_of({'b': [1], 'a': [0, 2]}), 'a b a')


class CitationExpansionTests(test_screening.ScreeningTests):
    # The inherited screening tests assume a plan without expansion.
    test_candidates_wait_for_screening_and_only_included_ones_are_acquired = None
    test_screening_respects_the_source_limit_and_the_current_candidates = None
    test_check_validates_screening_without_writing = None

    def setUp(self):
        super().setUp()
        self.service.discovery_records = [{'title': 'Relevant work', 'doi': '10.1/rel', 'pmid': '1'},
                                          {'title': 'Off topic work', 'doi': '10.1/off'}]
        self.expansion = {'records': [
            {'title': 'Ethambutol query effect on cell wall', 'doi': '10.9/topic', 'links': [{'seed': 'x', 'relation': 'cites_seed'}]},
            {'title': 'Unrelated cooking paper', 'doi': '10.9/far', 'links': [{'seed': 'x', 'relation': 'cites_seed'}]},
            {'title': 'Relevant work', 'doi': '10.1/rel', 'links': [{'seed': 'x', 'relation': 'cites_seed'}]},
        ], 'failures': 0}
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            from ez.contracts import digest
            contract = read_json(self.folder / 'research-contract.json')
            contract['plan']['citation_expansion'] = True
            contract['plan']['queries'][0]['text'] = 'ethambutol cell wall'
            state['contract_hash'] = digest(contract)
            store.commit(state, {'research-contract.json': contract})

    def runner(self, args, **kwargs):
        if args[1:3] == ['-m', 'ez.citations']:
            self.citation_calls = getattr(self, 'citation_calls', 0) + 1
            self.seeds = read_json(args[args.index('--input') + 1])
            if self.expansion is None:
                from ez.process import Result
                return Result(3, '', 'down', 'provider_error')
            atomic_json(args[args.index('--output') + 1], self.expansion)
            from ez.process import Result
            return Result(0, '', '', None)
        return super().runner(args, **kwargs)

    def test_included_sources_seed_a_second_screening_round_once(self):
        self.execute()
        code, engine = self.execute(self.decisions([('Relevant work', 'include'), ('Off topic work', 'exclude')]))
        self.assertEqual((code, engine.state['legacy_signals']), (2, ['NEEDS_SCREENING']))
        self.assertIn('Segunda ronda', engine.state['next_action'])
        self.assertIn('10.1/rel', [s['doi'] for s in self.seeds])
        self.assertNotIn('10.1/off', [s['doi'] for s in self.seeds])
        request = read_json(self.folder / 'screening-request.json')
        self.assertEqual([(c['title'], c['linked_to_included']) for c in request['candidates']],
                         [('Ethambutol query effect on cell wall', 1)])
        self.assertEqual(engine.state['citation_expansion']['added'], 1)
        self.assertEqual(self.acquired, [])
        code, engine = self.execute(self.decisions([('Ethambutol query effect on cell wall', 'include')]))
        self.assertNotEqual(engine.state['legacy_signals'], ['NEEDS_SCREENING'])
        self.assertEqual(self.citation_calls, 1)

    def test_a_failed_expansion_does_not_stop_the_research(self):
        self.expansion = None
        self.execute()
        code, engine = self.execute(self.decisions([('Relevant work', 'include'), ('Off topic work', 'exclude')]))
        self.assertEqual(engine.state['citation_expansion']['status'], 'failed')
        self.assertNotEqual(engine.state['legacy_signals'], ['NEEDS_SCREENING'])


class SufficiencyTests(unittest.TestCase):
    def test_a_follow_up_is_sufficient_only_with_claims_and_no_stated_gap(self):
        self.assertEqual(sufficiency({'claims': []}), 'insufficient')
        claim = {'claims': [{'id': 'ask1-1'}]}
        self.assertEqual(sufficiency(claim), 'sufficient')
        self.assertEqual(sufficiency(dict(claim, uncited_statements=[{'text': 'Las fuentes no mencionan la estructura.'}])), 'partial')


if __name__ == '__main__':
    unittest.main()


class FullTextRecallTests(unittest.TestCase):
    """ez recall searches the project's PDFs page by page, so methods and references need no NotebookLM query."""
    PAGES = ['Results. Cells grown in CGXII medium with 10 mg/L of the drug showed a lower growth rate.',
             'Discussion of the envelope.\nReferences\nGarcia E, Lopez A (2019) Earlier work on growth. J Bact 1:1-2.']

    def recall(self, question):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from ez.vault import recall
        source = {'source_id': 's1', 'content_sha256': 'ab' * 32, 'title': 'Growth under the drug',
                  'authors': ['Kim J', 'Lee S'], 'year': 2020, 'pdf_path': 'x.pdf'}
        with tempfile.TemporaryDirectory() as temp, patch('ez.library.project_sources', return_value=[source]), \
                patch('ez.vault.page_cache', return_value=self.PAGES):
            return recall(Path(temp) / 'runs', 'p', question)

    def test_literal_passages_carry_page_marker_citation_and_reference_flag(self):
        result = self.recall('CGXII medium growth rate drug concentration')
        best = result['pdf_passages'][0]
        self.assertEqual((best['marker'], best['page'], best['in_references']), ('[EZ:pdf-' + 'ab' * 6 + '-p1]', 1, False))
        self.assertEqual(best['source']['citation'], 'Kim y Lee, 2020')
        self.assertGreaterEqual(result['pdf_coverage'], 0.6)
        cited = self.recall('Garcia 2019 earlier work')['pdf_passages'][0]
        self.assertEqual((cited['page'], cited['in_references']), (2, True))

    def test_a_named_work_outside_the_corpus_is_never_answered(self):
        # In a live run (2026-10-11) «Smith 2019» looked answered by claims from other works.
        absent = self.recall('What did Garcia 2019 find about growth rate in CGXII medium with the drug?')
        self.assertEqual(absent['named_works_absent'], ['Garcia 2019'])
        self.assertNotEqual(absent['evidence'], 'sufficient')
        self.assertEqual(self.recall('Kim et al., 2020 growth rate in CGXII medium')['named_works_absent'], [])
        self.assertEqual(self.recall('growth in 10.1128/other.2019. and CGXII medium')['named_works_absent'],
                         ['10.1128/other.2019'])

    def test_reference_lists_do_not_count_towards_answering(self):
        result = self.recall('Garcia 2019 earlier work')
        self.assertTrue(result['pdf_passages'][0]['in_references'])
        self.assertLess(result['pdf_coverage'], 0.6)

    def test_a_question_in_another_language_than_the_pdfs_is_flagged(self):
        self.assertTrue(self.recall('¿Qué tasa de crecimiento se midió en el medio CGXII con la droga?')['query_language_mismatch'])
        self.assertFalse(self.recall('tasa de crecimiento CGXII medium growth rate drug')['query_language_mismatch'])

    def test_recall_next_action_puts_an_absent_named_work_first(self):
        import tempfile
        from contextlib import redirect_stdout
        from io import StringIO
        import json
        from unittest.mock import patch
        from ez.cli import main
        result = {'claims_in_project': 1, 'hits': [{'text': 'x'}], 'coverage': 0.9, 'evidence': 'partial', 'missing_words': [],
                  'pdf_passages': [], 'pdf_coverage': 0.0, 'pdfs_searched': 1, 'named_works_absent': ['Smith 2019'],
                  'query_language_mismatch': True}
        output = StringIO()
        with tempfile.TemporaryDirectory() as temp, patch('ez.vault.recall', return_value=result), \
                patch('ez.workspace.project_names', return_value={'p'}), patch('ez.cli.load_environment'), \
                redirect_stdout(output):
            main(['recall', 'Smith 2019', '--project', 'p', '--root', temp, '--json'])
        hint = json.loads(output.getvalue())['next_action']
        self.assertIn('Smith 2019 no está entre las fuentes', hint)
        self.assertIn('idioma de los artículos', hint)

    def test_recall_finds_its_project_in_the_forms_agents_write(self):
        # A live agent wrote «ez recall <run> "<q>"» and «ez recall <project> "<q>"», and a missing --project searched an
        # empty «general» project (2026-10-11).
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from ez.cli import recall_project
        from ez.contracts import ContractError
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'runs'
            (root / 'ez-0123456789abcdef').mkdir(parents=True)
            (root / 'ez-0123456789abcdef' / 'research-contract.json').write_text(
                '{"context": {"project": "ayuno"}}', encoding='utf-8')
            form = lambda *words, project=None: recall_project(root, SimpleNamespace(question=list(words), project=project))
            with patch('ez.workspace.project_names', return_value={'ayuno', 'sueno'}):
                self.assertEqual(form('ayuno', 'insulin fasting'), ('ayuno', 'insulin fasting'))
                self.assertEqual(form('ez-0123456789abcdef', 'insulin fasting'), ('ayuno', 'insulin fasting'))
                self.assertEqual(form('ayuno intermitente', project='ayuno'), ('ayuno', 'ayuno intermitente'))
                with self.assertRaisesRegex(ContractError, 'Proyectos: ayuno, sueno'):
                    form('insulin fasting')
                with self.assertRaisesRegex(ContractError, 'No hay un proyecto «otro»'):
                    form('insulin', project='otro')
            with patch('ez.workspace.project_names', return_value={'ayuno'}):
                self.assertEqual(form('insulin fasting'), ('ayuno', 'insulin fasting'))

    def test_recall_answers_are_summarized_unless_full_is_asked(self):
        # Every passage carried its whole source record: a recall weighed 31 to 39 KB in a live project (2026-10-11).
        from ez.cli import compact
        source = {'title': 'Un título', 'citation': 'Kim y Lee, 2020', 'authors': ['Kim J'] * 40, 'pdf_path': 'x' * 200}
        hit = {'marker': '[EZ:r/qa1-1]', 'citation': '(Kim y Lee, 2020)', 'text': 'Afirmación.', 'path': 'y' * 200,
               'question': 'q' * 300, 'score': 3.2, 'passages': [{'text': 'pasaje ' * 100, 'page': 2, 'source': source}] * 3}
        chunk = {'marker': '[EZ:pdf-ab-p1]', 'page': 1, 'in_references': False, 'score': 2.0, 'text': 'literal', 'source': source}
        value = compact({'kind': 'recall', 'hits': [hit], 'pdf_passages': [chunk] * 6, 'evidence': 'partial'})
        shown = value['hits'][0]
        self.assertEqual((shown['marker'], shown['text'], shown['passages'], shown['passage']['page']),
                         ('[EZ:r/qa1-1]', 'Afirmación.', 3, 2))
        self.assertLess(len(shown['passage']['text']), 260)
        self.assertNotIn('path', shown)
        self.assertEqual(len(value['pdf_passages']), 4)
        self.assertEqual(value['pdf_passages'][0]['citation'], 'Kim y Lee, 2020')
        self.assertNotIn('source', value['pdf_passages'][0])
        self.assertIn('--full', value['detail'])

    def test_draft_check_accepts_only_existing_pdf_pages(self):
        from ez.deliver import check_draft
        exists = lambda sha12, page: sha12 == 'ab' * 6 and page <= 2
        text = 'Cells in CGXII grew more slowly with the drug [EZ:pdf-' + 'ab' * 6 + '-p1]. Other claim [EZ:pdf-' + 'ab' * 6 + '-p9].'
        result = check_draft({'claims': []}, text, pdf_page=exists)
        self.assertEqual(result['unknown_markers'], ['pdf-' + 'ab' * 6 + '-p9'])
        self.assertIn('pdf-' + 'ab' * 6 + '-p1', result['claims_used'])
