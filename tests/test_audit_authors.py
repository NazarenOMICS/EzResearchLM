"""Author metadata must retain structure from provider through EZ exports."""
from datetime import datetime
import json
import unittest
from xml.etree import ElementTree

from ez.deliver import citation_key, export_bibliography
from ez.presenter import author_list, short_citation, surname
from ez.vault import note_header
from paper_search_mcp.academic_platforms.crossref import CrossRefSearcher
from paper_search_mcp.academic_platforms.europepmc import EuropePMCSearcher
from paper_search_mcp.academic_platforms.pubmed import PubMedSearcher
from paper_search_mcp.paper import Paper
from search_topic import record_from_paper


class AuthorAuditTests(unittest.TestCase):
    def test_crossref_preserves_given_family_and_corporate_name(self):
        authors = CrossRefSearcher()._extract_authors({"author": [
            {"given": "Ana M.", "family": "de la Cruz"},
            {"name": "Council, Research Division"},
        ]})
        self.assertEqual(authors, [
            {"given": "Ana M.", "family": "de la Cruz"},
            {"literal": "Council, Research Division"},
        ])

    def test_europepmc_preserves_structured_and_literal_authors(self):
        paper = EuropePMCSearcher()._parse_item({
            "id": "123", "source": "MED", "title": "A title",
            "authorList": {"author": [
                {"firstName": "Ana M.", "lastName": "de la Cruz", "fullName": "Ana M. de la Cruz"},
                {"fullName": "Council, Research Division"},
            ]},
        })
        self.assertEqual(paper.authors, [
            {"given": "Ana M.", "family": "de la Cruz"},
            {"literal": "Council, Research Division"},
        ])

    def test_pubmed_keeps_fore_name_family_and_collective_name(self):
        root = ElementTree.fromstring("""<PubmedArticleSet><PubmedArticle>
          <MedlineCitation><PMID>123</PMID><Article><ArticleTitle>A title</ArticleTitle>
            <AuthorList><Author><LastName>de la Cruz</LastName><ForeName>Ana Maria</ForeName><Initials>AM</Initials></Author>
              <Author><CollectiveName>Council, Research Division</CollectiveName></Author></AuthorList>
            <Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal>
          </Article></MedlineCitation></PubmedArticle></PubmedArticleSet>""")
        searcher = PubMedSearcher()
        searcher._request_xml = lambda *args: ElementTree.fromstring("<eSearchResult><Id>123</Id></eSearchResult>") if "esearch" in args[0] else root
        paper = searcher.search("query", 1)[0]
        self.assertEqual(paper.authors, [
            {"given": "Ana Maria", "family": "de la Cruz"},
            {"literal": "Council, Research Division"},
        ])

    def test_paper_and_search_record_serialize_author_objects(self):
        paper = Paper(paper_id="1", title="Title", authors=[{"given": "Ana", "family": "de la Cruz"}],
                      abstract="", doi="", published_date=datetime(2020, 1, 1), pdf_url="", url="", source="crossref")
        self.assertEqual(paper.to_dict()["authors"], [{"given": "Ana", "family": "de la Cruz"}])
        self.assertEqual(record_from_paper(paper, "query", "crossref")["authors"],
                         [{"given": "Ana", "family": "de la Cruz"}])
        self.assertIn('"authors": [{"given": "Ana", "family": "de la Cruz"}]',
                      json.dumps(record_from_paper(paper, "query", "crossref")))

    def test_presenter_and_exports_accept_structured_and_legacy_authors(self):
        source = {"title": "A title", "authors": [
            {"given": "Ana M.", "family": "de la Cruz"},
        ], "year": 2020}
        self.assertEqual(author_list(source), ["Ana M. de la Cruz"])
        self.assertEqual(short_citation(source), "de la Cruz, 2020")
        self.assertEqual(citation_key(source, set()), "delacruz2020")
        corporate = {**source, "authors": source["authors"] + [{"literal": "Council, Research Division"}]}
        bib = export_bibliography([corporate])
        self.assertIn("author = {Ana M. de la Cruz and {Council, Research Division}}", bib)
        ris = export_bibliography([corporate], "ris")
        self.assertIn("AU  - Ana M. de la Cruz", ris)
        self.assertIn("AU  - Council, Research Division", ris)
        note = "\n".join(note_header({**corporate, "source_id": "s1"}))
        self.assertIn('  - "Ana M. de la Cruz"', note)
        self.assertIn('  - "Council, Research Division"', note)
        self.assertEqual(short_citation({"authors": ["Example X", "Sample I", "Demo JH."], "year": 2008}),
                         "Example et al., 2008")
        self.assertEqual(author_list({"authors": "Ana Garcia and Jun Kim"}), ["Ana Garcia and Jun Kim"])
        self.assertEqual(author_list({"authors": "Example E and Sample KC"}), ["Example E", "Sample KC"])
        self.assertEqual(author_list({"authors": "Research and Development Council"}),
                         ["Research and Development Council"])
        self.assertEqual(short_citation({"authors": ["Lopez, Ana M."], "year": 2008}), "Lopez, 2008")
        self.assertEqual(short_citation({"authors": ["de la Cruz ABCD"], "year": 2021}), "de la Cruz, 2021")

    def test_corporate_and_inverted_names_keep_their_form(self):
        self.assertEqual(surname("Research Council"), "Research Council")
        self.assertEqual(surname("Council, Research Division"), "Council, Research Division")
        self.assertEqual(surname("Ana M. Lopez"), "Lopez")  # display name: last word (test_audit_followup)
        self.assertEqual(surname("van der Berg JH"), "van der Berg")
        self.assertEqual(surname("Lopez, Ana M."), "Lopez")
        self.assertEqual(surname({"given": "Ana"}), "")


if __name__ == "__main__":
    unittest.main()
