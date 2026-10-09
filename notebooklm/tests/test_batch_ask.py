import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
BATCH_ASK_PATH = ROOT / "notebooklm" / "scripts" / "batch_ask.py"


def load_batch_ask():
    spec = importlib.util.spec_from_file_location("batch_ask", BATCH_ASK_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TestBatchAskCitationAudit(unittest.TestCase):
    def test_read_citation_audit_status_from_frontmatter(self):
        batch_ask = load_batch_ask()
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_ask.VAULT = Path(tmp_dir)
            note = Path(tmp_dir) / "Notes" / "NotebookLM" / "slug" / "QA" / "summaries" / "Audit.md"
            note.parent.mkdir(parents=True)
            note.write_text("---\nstatus: fail\n---\n\n- Status: PASS\n", encoding="utf-8")

            status = batch_ask.read_citation_audit_status("Notes/NotebookLM/slug/QA/summaries/Audit.md")

        self.assertEqual(status, "fail")

    def test_audit_preserves_fail_report_path(self):
        batch_ask = load_batch_ask()
        with tempfile.TemporaryDirectory() as tmp_dir:
            batch_ask.VAULT = Path(tmp_dir)
            note_rel = "Notes/NotebookLM/slug/QA/summaries/2026-07-08 Citation Audit.md"
            note = Path(tmp_dir) / note_rel
            note.parent.mkdir(parents=True)
            note.write_text("---\nstatus: fail\n---\n", encoding="utf-8")

            with patch.object(batch_ask, "run_cmd", return_value=(1, f"{note_rel}\n")):
                path, status, code = batch_ask.audit_qa_citations(
                    "questions.json",
                    "slug",
                    "Dashboard",
                    "2026-07-08",
                )

        self.assertEqual(path, note_rel)
        self.assertEqual(status, "fail")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()

