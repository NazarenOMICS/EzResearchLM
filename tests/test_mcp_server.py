"""Phase 6: the Claude Desktop adapter runs the same ez commands and exposes only run files."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez import mcp_server
from ez.state import read_json


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.dict(os.environ, {'EZRESEARCH_RUNS_ROOT': self.temp.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_research_read_and_submit_go_through_the_ez_cli(self):
        created = mcp_server.ez_research('Pregunta de prueba', 'demo')
        self.assertEqual(created['exit_code'], 0)
        run = created['run_id']
        contract = mcp_server.ez_read(run, 'research-contract.json')
        self.assertIn('Pregunta de prueba', contract['text'])
        self.assertIn('Lee research-contract.json', mcp_server.ez_read(run, 'host-request.md')['text'])
        proposal = read_json(Path(self.temp.name) / run / 'research-contract.json')
        proposal['plan']['stop_rule'] = ''
        checked = mcp_server.ez_submit(run, 'contract', proposal, check=True)
        self.assertEqual((checked['exit_code'], checked['valid'], checked['ready']), (0, True, False))
        self.assertEqual(read_json(Path(self.temp.name) / run / 'research-contract.json')['revision'], 1)
        status = mcp_server.ez_status(run)
        self.assertEqual(status['phase'], 'plan')

    def test_only_run_working_files_are_readable(self):
        run = mcp_server.ez_research('Pregunta', 'demo')['run_id']
        for name in ('../secret.txt', 'events.jsonl', 'qa/../../x.json', '/etc/passwd'):
            self.assertIn('error', mcp_server.ez_read(run, name), name)
        self.assertEqual(mcp_server.ez_submit(run, 'other', {})['error'], 'kind_invalid')
        self.assertEqual(mcp_server.ez_verify(run, claim='c1')['error'], 'judgement_required')

    def test_guide_is_available_to_the_agent(self):
        self.assertIn('Primera conversación', mcp_server.ez_guide())

    @unittest.skipUnless(importlib.util.find_spec('mcp'), 'mcp extra not installed')
    def test_server_registers_every_tool(self):
        import asyncio
        server = mcp_server.build_server()
        names = sorted(tool.name for tool in asyncio.run(server.list_tools()))
        self.assertEqual(names, sorted(tool.__name__ for tool in mcp_server.TOOLS))
        manifest = read_json(Path(__file__).resolve().parents[1] / 'desktop/manifest.json')
        self.assertEqual(sorted(t['name'] for t in manifest['tools']), names)


if __name__ == '__main__':
    unittest.main()
