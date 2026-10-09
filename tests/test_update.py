"""Phase 5: updating a research run, human checks and number warnings."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.engine import Engine, numbers_missing
from ez.metrics import collect
from ez.state import Store, lock, read_json
import test_engine


def review_for(folder, claims):
    state = Store(folder).state()
    return {'schema_version': '2.0', 'contract_hash': state['contract_hash'], 'corpus_hash': state['corpus_hash'],
            'reviewer': {'kind': 'host_agent', 'name': 'EZ'},
            'coverage': [{'scope_id': 'sq1', 'status': 'sufficient', 'rationale': 'QA citada revisada', 'limitations': []},
                         {'scope_id': 'sq2', 'status': 'insufficient', 'rationale': 'Falta fuente', 'limitations': ['Fuente requerida ausente']}],
            'claims': claims}


CLAIM = {'id': 'c1', 'text': 'Afirmación de prueba', 'scope_ids': ['sq1'], 'question_id': 'qa1', 'citation_numbers': [1]}


class UpdateTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine

    def cli(self, *arguments):
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main(['--root', self.temp.name, *arguments, '--json'])
        return code, json.loads(output.getvalue())

    def deliver(self, claims=(CLAIM,)):
        self.run_engine()
        self.assertEqual(self.run_engine(review_for(self.folder, list(claims)))[0], 0)

    def test_update_reuses_plan_sources_and_decisions_and_reports_changes(self):
        self.deliver()
        with lock(self.folder):
            store = Store(self.folder); state = store.state()
            sources = read_json(self.folder / 'sources.json')
            sources.append({'source_id': 'off', 'title': 'Fuera de tema', 'doi': '10.1/off', 'screening': 'exclude',
                            'screening_reason': 'Otro organismo', 'acquisition_status': 'pending', 'validation_status': 'unknown',
                            'identity_status': 'unknown', 'notebook_status': 'pending'})
            from ez.contracts import digest
            state['sources_hash'] = digest(sources)
            store.commit(state, {'sources.json': sources})
        code, created = self.cli('research', 'Pregunta de prueba', '--update', str(self.folder))
        self.assertEqual(code, 0)
        new = Path(created['path'])
        self.assertEqual(read_json(new / 'research-contract.json')['plan'], read_json(self.folder / 'research-contract.json')['plan'])
        sources = {s['source_id']: s for s in read_json(new / 'sources.json')}
        self.assertEqual(sources['off']['screening'], 'exclude')
        self.assertTrue(sources['s1']['reused_from'])
        service = test_engine.Service()
        with lock(new), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(new, runner=service).execute(), 2)
        claims = [CLAIM, dict(CLAIM, id='c2', text='Otra afirmación nueva')]
        with lock(new), patch('ez.engine.executable', return_value='notebooklm'):
            self.assertEqual(Engine(new, runner=service).execute(review_for(new, claims)), 0)
        changes = read_json(new / 'answer.json')['changes']
        self.assertEqual((changes['previous_run'], changes['kept'], changes['new'], changes['dropped']),
                         (Store(self.folder).state()['run_id'], ['c1'], ['c2'], []))
        self.assertIn('Cambios respecto de la versión anterior', (new / 'report.md').read_text(encoding='utf-8'))
        code, result = self.cli('research', 'Otra pregunta distinta', '--update', str(self.folder))
        self.assertEqual(code, 4)

    def test_a_person_can_withdraw_a_claim_and_the_judgement_survives_reverification(self):
        self.deliver()
        asks = sum(a[1] == 'ask' for a in self.service.calls)
        code, sample = self.cli('verify', str(self.folder))
        self.assertEqual((code, [c['id'] for c in sample['claims']]), (0, ['c1']))
        with patch('ez.engine.Engine.__init__.__defaults__', (self.service,)), patch('ez.engine.executable', return_value='notebooklm'):
            code, state = self.cli('verify', str(self.folder), '--claim', 'c1', '--judgement', 'unsupported', '--note', 'No lo dice')
        self.assertEqual(code, 0)
        answer = read_json(self.folder / 'answer.json')
        self.assertEqual((answer['claims'], answer['withheld_claims'][0]['reason']), ([], 'human_rejected'))
        self.assertEqual(sum(a[1] == 'ask' for a in self.service.calls), asks)
        self.assertEqual(collect(self.folder)['human_citation_review'], {'unsupported': 1, 'checked': 1})
        self.run_engine()
        self.assertEqual(read_json(self.folder / 'answer.json')['claims'], [])

    def test_numbers_absent_from_the_passages_are_flagged(self):
        self.deliver([dict(CLAIM, text='La inducción fue de 19,1 veces en 2024')])
        claim = read_json(self.folder / 'answer.json')['claims'][0]
        self.assertEqual(claim['warnings'], [{'code': 'numbers_not_in_passages', 'values': ['19.1', '2024']}])
        self.assertEqual(numbers_missing('aumentó 19.1 veces', ['(19,1-fold increase)']), [])


if __name__ == '__main__':
    unittest.main()
