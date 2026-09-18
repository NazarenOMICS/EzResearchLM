import unittest

from ez.audit import references, support_verdict
from ez.contracts import ContractError


class CitationFormatsTests(unittest.TestCase):
    def setUp(self):
        self.sources = [{'notebook_source_id': 's', 'notebook_status': 'ready',
                         'validation_status': 'valid', 'identity_status': 'verified'}]
        self.response = {'answer': 'Resultado [1, 2]. Límites [3–5].', 'references': [
            {'source_id': 's', 'citation_number': n, 'cited_text': 'Pasaje sintético'} for n in range(1, 6)]}

    def test_grouped_and_ranged_markers_preserve_every_reference(self):
        self.assertEqual(set(references(self.response, self.sources)), {1, 2, 3, 4, 5})

    def test_missing_passage_inside_group_cannot_hide_behind_valid_single_marker(self):
        self.response['answer'] += ' Otra cita [1].'
        self.response['references'][3]['cited_text'] = None
        with self.assertRaises(ContractError):
            references(self.response, self.sources)

    def test_invalid_range_fails_closed(self):
        for marker in ('[5-3]', '[0]', '[1-100000000]', '[1,,2]'):
            self.response['answer'] = 'Resultado ' + marker
            with self.assertRaises(ContractError):
                references(self.response, self.sources)

    def test_review_can_select_supported_claim_without_delivering_unverified_draft(self):
        self.response['references'][3]['cited_text'] = None
        self.assertEqual(set(references(self.response, self.sources, [1, 2])), {1, 2})
        for numbers in ([4], [6]):
            with self.assertRaises(ContractError):
                references(self.response, self.sources, numbers)
        self.response['references'][3]['source_id'] = 'foreign'
        with self.assertRaises(ContractError):
            references(self.response, self.sources, [1])

    def test_native_support_protocol_requires_real_citation_objects(self):
        self.response['answer'] = 'EZ_VERDICT: supported\nEZ_RATIONALE: Pasaje de respaldo [1, 2].'
        self.assertEqual(support_verdict(self.response, self.sources, {'s'})['verdict'], 'supported')
        self.response['references'] = []
        with self.assertRaises(ContractError):
            support_verdict(self.response, self.sources, {'s'})
