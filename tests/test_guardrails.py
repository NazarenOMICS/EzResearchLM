"""Guardrails for host agents: rules repeated in every JSON answer, and plan and screening built from flags."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.state import read_json
import test_screening


def call(*argv):
    output = StringIO()
    with redirect_stdout(output), patch('ez.cli.load_environment'):
        code = main([*argv, '--json'])
    return code, json.loads(output.getvalue())


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'runs'
        code, state = call('research', '¿Qué efecto tiene el etambutol en C. glutamicum?', '--plan-only', '--root', str(self.root))
        self.run = state['path']

    def tearDown(self):
        self.temp.cleanup()

    def test_every_json_answer_repeats_the_operator_rules(self):
        code, state = call('status', self.run, '--root', str(self.root))
        self.assertIn('ez ask', state['operator_reminder'])
        self.assertIn('fuente externa, no del corpus', state['operator_reminder'])

    def test_plan_is_built_from_flags_and_checked_without_touching_the_run(self):
        before = (Path(self.run) / 'events.jsonl').read_bytes()
        code, result = call('plan', self.run, '--qa', '¿Qué cambia en la pared celular?', '--qa', '¿Qué genes responden?',
                            '--query', 'pubmed:ethambutol Corynebacterium glutamicum', '--root', str(self.root))
        self.assertEqual((code, result['ready']), (0, True))
        self.assertEqual(result['estimate']['notebooklm_questions'], 2)
        proposal = read_json(result['proposal'])
        self.assertEqual([q['scope_ids'] for q in proposal['plan']['notebook_questions']], [['sq1'], ['sq2']])
        self.assertEqual(proposal['plan']['queries'][0]['provider'], 'pubmed')
        self.assertEqual((proposal['plan']['queries'][0]['max_results'], proposal['plan']['citation_expansion']), (25, True))
        self.assertIn('segunda ronda', result['estimate']['text'])
        self.assertEqual(before, (Path(self.run) / 'events.jsonl').read_bytes())
        self.assertEqual(read_json(Path(self.run) / 'research-contract.json')['plan']['status'], 'needs_host_plan')
        self.assertIn('--contract', result['choices'][0]['action'])

    def test_plan_rejects_unknown_providers_and_missing_searches(self):
        code, result = call('plan', self.run, '--qa', 'x', '--query', 'google:x', '--root', str(self.root))
        self.assertEqual(code, 4)
        self.assertIn('proveedor', result['next_action'])
        code, result = call('plan', self.run, '--qa', 'x', '--root', str(self.root))
        self.assertEqual(code, 4)
        code, result = call('plan', self.run, '--qa', 'x', '--reuse-only', '--root', str(self.root))
        self.assertEqual((code, result['ready']), (0, True))


class ScreenTests(test_screening.ScreeningTests):
    def ids(self):
        request = read_json(self.folder / 'screening-request.json')
        return {c['title']: c['source_id'] for c in request['candidates']}

    def test_screen_builds_the_decisions_from_flags(self):
        self.execute()
        ids = self.ids()
        before = (self.folder / 'events.jsonl').read_bytes()
        code, result = call('screen', str(self.folder), '--include', ids['Relevant work'] + ': estudia el efecto pedido',
                            '--key', ids['Relevant work'], '--exclude-rest', 'otro tema', '--check')
        self.assertEqual((code, result['decisions']), (0, 2))
        self.assertEqual(before, (self.folder / 'events.jsonl').read_bytes())
        document = read_json(sorted((self.folder / 'proposals').glob('screening-*.json'))[0])
        self.assertEqual({d['source_id']: (d['decision'], d.get('key')) for d in document['decisions']},
                         {ids['Relevant work']: ('include', True), ids['Off topic work']: ('exclude', None)})
        code, engine = self.execute(document)
        sources = {s['source_id']: s for s in read_json(self.folder / 'sources.json')}
        self.assertEqual((sources[ids['Off topic work']]['screening'], sources[ids['Relevant work']].get('key')), ('exclude', True))

    def test_screen_requires_a_reason_and_a_decision_for_every_candidate(self):
        self.execute()
        ids = self.ids()
        code, result = call('screen', str(self.folder), '--include', ids['Relevant work'], '--check')
        self.assertEqual(code, 4)
        code, result = call('screen', str(self.folder), '--include', ids['Relevant work'] + ': relevante', '--check')
        self.assertEqual(code, 4)
        self.assertIn('--exclude-rest', result['next_action'])
        code, result = call('screen', str(self.folder), '--exclude-rest', 'fuera', '--key', ids['Relevant work'], '--check')
        self.assertEqual(code, 4)


if __name__ == '__main__':
    unittest.main()


class FirstContactTests(unittest.TestCase):
    def test_setup_and_welcome_tell_a_new_person_what_to_ask(self):
        with tempfile.TemporaryDirectory() as temp, patch('ez.setup.executable', return_value=None):
            _, checks = call('setup', '--check', '--root', str(Path(temp) / 'runs'))
            _, welcome = call('--root', str(Path(temp) / 'runs'))
        self.assertIn('Soy EZ', checks['introduction']['say'])
        self.assertGreaterEqual(len(checks['introduction']['you_can_ask']), 4)
        self.assertEqual(welcome['you_can_ask'], checks['introduction']['you_can_ask'])

    def test_agent_facing_text_starts_onboarding_after_a_bare_download(self):
        root = Path(__file__).resolve().parents[1]
        for name in ('AGENTS.md', 'CLAUDE.md'):
            self.assertIn('## First Contact', (root / name).read_text(encoding='utf-8'))
        self.assertIn('### For the agent', (root / 'README.md').read_text(encoding='utf-8'))
        self.assertIn('### Para el agente', (root / 'README.es.md').read_text(encoding='utf-8'))

    def test_agent_facing_text_gives_no_hint_about_the_gold_set(self):
        from ez.setup import INTRODUCTION
        root = Path(__file__).resolve().parents[1]
        texts = {name: (root / name).read_text(encoding='utf-8') for name in
                 ('AGENTS.md', 'CLAUDE.md', 'docs/ez-host-operator.md', 'docs/ez-user-guide.md')}
        texts['introduction'] = json.dumps(INTRODUCTION, ensure_ascii=False)
        for name, text in texts.items():
            for topic in ('etambutol', 'ethambutol', 'glutamicum', 'smegmatis'):
                self.assertNotIn(topic, text.casefold(), name)
