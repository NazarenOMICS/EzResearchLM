"""Refactor v6, phase 1: verified claims stand on their own and review slips are corrected, not rejected."""
import json
import unittest
from unittest.mock import patch

from ez.engine import Engine
from ez.process import Result
from ez.state import lock, read_json
import test_engine
import test_phase1


class RuleTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine
    review = test_engine.EngineTests.review
    add_source = test_phase1.Phase1Tests.add_source

    def test_verification_may_cite_another_verified_source_of_the_corpus(self):
        self.add_source('s2')
        self.run_engine()
        def other_source(args, **kwargs):
            if args[1] == 'ask' and 'Evalúa si las fuentes' in args[-2]:
                answer = 'EZ_VERDICT c1: supported\nEZ_RATIONALE c1: Lo dice la otra fuente [1].'
                return Result(0, json.dumps({'answer': answer, 'references': [{'source_id': 'remote2', 'citation_number': 1,
                                             'cited_text': 'Pasaje de la segunda fuente.'}]}), '', None)
            return self.service(args, **kwargs)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(self.folder, runner=other_source).execute(self.review()), 0)
        claim = read_json(self.folder / 'answer.json')['claims'][0]
        self.assertEqual([(r['role'], r['source']['source_id']) for r in claim['references']],
                         [('qa', 's1'), ('verification', 's2')])

    def test_review_slips_are_corrected_and_recorded(self):
        self.run_engine()
        review = self.review()
        review['claims'][0].update(scope_ids=['sq1', 'sq2'], citation_numbers=[1, 2])
        self.assertEqual(self.run_engine(review)[0], 0)
        report = read_json(self.folder / 'answer.json')
        self.assertEqual(report['claims'][0]['scope_ids'], ['sq1'])
        self.assertEqual(report['claims'][0]['citation_numbers'], [1])
        self.assertEqual(report['review_adjustments'], [
            {'claim_id': 'c1', 'field': 'scope_ids', 'from': ['sq1', 'sq2'], 'to': ['sq1']},
            {'claim_id': 'c1', 'field': 'citation_numbers', 'from': [1, 2], 'to': [1]}])

    def test_a_claim_without_any_cited_passage_is_still_rejected(self):
        self.run_engine()
        review = self.review()
        review['claims'][0]['citation_numbers'] = [5]
        code, state = self.run_engine(review)
        self.assertEqual((code, state['legacy_signals']), (2, ['review_invalid']))


if __name__ == '__main__':
    unittest.main()
