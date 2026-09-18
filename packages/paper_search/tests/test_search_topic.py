import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import search_topic


class TestSearchTopic(unittest.TestCase):
    def base_record(self, **overrides):
        record = {
            "title": "Comparative proteome analysis of Mycobacterium smegmatis in response to ethambutol",
            "authors": "Wang X",
            "year": 2011,
            "doi": "",
            "pmid": "20686769",
            "pmcid": None,
            "abstract": "",
            "url": "https://example.org",
            "pdf_url": None,
            "tgz_url": None,
            "is_oa": False,
            "pdf_path": None,
            "pdf_status": None,
            "pdf_source": None,
            "oa_sources": [],
            "manual_reason": None,
            "source": "pubmed",
            "sources": ["pubmed"],
            "queries": ["query"],
            "paper_id": "20686769",
            "identifier_confidence": 100,
            "title_match_confidence": 100,
            "source_match_reason": "matched_target:PMID:20686769",
            "acquisition_policy": "oa_first",
            "fallback_after": [],
        }
        record.update(overrides)
        return record

    def test_availability_is_separate_from_priority(self):
        record = self.base_record(abstract="Abstract", pdf_status="manual_needed", pdf_path=None, is_oa=False)
        self.assertEqual(search_topic.availability_status(record), "paywalled_or_unresolved")
        self.assertEqual(search_topic.review_priority(record, []), "candidate")

    def test_download_plan_lists_paywalled_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            record = self.base_record(
                abstract="Abstract",
                pdf_status="candidate",
                pdf_path=None,
                is_oa=False,
                doi="10.1000/paywalled",
                sources=["openalex", "semantic"],
            )
            path = search_topic.write_download_plan("review-test", [record], [], Path(tmp))
            content = path.read_text(encoding="utf-8")
            self.assertIn("bibliographic_priority: `high_priority`", content)
            self.assertIn("availability: `candidate`", content)
            self.assertIn("10.1000/paywalled", content)

        targets = [
            {
                "target_id": "PMID:20686769",
                "title": "Comparative proteome analysis of Mycobacterium smegmatis in response to ethambutol",
                "doi": "",
                "pmid": "20686769",
                "pmcid": "",
                "required": True,
            }
        ]

        queries = search_topic.discovery_queries(["ethambutol proteomics Mycobacterium smegmatis"], targets)

        self.assertEqual(queries[0], "20686769")
        self.assertIn("ethambutol proteomics Mycobacterium smegmatis", queries)

    def test_target_priority_acquires_required_matches_first(self):
        targets = [{"target_id": "PMID:20686769", "title": "", "doi": "", "pmid": "20686769", "pmcid": "", "required": True}]
        matched = self.base_record()
        unrelated = self.base_record(title="Unrelated paper", pmid="999", source_match_reason="discovery_result")

        ordered = sorted([unrelated, matched], key=lambda item: search_topic.target_priority(item, targets))

        self.assertEqual(ordered[0]["pmid"], "20686769")

    def test_dedupe_prefers_richer_metadata_and_merges_sources(self):
        first = {
            "title": "A useful paper",
            "authors": "Smith J",
            "year": 2024,
            "doi": "10.1000/test",
            "pmid": "123",
            "pmcid": None,
            "abstract": "",
            "url": "https://example.org/a",
            "pdf_url": None,
            "tgz_url": None,
            "is_oa": False,
            "pdf_path": None,
            "pdf_status": None,
            "source": "pubmed",
            "sources": ["pubmed"],
            "queries": ["query a"],
            "paper_id": "123",
        }
        second = {
            "title": "A useful paper",
            "authors": "Smith J; Doe A",
            "year": 2024,
            "doi": "10.1000/test",
            "pmid": "123",
            "pmcid": "PMC123",
            "abstract": "Abstract here",
            "url": "https://example.org/b",
            "pdf_url": "https://example.org/paper.pdf",
            "tgz_url": None,
            "is_oa": True,
            "pdf_path": None,
            "pdf_status": None,
            "source": "europepmc",
            "sources": ["europepmc"],
            "queries": ["query b"],
            "paper_id": "PMID:123",
        }

        deduped = search_topic.dedupe_records([first, second])
        self.assertEqual(len(deduped), 1)
        merged = deduped[0]
        self.assertEqual(merged["pmcid"], "PMC123")
        self.assertEqual(merged["pdf_url"], "https://example.org/paper.pdf")
        self.assertEqual(merged["sources"], ["europepmc", "pubmed"])
        self.assertEqual(merged["queries"], ["query a", "query b"])

    def test_filename_for_record_uses_author_year_and_title(self):
        record = {
            "authors": "Garcia Bereguiain A; Doe B",
            "year": 2025,
            "title": "South America End TB roadmap and equity",
        }
        filename = search_topic.filename_for_record(record)
        self.assertEqual(filename, "garcia_2025_south_america_end_tb_roadmap_and_equity.pdf")

    def test_dedupe_keeps_alternative_urls_and_rejects_conflicting_identifiers(self):
        first = self.base_record(doi='https://doi.org/10.1234/example', pdf_url='https://repo.example/accepted.pdf')
        second = self.base_record(doi='10.1234/example', pdf_url='https://publisher.example/final.pdf')
        merged = search_topic.dedupe_records([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0]['pdf_urls']), {'https://repo.example/accepted.pdf', 'https://publisher.example/final.pdf'})
        conflicting = self.base_record(doi='10.1234/different')
        self.assertEqual(len(search_topic.dedupe_records([merged[0], conflicting])), 2)

    def test_download_for_record_marks_manual_needed_for_identified_closed_paper(self):
        record = {
            "title": "Paper",
            "authors": "Smith J",
            "year": 2024,
            "doi": "10.1000/test",
            "pmid": "123",
            "pmcid": None,
            "abstract": "",
            "url": "https://example.org",
            "pdf_url": None,
            "tgz_url": None,
            "is_oa": False,
            "pdf_path": None,
            "pdf_status": None,
            "source": "pubmed",
            "sources": ["pubmed"],
            "queries": ["query"],
            "paper_id": "123",
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            updated = search_topic.download_for_record(record, Path(tmp_dir), min_oa=True)
        self.assertEqual(updated["pdf_status"], "manual_needed")
        self.assertIsNone(updated["pdf_path"])
        self.assertIn("No open-access PDF", updated["manual_reason"])
        self.assertIsNone(updated["pdf_source"])

    def test_normalize_identifier_handles_doi_pmid_pmcid_and_title(self):
        self.assertEqual(search_topic.normalize_identifier("https://doi.org/10.1000/ABC."), "DOI:10.1000/abc")
        self.assertEqual(search_topic.normalize_identifier("PMID: 20686769"), "PMID:20686769")
        self.assertEqual(search_topic.normalize_identifier("PMC3962153"), "PMCID:PMC3962153")
        self.assertEqual(search_topic.normalize_identifier("Some useful title"), "TITLE:some useful title")

    def test_anna_fallback_runs_only_after_oa_failure_when_enabled(self):
        record = {
            "title": "Closed paper",
            "authors": "Smith J",
            "year": 2024,
            "doi": "10.1000/test",
            "pmid": "123",
            "pmcid": None,
            "abstract": "",
            "url": "https://example.org",
            "pdf_url": "https://example.org/paywalled.pdf",
            "tgz_url": None,
            "is_oa": True,
            "pdf_path": None,
            "pdf_status": None,
            "source": "pubmed",
            "sources": ["pubmed"],
            "queries": ["query"],
            "paper_id": "123",
            "oa_sources": [],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            anna_pdf = Path(tmp_dir) / "anna.pdf"
            anna_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 2048)
            with patch("search_topic.try_direct_pdf", return_value=(None, "failed")) as direct, \
                 patch("search_topic.try_anna_archive", return_value=(str(anna_pdf), "downloaded")) as anna:
                updated = search_topic.download_for_record(record, Path(tmp_dir), min_oa=True, allow_anna_fallback=True)

        direct.assert_called_once()
        anna.assert_called_once()
        self.assertEqual(updated["pdf_status"], "downloaded")
        self.assertEqual(updated["pdf_source"], "anna_archive")
        self.assertEqual(updated["acquisition_policy"], "non_oa_fallback")
        self.assertEqual(updated["fallback_after"], ["legacy_direct_or_pmc"])
        self.assertNotIn("unpaywall", updated["fallback_after"])

    def test_anna_fallback_not_called_when_disabled(self):
        record = {
            "title": "Closed paper",
            "authors": "Smith J",
            "year": 2024,
            "doi": "10.1000/test",
            "pmid": "123",
            "pmcid": None,
            "abstract": "",
            "url": "https://example.org",
            "pdf_url": None,
            "tgz_url": None,
            "is_oa": False,
            "pdf_path": None,
            "pdf_status": None,
            "source": "pubmed",
            "sources": ["pubmed"],
            "queries": ["query"],
            "paper_id": "123",
            "oa_sources": [],
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("search_topic.try_anna_archive") as anna:
                updated = search_topic.download_for_record(record, Path(tmp_dir), min_oa=True, allow_anna_fallback=False)
        anna.assert_not_called()
        self.assertEqual(updated["pdf_status"], "manual_needed")
        self.assertIsNone(updated["pdf_source"])

    def test_anna_timeout_marks_manual_needed(self):
        record = self.base_record(doi="10.1000/test")
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("search_topic.try_direct_pdf", return_value=(None, "failed")), \
                 patch("search_topic.download_anna_identifier_with_timeout", return_value=(None, "timeout")):
                updated = search_topic.download_for_record(record, Path(tmp_dir), min_oa=True, allow_anna_fallback=True)

        self.assertEqual(updated["pdf_status"], "manual_needed")
        self.assertIn("timeout", updated["manual_reason"])
        self.assertEqual(updated["fallback_after"], [a["provider"] for a in updated["acquisition_attempts"]])
        self.assertNotIn("core_openaire_semantic", updated["fallback_after"])

    def test_incremental_artifacts_survive_acquisition_exception(self):
        targets = [{"target_id": "PMID:20686769", "title": "", "doi": "", "pmid": "20686769", "pmcid": "", "required": True}]
        records = [self.base_record()]
        with tempfile.TemporaryDirectory() as tmp_dir:
            save_dir = Path(tmp_dir)
            with patch("search_topic.download_for_record", side_effect=RuntimeError("boom")):
                paths = search_topic.acquire_records_incrementally(
                    "slug",
                    ["query"],
                    records,
                    targets,
                    save_dir,
                    min_oa=True,
                    allow_anna_fallback=True,
                )
            rescue = json.loads(paths["rescue"].read_text(encoding="utf-8"))
            candidates = json.loads(paths["candidate"].read_text(encoding="utf-8"))

        self.assertEqual(rescue["sources"][0]["status"], "failed")
        self.assertEqual(rescue["sources"][0]["failure_reason"], "network")
        self.assertEqual(candidates["candidates"][0]["pdf_status"], "failed")

    def test_anna_pdf_validation_rejects_html_and_tiny_pdf(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            html = Path(tmp_dir) / "paper.pdf"
            html.write_bytes(b"<html>not a pdf</html>" + b"x" * 2048)
            tiny = Path(tmp_dir) / "tiny.pdf"
            tiny.write_bytes(b"%PDF tiny")
            ok = Path(tmp_dir) / "ok.pdf"
            corrupt = Path(tmp_dir) / "corrupt.pdf"
            corrupt.write_bytes(b"%PDF-1.4\n" + b"x" * 2048)
            from PyPDF2 import PdfWriter
            writer = PdfWriter(); writer.add_blank_page(width=72, height=72)
            with ok.open('wb') as stream:
                writer.write(stream)

            self.assertFalse(search_topic.valid_pdf_file(html))
            self.assertFalse(search_topic.valid_pdf_file(tiny))
            self.assertFalse(search_topic.valid_pdf_file(corrupt))
            self.assertTrue(search_topic.valid_pdf_file(ok))

    def test_source_rescue_marks_missing_must_have(self):
        records = []
        targets = [{"target_id": "PMID:20686769", "title": "", "doi": "", "pmid": "20686769", "pmcid": "", "required": True}]
        entries = search_topic.build_source_rescue(records, targets)
        with tempfile.TemporaryDirectory() as tmp_dir:
            missing_path = search_topic.write_missing_sources(entries, Path(tmp_dir))
            text = missing_path.read_text(encoding="utf-8")

        self.assertEqual(entries[0]["status"], "manual_needed")
        self.assertEqual(entries[0]["failure_reason"], "no_match")
        self.assertIn("PMID:20686769", text)
        self.assertIn("Manual rescue checklist", text)
        self.assertIn("download_url: `TBD: verify authoritative OA PDF URL`", text)
        self.assertIn("suggested_destination:", text)

    def test_enrich_records_uses_unpaywall_when_pmc_has_no_pdf(self):
        record = {
            "title": "Paper",
            "authors": "Smith J",
            "year": 2024,
            "doi": "10.1000/test",
            "pmid": None,
            "pmcid": None,
            "abstract": "",
            "url": "https://example.org",
            "pdf_url": None,
            "tgz_url": None,
            "is_oa": False,
            "pdf_path": None,
            "pdf_status": None,
            "source": "pubmed",
            "sources": ["pubmed"],
            "queries": ["query"],
            "paper_id": "123",
        }

        with patch("search_topic.fetch_oa_metadata", return_value={"pmcid": None, "pdf_url": None, "tgz_url": None, "is_oa": False}), \
             patch("search_topic.fetch_unpaywall_pdf_url", return_value="https://repo.example/paper.pdf"):
            updated = search_topic.enrich_records([record])[0]

        self.assertTrue(updated["is_oa"])
        self.assertEqual(updated["pdf_url"], "https://repo.example/paper.pdf")
        self.assertEqual(updated["oa_sources"], ["unpaywall"])

    def test_extract_pdf_from_tgz_validates_unambiguous_pdf(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            destination = Path(tmp_dir) / "result.pdf"

            def fake_download(_url, archive_path, expected=None):
                import tarfile

                inner_dir = Path(tmp_dir) / "inner"
                inner_dir.mkdir(exist_ok=True)
                pdf_path = inner_dir / "paper.pdf"
                from PyPDF2 import PdfWriter
                writer = PdfWriter(); writer.add_blank_page(width=72, height=72)
                with pdf_path.open('wb') as stream:
                    writer.write(stream)
                with tarfile.open(archive_path, "w:gz") as archive:
                    archive.add(pdf_path, arcname="nested/paper.pdf")
                return True

            with patch("search_topic.download_binary", side_effect=fake_download):
                ok = search_topic.extract_pdf_from_tgz("https://example.org/archive.tgz", destination)

            self.assertTrue(ok)
            self.assertTrue(destination.exists())
            self.assertTrue(destination.read_bytes().startswith(b"%PDF"))

    def test_candidate_download_urls_adds_pbmc_https_and_english_suffix(self):
        urls = search_topic.candidate_download_urls("http://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127")

        self.assertEqual(urls[0], "http://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127")
        self.assertIn("https://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127", urls)
        self.assertIn("http://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127-en", urls)
        self.assertIn("https://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127-en", urls)

    def test_try_direct_pdf_attempts_candidate_urls(self):
        record = self.base_record(
            doi="10.18097/pbmcr1509",
            pdf_url="http://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127",
        )
        record["is_oa"] = True

        attempts = []

        def fake_download(url, destination, expected=None):
            attempts.append(url)
            if url == "https://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127-en":
                destination.write_bytes(b"%PDF-1.6\n" + b"x" * 2048)
                return True
            return False

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("search_topic.download_binary", side_effect=fake_download):
                path, status = search_topic.try_direct_pdf(record, Path(tmp_dir))

        self.assertEqual(status, "downloaded")
        self.assertTrue(path)
        self.assertIn("https://pbmc.ibmc.msk.ru/pdf/PBMC-2025-71-2-127-en", attempts)

    def test_download_binary_rejects_html_when_pdf_expected(self):
        class FakeResponse:
            def __init__(self):
                self.headers = {"Content-Type": "text/html; charset=utf-8"}
                self._chunks = [b"<html><title>Preparing to download</title></html>"]
                self.closed = False

            def raise_for_status(self):
                return None

            def iter_content(self, _chunk_size):
                yield from self._chunks

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as tmp_dir:
            destination = Path(tmp_dir) / "result.pdf"
            response = FakeResponse()
            with patch("search_topic.requests.get", return_value=response):
                ok = search_topic.download_binary(
                    "https://example.org/fake.pdf",
                    destination,
                    expected="pdf",
                )

        self.assertFalse(ok)
        self.assertFalse(destination.exists())
        self.assertTrue(response.closed)


if __name__ == "__main__":
    unittest.main()
