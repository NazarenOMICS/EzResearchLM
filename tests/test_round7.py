"""Round 7: open access in screening, early PDF requests, pages, bibliography export, estimates and onboarding."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.engine import Engine
from ez.state import Store, lock, read_json
import test_engine
import test_screening


class OpenAccessTests(unittest.TestCase):
    setUp = test_screening.ScreeningTests.setUp
    setUp_base = test_engine.EngineTests.setUp

    def test_screening_candidates_say_whether_they_are_open_access(self):
        self.service.discovery_records = [{'title': 'Abierto', 'doi': '10.1/aoa'}, {'title': 'Pago', 'doi': '10.1/paid'}]
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(self.folder, runner=self.service).execute(), 2)
        request = read_json(self.folder / 'screening-request.json')
        self.assertEqual({c['doi']: c['open_access'] for c in request['candidates']}, {'10.1/aoa': 'yes', '10.1/paid': 'no'})
        self.assertEqual(request['sources_hash'], Store(self.folder).state()['sources_hash'])
        lookups = sum(a[1:3] == ['-m', 'ez.openaccess'] for a in self.service.calls)
        with lock(self.folder), patch('ez.engine.executable', return_value='notebooklm'):
            Engine(self.folder, runner=self.service).execute()
        self.assertEqual(sum(a[1:3] == ['-m', 'ez.openaccess'] for a in self.service.calls), lookups)


    def test_openalex_batches_are_parsed_and_failures_stay_unknown(self):
        from ez.openaccess import lookup
        class Response:
            status_code = 200
            def json(self):
                return {'results': [{'doi': 'https://doi.org/10.1/A', 'open_access': {'is_oa': True, 'oa_status': 'green'}}]}
        class Session:
            urls = []
            def get(self, url, **kwargs):
                self.urls.append(url)
                return Response()
        session = Session()
        self.assertEqual(lookup(['10.1/a', '10.1/b'], session), {'10.1/a': {'is_oa': True, 'oa_status': 'green'}})
        self.assertEqual(len(session.urls), 1)


if __name__ == '__main__':
    unittest.main()
