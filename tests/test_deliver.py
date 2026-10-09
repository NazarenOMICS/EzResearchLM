"""Phase 3: the evidence report and drafting only from verified claims."""
from contextlib import redirect_stdout
from io import StringIO
import json
import unittest
from unittest.mock import patch

from ez.cli import main
from ez.doctor import diagnose
import test_engine


class DeliverTests(unittest.TestCase):
    setUp = test_engine.EngineTests.setUp
    run_engine = test_engine.EngineTests.run_engine
    review = test_engine.EngineTests.review

    def deliver(self):
        self.run_engine()
        self.assertEqual(self.run_engine(self.review())[0], 0)

    def cli(self, *arguments):
        output = StringIO()
        with redirect_stdout(output), patch('ez.cli.load_environment'):
            code = main([*arguments, '--json'])
        return code, json.loads(output.getvalue())

    def test_report_is_deterministic_cites_sources_and_explains_gaps(self):
        self.deliver()
        report = (self.folder / 'report.md').read_text(encoding='utf-8')
        self.assertIn('**Pregunta:** Pregunta de prueba', report)
        self.assertIn('- Afirmación de prueba [1] `[EZ:c1]`', report)
        self.assertIn('1. Fuente de prueba.', report)
        self.assertIn('«Pasaje de prueba, sin contenido académico real.»', report)
        self.assertIn('- Pendiente: una fuente obligatoria no se encontró.', report)
        self.assertIn('verificación automática', report)
        before = (self.folder / 'report.md').read_bytes()
        self.assertEqual(self.run_engine()[0], 0)
        self.assertEqual((self.folder / 'report.md').read_bytes(), before)
        code, answer = self.cli('status', str(self.folder), '--answer')
        self.assertEqual((code, answer['report_path']), (0, str(self.folder / 'report.md')))

    def test_doctor_notices_an_edited_report_without_failing_the_run(self):
        self.deliver()
        (self.folder / 'report.md').write_text('editado', encoding='utf-8')
        diagnosis = diagnose(self.folder)
        self.assertTrue(diagnosis['healthy'])
        self.assertIn('report_edited', [f['code'] for f in diagnosis['findings']])

    def test_drafts_may_cite_only_delivered_claims(self):
        self.deliver()
        code, material = self.cli('draft', str(self.folder))
        self.assertEqual((code, material['claims'][0]['marker']), (0, '[EZ:c1]'))
        draft = self.folder.parent / 'borrador.md'
        draft.write_text('# Título\n\nLa afirmación verificada se sostiene en la fuente citada [EZ:c1]. '
                         'Esta otra oración afirma algo de la literatura sin ningún marcador visible.\n', encoding='utf-8')
        code, result = self.cli('draft', str(self.folder), '--check', str(draft))
        self.assertEqual((code, result['valid'], result['claims_used'], result['unmarked_count']), (0, True, ['c1'], 1))
        draft.write_text('Una afirmación inventada por el redactor sin respaldo alguno [EZ:c9].', encoding='utf-8')
        code, result = self.cli('draft', str(self.folder), '--check', str(draft))
        self.assertEqual((code, result['valid'], result['unknown_markers']), (4, False, ['c9']))

    def test_draft_refuses_runs_without_verified_claims(self):
        self.run_engine()
        code, result = self.cli('draft', str(self.folder))
        self.assertEqual(code, 4)
        self.assertIn('afirmaciones verificadas', result['next_action'])


if __name__ == '__main__':
    unittest.main()
