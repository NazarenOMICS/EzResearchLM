import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

AUDIT = Path(__file__).resolve().parents[1] / 'scripts/audit_qa_citations.py'


class AuditIntegrityTests(unittest.TestCase):
    def audit(self, folder, questions):
        path = Path(folder) / 'questions.json'
        path.write_text(json.dumps({'questions': questions}), encoding='utf-8')
        return subprocess.run([sys.executable, str(AUDIT), '--questions', str(path), '--slug', 'example', '--dashboard', 'Example'], cwd=folder, capture_output=True, timeout=10)

    def test_empty_audit_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertNotEqual(self.audit(folder, []).returncode, 0)

    def test_anchor_must_exist(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'Notes/NotebookLM/example/Sources/Paper.md'
            source.parent.mkdir(parents=True)
            source.write_text('# Paper\n\n## Passage 1\n\nSynthetic excerpt.', encoding='utf-8')
            qa = Path(folder) / 'qa.md'
            qa.write_text('Statement [[Notes/NotebookLM/example/Sources/Paper#Passage 2|[1]]]', encoding='utf-8')
            questions = [{'question': 'Test?', 'vault_note': 'qa.md'}]
            self.assertNotEqual(self.audit(folder, questions).returncode, 0)
            qa.write_text(qa.read_text().replace('Passage 2', 'Passage 1'), encoding='utf-8')
            self.assertEqual(self.audit(folder, questions).returncode, 0)
