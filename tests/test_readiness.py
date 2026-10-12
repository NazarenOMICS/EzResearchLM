"""Before the live test (2026-10-12): output size, gold-set hints, legacy config, moved projects and recall speed."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez.cli import compact

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {'source_id': 's1', 'title': 'A long title of the work', 'authors': ['Kim J', 'Lee S'], 'year': 2020,
          'doi': '10.1/x', 'pmid': '1', 'journal': 'J', 'content_sha256': 'ab' * 32, 'pdf_path': 'C:/runs/ez-1/x.pdf',
          'pdf_source': 'pmc', 'origin_url': 'https://example.org/x.pdf', 'source_version': 'v1'}


class CompactPassagesNameTheirWorkOnly(unittest.TestCase):
    """Every passage carried its whole source record: recall grew from 6 to 14-18 KB after the audit fixes."""
    def test_claim_and_recall_passages_keep_id_and_citation_but_not_the_record(self):
        claim = {'id': 'q1', 'text': 'T', 'context': 'Adults', 'references': [
            {'source_id': 's1', 'page': 2, 'cited_text': 'P', 'source': SOURCE}]}
        shown = compact({'claims': [claim]})['claims'][0]
        self.assertEqual(shown['passage_sources'], [{'source_id': 's1', 'page': 2, 'citation': 'Kim y Lee, 2020'}])
        hit = {'marker': '[EZ:r/a]', 'text': 'T', 'question': 'q', 'passages': [{'text': 'P', 'page': 2, 'source': SOURCE}]}
        passage = compact({'kind': 'recall', 'hits': [hit], 'pdf_passages': []})['hits'][0]['passage']
        self.assertEqual(passage['source'], {'source_id': 's1', 'citation': 'Kim y Lee, 2020'})
        self.assertNotIn('pdf_path', json.dumps(compact({'kind': 'recall', 'hits': [hit], 'pdf_passages': []})))


class OperatorTextNamesNoGoldSetTopic(unittest.TestCase):
    TOPICS = ('etambutol', 'ethambutol', 'glutamicum', 'smegmatis', 'radmacher', 'alderwick', 'corynebact',
              'mycobact', 'arabinogalact', 'embc')

    def test_readmes_setup_help_and_mcp_text_name_no_gold_set_topic(self):
        # The guide was checked; the operator also reads the READMEs, ez … --help and the MCP tool texts.
        names = ('README.md', 'README.es.md', 'SETUP.md', 'desktop/README.md', 'docs/carpetas.md',
                 'packages/ez/cli.py', 'packages/ez/setup.py', 'packages/ez/mcp_server.py', 'packages/ez/presenter.py')
        for name in names:
            text = (ROOT / name).read_text(encoding='utf-8').casefold()
            for topic in self.TOPICS:
                self.assertFalse(topic in text, f'{name} nombra «{topic}»')


class LegacyConfigStaysReadable(unittest.TestCase):
    def test_a_root_not_named_runs_still_reads_the_config_beside_it(self):
        # Before 2026-10-12 the config sat next to any runs root; moving it to the root itself lost projects_dir.
        from ez.paths import load_user_config
        from ez.workspace import projects_home
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp).resolve()
            root = base / 'researches'
            root.mkdir()
            (base / 'ez-config.json').write_text(json.dumps({'projects_dir': str(base / 'visible'),
                                                             'unpaywall_email': 'a@b.org'}), encoding='utf-8')
            self.assertEqual(projects_home(root), base / 'visible')
            with patch.dict('os.environ', {}, clear=False):
                load_user_config(root)
                import os
                self.assertEqual(os.environ.get('PAPER_SEARCH_MCP_UNPAYWALL_EMAIL'), 'a@b.org')


class MovedProjectsSayWhereTheyWent(unittest.TestCase):
    def test_the_old_folder_and_its_inboxes_point_to_the_new_one(self):
        from ez.setup import prepare
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root, first, second = base / 'runs', base / 'A', base / 'B'
            with patch('ez.setup.executable', return_value=None):
                prepare(root, projects_dir=first)
                (first / 'tesis' / 'inbox').mkdir(parents=True)
                checks = prepare(root, projects_dir=second)
            self.assertEqual(Path(checks['projects_moved_from']), first.resolve())
            for notice in (first / 'MOVED.md', first / 'tesis' / 'inbox' / 'MOVED.md'):
                self.assertIn(str(second.resolve()), notice.read_text(encoding='utf-8'))
            self.assertFalse((second / 'MOVED.md').exists())
            self.assertFalse((second / 'tesis' / 'inbox' / 'MOVED.md').exists())


class RecallReadsEachRunOnce(unittest.TestCase):
    def test_a_verified_journal_is_not_rechecked_until_it_changes(self):
        from ez.contracts import ContractError
        from ez.state import Store
        import ez.state
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp))
            store.append('state', {'run_id': 'r'})
            store.events()
            with patch('ez.state.digest', wraps=ez.state.digest) as hashed:
                store.events()
            self.assertEqual(hashed.call_count, 0)
            raw = store.journal.read_bytes().replace(b'"r"', b'"x"')
            store.journal.write_bytes(raw)
            with self.assertRaises(ContractError):
                store.events()

    def test_recall_lists_the_project_runs_once(self):
        import ez.context
        from ez.vault import recall
        with tempfile.TemporaryDirectory() as temp, \
                patch('ez.context.history', wraps=ez.context.history) as listed:
            recall(Path(temp) / 'runs', 'p', 'growth rate')
        self.assertEqual(listed.call_count, 1)


if __name__ == '__main__':
    unittest.main()
