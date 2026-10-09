"""Verification that works with real NotebookLM behaviour, provider failures and identity routes."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ez.acquisition import verify_identity
from ez.contracts import digest
from ez.engine import Engine
from ez.process import Result
from ez.state import Store, atomic_json, lock, read_json
import test_engine

PASSAGE = 'Pasaje de prueba, sin contenido académico real.'


class GroundingTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine
    review = test_engine.EngineTests.review

    def two_claim_review(self):
        review = self.review()
        review['claims'].append({'id': 'c2', 'text': 'Segunda afirmación', 'scope_ids': ['sq1'], 'question_id': 'qa1', 'citation_numbers': [1]})
        return review

    def verify_with(self, review, verdict_answer):
        """verdict_answer(claim_ids) -> (answer text, references) or a Result for failures."""
        calls = []
        def runner(args, **kwargs):
            if args[1] == 'ask' and 'EZ_VERDICT' in args[-2]:
                ids = [c['id'] for c in json.loads(args[-2].rsplit('\n', 1)[-1])['claims']]
                calls.append(ids)
                value = verdict_answer(ids)
                if isinstance(value, Result):
                    return value
                answer, refs = value
                return Result(0, json.dumps({'answer': answer, 'references': refs}), '', None)
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            code = Engine(self.folder, runner=runner).execute(review)
        return code, calls, read_json(self.folder / 'answer.json')

    @staticmethod
    def lines(ids, quote, marker=''):
        return '\n'.join(f'EZ_VERDICT {i}: supported\nEZ_RATIONALE {i}: La fuente dice "{quote}"{marker}.' for i in ids)

    def test_missing_native_citations_are_retried_alone_then_grounded_by_a_literal_quote(self):
        self.run_engine()
        code, calls, report = self.verify_with(self.two_claim_review(), lambda ids: (self.lines(ids, PASSAGE), []))
        self.assertEqual(code, 0)
        self.assertEqual(calls, [['c1', 'c2'], ['c1'], ['c2']])
        self.assertEqual([c['verification']['grounding'] for c in report['claims']], ['quote_in_fulltext'] * 2)
        roles = [r['role'] for r in report['claims'][0]['references']]
        self.assertEqual(roles, ['qa', 'verification_quote'])
        self.assertTrue(all(r['found_in_fulltext'] for r in report['claims'][0]['references']))
        state = Store(self.folder).state()
        self.assertEqual(len(state['fulltext_receipts']), 1)

    def test_a_quote_absent_from_the_source_does_not_ground_the_verdict(self):
        self.run_engine()
        code, _, report = self.verify_with(self.review(), lambda ids: (self.lines(ids, 'Una frase que no está en la fuente'), []))
        self.assertEqual(code, 2)
        self.assertEqual(report['claims'], [])
        self.assertEqual(report['withheld_claims'][0]['reason'], 'verification_without_citations')

    def test_single_question_recovers_native_citations_lost_in_a_batch(self):
        self.run_engine()
        ref = [{'source_id': 'remote1', 'citation_number': 1, 'cited_text': PASSAGE}]
        code, calls, report = self.verify_with(self.two_claim_review(),
                                               lambda ids: (self.lines(ids, 'x' * 3), [] if len(ids) > 1 else ref) if len(ids) > 1
                                               else (self.lines(ids, PASSAGE, ' [1]'), ref))
        self.assertEqual(code, 0)
        self.assertEqual(calls, [['c1', 'c2'], ['c1'], ['c2']])
        self.assertEqual([c['verification']['grounding'] for c in report['claims']], ['native_citations'] * 2)

    def test_oversized_questions_are_split_and_a_claim_too_long_alone_is_withheld(self):
        self.run_engine()
        too_long = Result(1, '', 'Chat request was rejected by the server (status 3): the question is too large', None)
        ref = [{'source_id': 'remote1', 'citation_number': 1, 'cited_text': PASSAGE}]
        code, calls, report = self.verify_with(self.two_claim_review(),
                                               lambda ids: too_long if len(ids) > 1 or ids == ['c2'] else (self.lines(ids, PASSAGE, ' [1]'), ref))
        self.assertEqual(calls, [['c1', 'c2'], ['c1'], ['c2']])
        self.assertEqual(report['withheld_claims'][0]['id'], 'c2')
        self.assertEqual(report['withheld_claims'][0]['reason'], 'verification_question_too_long')

    def test_verification_batches_respect_the_question_size_limit(self):
        from ez.audit import VERIFICATION_PROMPT_LIMIT, verification_prompt
        self.run_engine()
        claims = [{'id': f'c{i}', 'text': 'x' * 900, 'references': []} for i in range(6)]
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            batches = Engine(self.folder, runner=self.service).verification_batches(claims)
        self.assertGreater(len(batches), 1)
        self.assertTrue(all(len(verification_prompt(b)) <= VERIFICATION_PROMPT_LIMIT for b in batches))
        self.assertEqual([c['id'] for b in batches for c in b], [c['id'] for c in claims])


class DiscoveryTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp

    def prepare(self, providers):
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            contract = read_json(self.folder / 'research-contract.json')
            contract['plan']['queries'] = [{'id': f'q{i}', 'text': 'query', 'provider': p, 'scope_ids': ['sq1']} for i, p in enumerate(providers)]
            state.update(contract_hash=digest(contract), discovery_complete=False)
            store.commit(state, {'research-contract.json': contract})

    def runner(self, args, **kwargs):
        if args[1:3] == ['-m', 'ez.discovery']:
            query = read_json(args[args.index('--query') + 1])
            output = args[args.index('--output') + 1]
            if query['provider'] == 'semantic':
                atomic_json(output, {'candidates': [], 'status': 'failed'})
                return Result(3, '', 'HTTP 429', None)
            atomic_json(output, {'candidates': [{'title': 'Found', 'doi': '10.1234/found'}], 'status': 'complete'})
            return Result(0, '{}', '', None)
        return self.service(args, **kwargs)

    def test_a_failing_provider_is_recorded_and_the_search_continues(self):
        self.prepare(['semantic', 'crossref'])
        with lock(self.folder):
            engine = Engine(self.folder, runner=self.runner)
            engine.discover()
        self.assertTrue(engine.state['discovery_complete'])
        self.assertEqual(engine.state['discovery_failures'], [{'query_id': 'q0', 'provider': 'semantic', 'reason': 'provider_error'}])
        self.assertTrue(any(s.get('doi') == '10.1234/found' for s in engine.sources))

    def test_search_pauses_only_when_every_provider_fails(self):
        from ez.engine import Pause
        self.prepare(['semantic'])
        with lock(self.folder):
            engine = Engine(self.folder, runner=self.runner)
            with self.assertRaises(Pause) as raised:
                engine.discover()
        self.assertEqual(raised.exception.reason, 'discovery_failed')


class IdentityTests(unittest.TestCase):
    title = 'Effects of benzothiazinone and ethambutol on the integrity of the corynebacterial cell envelope'

    def identity(self, header, record, provider=None):
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: header)], metadata={})
        with patch('PyPDF2.PdfReader', return_value=reader):
            return verify_identity('synthetic.pdf', record, provider)

    def test_title_with_pmc_route_or_printed_pmid_identifies_a_manuscript_without_doi(self):
        record = {'title': self.title, 'doi': '10.1016/j.tcsw.2023.100116', 'pmid': '38044953', 'pmcid': 'PMC10690000'}
        manuscript = 'Author manuscript\n' + self.title + '\nMeyer et al.'
        self.assertEqual(self.identity(manuscript, record), 'needs_review')
        self.assertEqual(self.identity(manuscript, record, 'pmc_cloud'), 'verified')
        self.assertEqual(self.identity(manuscript + '\nPMID: 38044953', record), 'verified')
        self.assertEqual(self.identity('Another paper title\nPMID: 38044953', record, 'pmc_cloud'), 'needs_review')

    def test_data_dois_after_the_article_doi_do_not_block_identity(self):
        record = {'title': self.title, 'doi': '10.1016/j.tcsw.2023.100116'}
        header = self.title + '\nhttps://doi.org/10.1016/j.tcsw.2023.100116\nData: https://doi.org/10.5281/zenodo.123'
        self.assertEqual(self.identity(header, record), 'verified')
        greek = {'title': 'The conserved σD envelope stress response monitors multiple aspects', 'doi': '10.1371/journal.pgen.1011127'}
        self.assertEqual(self.identity('The conserved σ D envelope stress response monitors multiple aspects\n'
                                       'doi:10.1371/journal.pgen.1011127', greek), 'verified')


if __name__ == '__main__':
    unittest.main()
