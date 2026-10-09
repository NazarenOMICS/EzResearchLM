import logging
import unittest
from unittest.mock import patch

from ez.discovery import search


class DiscoveryTests(unittest.TestCase):
    def test_swallowed_provider_failure_is_not_a_successful_empty_search(self):
        def failed(*args, **kwargs):
            logging.getLogger('paper_search_mcp.academic_platforms.crossref').error('HTTP 429 simulated')
            return []
        with patch('search_topic.search_single', side_effect=failed):
            result = search({'provider': 'crossref', 'text': 'query'})
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['failure_code'], 'provider_error')

    def test_successful_zero_results_and_partial_parse_are_distinct(self):
        with patch('search_topic.search_single', return_value=[]):
            self.assertEqual(search({'provider': 'crossref', 'text': 'query'})['status'], 'complete')
        def partial(*args, **kwargs):
            logging.getLogger('paper_search_mcp.academic_platforms.crossref').warning('Skipped item')
            return [{'title': 'Synthetic fixture'}]
        with patch('search_topic.search_single', side_effect=partial):
            result = search({'provider': 'crossref', 'text': 'query'})
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(len(result['candidates']), 1)
