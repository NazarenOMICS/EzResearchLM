from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.benchmark_recovery import execute, summarize, validate_corpus
from ez.process import Result


class RecoveryBenchmarkTests(unittest.TestCase):
    def corpus(self):
        base = {'kind': 'eligible', 'eligibility_url': 'https://publisher.example/paper',
                'checked_at': '2026-09-20', 'accepted_version': 'published',
                'record': {'title': 'Synthetic test article', 'doi': '10.1234/test', 'pdf_url': 'https://publisher.example/paper.pdf'}}
        return {'cases': [dict(deepcopy(base), case_id='paper'),
                          dict(deepcopy(base), case_id='control', kind='negative_control')]}

    def test_timeouts_and_unattempted_cases_remain_in_denominator(self):
        cases = self.corpus()['cases']
        summary = summarize(cases, [{'case_id': 'paper', 'failure_code': 'deadline_exceeded'}])
        self.assertEqual(summary['eligible_works'], 1)
        self.assertEqual(summary['structurally_valid'], 0)
        self.assertEqual(summary['control_inconclusive'], 1)
        self.assertIsNone(summary['accepted_recovery_rate'])

    def test_structure_and_automatic_identity_never_imply_independent_acceptance(self):
        cases = self.corpus()['cases']
        rows = [{'case_id': 'paper', 'validation_status': 'valid', 'identity_status': 'needs_review'},
                {'case_id': 'control', 'validation_status': 'valid', 'identity_status': 'verified'}]
        summary = summarize(cases, rows)
        self.assertEqual(summary['identity_review_pending'], 1)
        self.assertEqual(summary['control_false_acceptances'], 1)
        self.assertFalse(summary['release_ready'])
        self.assertIsNone(summary['independently_accepted'])

    def test_corpus_rejects_duplicate_works_path_escape_and_consent(self):
        corpus = self.corpus()
        validate_corpus(corpus)
        for change in ('duplicate', 'escape', 'consent'):
            bad = deepcopy(corpus)
            if change == 'duplicate':
                bad['cases'][1]['kind'] = 'eligible'
                bad['cases'][1]['record']['doi'] = 'https://doi.org/10.1234/TEST'
            elif change == 'escape':
                bad['cases'][0]['case_id'] = '../outside'
            else:
                bad['cases'][0]['record']['anna_consent'] = {}
            with self.assertRaises(ValueError):
                validate_corpus(bad)

    def test_failed_worker_retains_evidence_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp, patch('scripts.benchmark_recovery.run', return_value=Result(124, '', '', 'deadline_exceeded')) as worker:
            folder = Path(temp) / 'pilot'
            result = execute(self.corpus(), folder, seconds=1)
            self.assertEqual(len(result['results']), 2)
            self.assertEqual(result['summary']['eligible_works'], 1)
            self.assertTrue((folder / 'corpus.json').is_file())
            self.assertTrue((folder / 'runner.py').is_file())
            commands = [call.args[0] for call in worker.call_args_list]
            self.assertEqual(commands[0][1:4], ['-I', '-m', 'ez.acquisition'])
            self.assertEqual(commands[1][1:3], ['-I', '-c'])
            self.assertIn('candidates=[', commands[1][3])
            with self.assertRaises(FileExistsError):
                execute(self.corpus(), folder, seconds=1)
