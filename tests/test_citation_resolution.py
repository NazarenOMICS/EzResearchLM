import unittest

from ez.citation_resolution import resolve_quotes


class CitationResolutionTests(unittest.TestCase):
    def setUp(self):
        self.quote = 'This synthetic source reports a specific change to the documented research procedure.'
        self.response = {'answer': '> *"' + self.quote + '"* [1]',
                         'references': [{'source_id': 's', 'citation_number': 1, 'cited_text': None}]}
        self.texts = {'s': {'source_id': 's', 'content': 'Header\n' + self.quote + '\nFooter'}}

    def test_unique_quote_resolves_without_overwriting_raw_response(self):
        resolved = resolve_quotes(self.response, self.texts)
        self.assertEqual(resolved['references'][0]['cited_text'], self.quote)
        self.assertIsNone(self.response['references'][0]['cited_text'])
        self.assertEqual(resolved['references'][0]['resolution']['normalized_offset'], 7)

    def test_ambiguous_or_absent_quote_stays_unresolved(self):
        for content in (self.quote + self.quote, 'A different source text.'):
            self.texts['s']['content'] = content
            self.assertIsNone(resolve_quotes(self.response, self.texts)['references'][0]['cited_text'])

    def test_paraphrase_or_foreign_source_cannot_supply_a_passage(self):
        self.response['answer'] = self.quote + ' [1]'
        self.assertIsNone(resolve_quotes(self.response, self.texts)['references'][0]['cited_text'])
        self.response['answer'] = '"' + self.quote + '" [1]'
        self.texts['s']['source_id'] = 'foreign'
        self.assertIsNone(resolve_quotes(self.response, self.texts)['references'][0]['cited_text'])

    def test_only_whitespace_and_unicode_normalization_are_allowed(self):
        self.texts['s']['content'] = self.quote.replace('specific change', 'specific\n change')
        self.assertEqual(resolve_quotes(self.response, self.texts)['references'][0]['cited_text'], self.quote)
        self.texts['s']['content'] = self.quote.replace('specific change', 'SPECIFIC CHANGE')
        self.assertIsNone(resolve_quotes(self.response, self.texts)['references'][0]['cited_text'])
