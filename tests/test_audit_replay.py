"""Synthetic, neutral checks for the offline audit replay helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.replay_audit import (
    answer_replay,
    citation_expansion_replay,
    contract_replay,
    discovery_replay,
    inventory,
    last_author_notes_replay,
    lossless_bytes_replay,
    main,
    qa_replay,
    screening_replay,
)


class ReplayAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_json(self, relative: str, value: object) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_inventory_hashes_unique_content_and_skips_sensitive_names(self) -> None:
        (self.root / "runs").mkdir()
        (self.root / "runs" / "one.txt").write_bytes(b"abc")
        (self.root / "runs" / "two.txt").write_bytes(b"abc")
        (self.root / "runs" / "token-cache.json").write_text("ignored", encoding="utf-8")

        result = inventory(self.root / "runs")

        self.assertEqual(result["file_count"], 2)
        self.assertEqual(result["unique_content_count"], 1)
        self.assertEqual(result["logical_bytes"], 6)
        self.assertEqual(result["unique_content_bytes"], 3)

    def test_discovery_reports_raw_records_per_query_without_deduplication(self) -> None:
        base = "runs/run-a/discovery/0"
        query = {"provider": "synthetic-provider", "text": "neutral query"}
        self.write_json(f"{base}/queries.json", query)
        self.write_json(f"{base}/candidate-sources.json", {"status": "complete", "candidates": [{"id": "a"}, {"id": "a"}, {"id": "b"}]})

        result = discovery_replay(self.root)

        self.assertEqual(result["session_count"], 1)
        self.assertEqual(result["candidate_record_count_raw"], 3)
        self.assertEqual(result["candidate_records_by_provider"], {"synthetic-provider": 3})

    def test_screening_reports_candidate_and_decision_sets_separately(self) -> None:
        self.write_json(
            "runs/run-b/screening-request.json",
            {"candidates": [{"id": "a"}, {"id": "b"}], "decisions": [{"id": "a", "decision": "include"}]},
        )

        result = screening_replay(self.root)

        self.assertEqual(result["runs"][0]["candidate_count"], 2)
        self.assertEqual(result["runs"][0]["decision_count"], 1)
        self.assertEqual(result["runs"][0]["decisions_by_status"], {"include": 1})

    def test_qa_only_counts_nonempty_answers_and_explicit_labels(self) -> None:
        self.write_json("runs/run-c/qa/one.json", {"answer": "Synthetic answer", "sufficiency": "sufficient"})
        self.write_json("runs/run-c/qa/two.json", {"answer": "  "})
        self.write_json("runs/run-c/qa/manifest.json", {"answers": ["not counted as a turn"]})

        result = qa_replay(self.root)

        self.assertEqual(result["qa_file_count"], 2)
        self.assertEqual(result["nonempty_answer_count"], 1)
        self.assertEqual(result["explicit_machine_status_counts"], {"sufficient": 1})
        self.assertFalse(result["scientific_completeness_assessed"])

    def test_answer_counts_saved_claims_and_preserves_delivery_label(self) -> None:
        self.write_json(
            "runs/run-d/answer.json",
            {"delivery": "direct", "claims": [{"id": 1, "text": r"\(a+b\)"}, {"id": 2, "text": "plain text"}]},
        )

        result = answer_replay(self.root)

        self.assertEqual(result["answer_file_count"], 1)
        self.assertEqual(result["claim_count_all_saved_answers"], 2)
        self.assertEqual(result["direct_claim_count"], 2)
        self.assertEqual(result["direct_claims_with_base_audit_latex_delimiters"], 1)
        self.assertEqual(result["runs"][0]["delivery"], "direct")

    def test_citation_expansion_replays_merge_filter_and_top_40(self) -> None:
        run = "runs/ez-synthetic"
        self.write_json(f"{run}/research-contract.json", {
            "question": {"original": "neutral query"},
            "plan": {"queries": [], "notebook_questions": []},
        })
        self.write_json(f"{run}/discovery/citations-request.json", [{"source_id": "seed-a"}])
        self.write_json(f"{run}/discovery/citations.json", {
            "records": [
                {"doi": "https://doi.org/10.1234/merge", "title": "Record One", "authors": "Example, A.", "year": "2020", "abstract": "Neutral wording.", "links": [{"seed": "seed-a"}]},
                {"doi": "doi: 10.1234/merge.", "title": "Record One", "authors": "Example, A.", "year": "2020", "abstract": "Neutral wording.", "links": [{"seed": "seed-b"}]},
                {"doi": "10.9999/existing", "title": "Already known", "authors": "Example, B.", "year": "2021", "links": [{"seed": "seed-a"}]},
            ],
            "failures": 0,
        })
        source_key = "10.1234/merge"
        source_id = "src-" + __import__("hashlib").sha256(source_key.encode()).hexdigest()[:20]
        self.write_json(f"{run}/sources.json", [
            {"source_id": "existing", "doi": "https://doi.org/10.9999/existing", "title": "Already known", "authors": "Example, B.", "year": "2021"},
            {"source_id": source_id, "doi": source_key, "title": "Record One", "authors": "Example, A.", "year": "2020", "discovery_origin": "citations"},
        ])
        self.write_json(f"{run}/run-state.json", {"citation_expansion": {"found": 1, "added": 1, "seeds": 1}})

        result = citation_expansion_replay(self.root)["runs"][0]

        self.assertEqual(result["raw_record_count"], 3)
        self.assertEqual(result["existing_source_identity_exclusions"], 1)
        self.assertEqual(result["duplicate_identity_records_merged"], 1)
        self.assertEqual(result["eligible_by_link_or_topic_rule"], 1)
        self.assertTrue(result["top40_source_id_set_matches_saved_sources"])
        self.assertTrue(result["top40_order_matches_saved_sources"])

    def test_last_author_key_matches_metadata_after_transliteration(self) -> None:
        self.write_json("runs/ez-source/sources.json", [{
            "doi": "10.5555/example",
            "authors": "First, A. and García, M.",
        }])
        note = self.root / "projects" / "project-a" / "notes" / "sources" / "garcia2020-example.md"
        note.parent.mkdir(parents=True)
        note.write_text("title: Example\nyear: 2020\ndoi: 10.5555/example\n", encoding="utf-8")

        result = last_author_notes_replay(self.root)

        self.assertEqual(result["source_note_count"], 1)
        self.assertEqual(result["notes_with_doi_matched_source_metadata"], 1)
        self.assertEqual(result["filename_keys_matching_last_author_any_recorded_variant"], 1)
        self.assertEqual(result["filename_keys_matching_first_author_any_recorded_variant"], 0)

    def test_followup_contract_count_is_not_qa_count_or_sufficiency(self) -> None:
        self.write_json("runs/ez-a/research-contract.json", {
            "question": {"original": "A neutral question"}, "plan": {"discovery_mode": "reuse_only"}})
        self.write_json("runs/ez-b/research-contract.json", {
            "question": {"original": "A search question"}, "plan": {"discovery_mode": "search"}})
        result = contract_replay(self.root)
        self.assertEqual(result["reuse_only_contracts_with_question"], 1)
        self.assertEqual(result["qa_replay"]["qa_file_count"], 0)
        self.assertFalse(result["validity_and_sufficiency_manifest_found"])

    def test_utf8_comparison_retains_pdf_pages_and_source_metadata(self) -> None:
        self.write_json("runs/ez-a/answer.json", {"claims": [{"context": "Sólo adultos", "text": "Measured response"}]})
        self.write_json("runs/ez-a/sources.json", [{"source_id": "s1", "authors": [{"family": "Example"}]}])
        self.write_json("cache/pages/hash.json", {"sha256": "hash", "pages": ["Literal page α", "Page two"]})
        result = lossless_bytes_replay(self.root)
        self.assertTrue(result["parsed_content_equal"])
        self.assertEqual(result["pdf_page_count"], 2)
        self.assertEqual(result["source_manifest_count"], 1)
        self.assertGreater(result["saved_utf8_bytes"], 0)

    def test_replay_refuses_output_inside_evidence(self) -> None:
        with self.assertRaises(SystemExit):
            main(["--root", str(self.root), "--output", str(self.root / "result.json")])
        self.assertFalse((self.root / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
