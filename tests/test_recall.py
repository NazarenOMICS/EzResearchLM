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
