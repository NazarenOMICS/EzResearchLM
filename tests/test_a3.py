"""The A3 comparison kit: copied answers become a blind, shuffled sheet and a report of counts only."""
import csv
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'gold_set_benchmark' / 'a3.py'
spec = importlib.util.spec_from_file_location('a3', PATH)
a3 = importlib.util.module_from_spec(spec)
# a3.py puts packages/paper_search first on the path, and its own `tests` would shadow this suite's.
saved_path = list(sys.path)
spec.loader.exec_module(a3)
sys.path[:] = saved_path

CHATGPT = """# Respuesta

FAIR define cuatro principios para que los datos sean encontrables y reutilizables. ([nature.com](https://www.nature.com/articles/sdata201618))

Cada conjunto de datos debe tener un identificador persistente asignado por un registro [1].

## Referencias

1. Inventado A. Un artículo que no existe. doi:10.9999/no.existe
"""
NOTEBOOKLM = "Los principios también se aplican a los algoritmos y flujos de trabajo que generaron los datos [1].\n\n## Fuentes\n[1] wilkinson_2016.pdf\n"


class ComparisonKitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        work = Path(self.temp.name) / 'a3'
        (work / 'respuestas').mkdir(parents=True)
        (work / 'respuestas' / 'chatgpt_M1.md').write_text(CHATGPT, encoding='utf-8')
        (work / 'respuestas' / 'notebooklm_M1.md').write_text(NOTEBOOKLM, encoding='utf-8')
        run = Path(self.temp.name) / 'run'
        run.mkdir()
        (run / 'answer.json').write_text(json.dumps({'claims': [{
            'id': 'c1', 'text': 'Los metadatos deben seguir accesibles aunque los datos ya no estén disponibles [EZ:c1].',
            'references': [{'source': {'doi': '10.1038/sdata.2016.18', 'authors': ['Mark D. Wilkinson'], 'year': 2016}}]}]}),
            encoding='utf-8')
        self.work, self.run = work, run
        patcher = patch.object(a3, 'WORK', work)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_answers_become_a_blind_sheet_and_a_report_without_their_texts(self):
        exists = {'10.1038/sdata.2016.18': 'si', '10.9999/no.existe': 'no'}
        with patch.object(a3, 'doi_exists', lambda doi, session: exists[doi]):
            sheet, key = a3.prepare({'M1': str(self.run)}, check_dois=True)
        self.assertEqual(sorted(k['sistema'] for k in key), ['chatgpt', 'chatgpt', 'ez', 'notebooklm'])
        text = ' '.join(r['afirmacion'] for r in sheet)
        for leak in ('[EZ:', '[1]', 'http', 'nature.com', 'Referencias', 'Respuesta'):
            self.assertNotIn(leak, text)
        by_text = {r['afirmacion'][:20]: r for r in sheet}
        self.assertIn('sdata201618', by_text['FAIR define cuatro p']['fuente_citada'])  # the link left at the paragraph's end
        self.assertEqual(by_text['Cada conjunto de dat']['doi_existe'], 'no')
        self.assertEqual(by_text['Los principios tambi']['fuente_citada'], 'wilkinson_2016.pdf')
        self.assertEqual(by_text['Los metadatos deben ']['doi_existe'], 'si')

        rows = a3.read_rows(self.work / 'planilla_ciega.csv')
        for row in rows:
            row['puntaje'] = '0' if row['doi_existe'] == 'no' else '3'
        a3.write_rows(self.work / 'planilla_ciega.csv', a3.SHEET, rows)
        with (self.work / 'registro.csv').open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=a3.LOG)
            writer.writeheader()
            writer.writerow({'sistema': 'ez', 'mision': 'M1', 'minutos': '6,5', 'lagunas_declaradas': '1', 'lagunas_esperadas': '1'})
        report = a3.results()
        self.assertIn('| referencias inventadas | 0 de 1 | 1 de 2 | 0 de 1 |', report)
        self.assertIn('| minutos | 6.5 | — | — |', report)
        self.assertIn('EZ supera o iguala', report)
        self.assertNotIn('identificador persistente', report)

    def test_rows_marked_as_not_claims_are_left_out_and_blanks_stop_the_report(self):
        a3.prepare({'M1': str(self.run)})
        rows = a3.read_rows(self.work / 'planilla_ciega.csv')
        a3.write_rows(self.work / 'planilla_ciega.csv', a3.SHEET, rows)
        with self.assertRaises(SystemExit):
            a3.results()
        for row in rows:
            row['puntaje'] = '-'
        rows[0]['puntaje'] = '2'
        a3.write_rows(self.work / 'planilla_ciega.csv', a3.SHEET, rows)
        self.assertIn('| afirmaciones | 1 |', a3.results())
        self.assertEqual(len(a3.rescore_sample()), 1)


if __name__ == '__main__':
    unittest.main()
