import unittest

import search_topic


class TestSearchTopic(unittest.TestCase):
    def test_search_single_turns_papers_into_records(self):
        from unittest.mock import patch
        from paper_search_mcp.paper import Paper

        class Searcher:
            def search(self, query, max_results):
                return [Paper(paper_id="PMC123", title="A work", authors=["Ana B"], abstract="Text", doi="10.1/X",
                              published_date=None, pdf_url="", url="https://example.org", source="europepmc")][:max_results]

        with patch.dict(search_topic.SEARCHER_FACTORIES, {"europepmc": Searcher}):
            records = search_topic.search_single("europepmc", "query", 5)
        self.assertEqual([(r["title"], r["doi"], r["authors"], r["queries"]) for r in records],
                         [("A work", "10.1/X", "Ana B", ["query"])])

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

    def test_dedupe_keeps_alternative_urls_and_rejects_conflicting_identifiers(self):
        first = self.base_record(doi='https://doi.org/10.1234/example', pdf_url='https://repo.example/accepted.pdf')
        second = self.base_record(doi='10.1234/example', pdf_url='https://publisher.example/final.pdf')
        merged = search_topic.dedupe_records([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(set(merged[0]['pdf_urls']), {'https://repo.example/accepted.pdf', 'https://publisher.example/final.pdf'})
        conflicting = self.base_record(doi='10.1234/different')
        self.assertEqual(len(search_topic.dedupe_records([merged[0], conflicting])), 2)


if __name__ == "__main__":
    unittest.main()
