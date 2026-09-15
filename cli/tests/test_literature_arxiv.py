import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import literature, project


class LiteratureArxivTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.items = self.root / "items"
        self.patchers = [
            mock.patch.object(literature, "LITERATURE_ITEMS", self.items),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def test_search_arxiv_prints_readable_rows(self) -> None:
        args = argparse.Namespace(
            query=["spin", "qubit"],
            author="Loss",
            title=None,
            abstract=None,
            category="quant-ph",
            max_results=2,
            start=0,
            sort="relevance",
        )
        rows = [{
            "id": "2401.01234",
            "title": "Spin Qubits in Quantum Dots",
            "authors": "Loss, Daniel and DiVincenzo, David",
            "year": "2024",
            "primary_class": "quant-ph",
            "doi": "10.1234/example",
            "journal_ref": "",
            "summary": "A compact abstract about spin qubits.",
            "url": "https://arxiv.org/abs/2401.01234",
        }]

        with mock.patch.object(literature, "arxiv_api_search", return_value=rows) as search:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                literature.command_literature_search_arxiv(args)

        params = search.call_args.args[0]
        self.assertIn("all:spin", params["search_query"])
        self.assertIn("au:Loss", params["search_query"])
        self.assertIn("cat:quant-ph", params["search_query"])
        self.assertIn("1. 2401.01234 [quant-ph] 2024", out.getvalue())
        self.assertIn("Authors: Loss, Daniel and DiVincenzo, David", out.getvalue())
        self.assertIn("Abstract: A compact abstract about spin qubits.", out.getvalue())

    def test_parse_arxiv_entries_keeps_multiple_results_and_legacy_ids(self) -> None:
        feed = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v2</id>
    <title>Modern Paper</title>
    <summary>First summary.</summary>
    <published>2024-01-01T00:00:00Z</published>
    <author><name>Alice Smith</name></author>
    <arxiv:primary_category term="quant-ph" />
    <category term="quant-ph" />
    <arxiv:doi>10.1000/example</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/hep-th/9901001</id>
    <title>Legacy Paper</title>
    <summary>Second summary.</summary>
    <published>1999-01-01T00:00:00Z</published>
    <author><name>Bob Doe</name></author>
    <arxiv:primary_category term="hep-th" />
    <category term="hep-th" />
  </entry>
</feed>
"""

        rows = literature.parse_arxiv_entries(feed)

        self.assertEqual([row["id"] for row in rows], ["2401.01234v2", "hep-th/9901001"])
        self.assertEqual(rows[0]["doi"], "10.1000/example")
        self.assertEqual(rows[1]["primary_class"], "hep-th")

    def test_add_arxiv_prefers_published_bibtex_and_enriches_item(self) -> None:
        match = {
            "id": "2401.01234v2",
            "title": "AI for Quantum Chemistry",
            "authors": "Smith, Alice and Doe, Bob",
            "year": "2024",
            "primary_class": "quant-ph",
            "doi": "10.1000/journal.abc",
            "summary": "A paper about models for chemistry.",
            "url": "https://arxiv.org/abs/2401.01234v2",
        }
        published_bibtex = """@article{PublisherKey,
  title = {AI for Quantum Chemistry},
  author = {Smith, Alice and Doe, Bob},
  year = {2024},
  doi = {10.1000/journal.abc},
}
"""
        args = argparse.Namespace(
            arxiv_id="2401.01234",
            key="Smith2024AI",
            full=True,
            prefer_published=False,
            pdf=False,
            source=False,
            force=False,
            no_extract=False,
        )

        with (
            mock.patch.object(literature, "arxiv_api_query", return_value=match),
            mock.patch.object(literature, "fetch_bibtex_for_doi", return_value=published_bibtex),
            mock.patch.object(literature, "fetch_crossref_message", return_value={"subject": ["Quantum chemistry"]}),
            mock.patch.object(literature, "command_literature_download_pdf") as download_pdf,
            mock.patch.object(literature, "command_literature_download_source") as download_source,
        ):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                literature.command_literature_add_arxiv(args)

        item = self.items / "Smith2024AI"
        citation = (item / "citation.bib").read_text(encoding="utf-8")
        arxiv_citation = (item / "source" / "arxiv" / "citation.bib").read_text(encoding="utf-8")
        self.assertIn("@article{Smith2024AI", citation)
        self.assertIn("doi = {10.1000/journal.abc}", citation)
        self.assertIn("keywords = {Quantum chemistry}", citation)
        self.assertIn("@misc{Smith2024AIArxiv", arxiv_citation)
        self.assertIn("eprint = {2401.01234v2}", arxiv_citation)
        self.assertIn("doi = {10.48550/arXiv.2401.01234}", arxiv_citation)
        self.assertIn("published DOI: 10.1000/journal.abc (main citation)", out.getvalue())
        self.assertEqual(download_pdf.call_args.args[0].key, "Smith2024AI")
        self.assertEqual(download_source.call_args.args[0].key, "Smith2024AI")


class LiteratureAddDispatchTests(unittest.TestCase):
    def add_args(self, source: str, **overrides) -> argparse.Namespace:
        values = {
            "source_value": source,
            "kind": "auto",
            "title": None,
            "doi": None,
            "isbn": None,
            "arxiv": None,
            "entry_type": "article",
            "project": "someproject",
            "no_link": False,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_add_detects_doi_and_keeps_project_link(self) -> None:
        args = self.add_args("https://doi.org/10.1103/PhysRevA.57.120")
        with mock.patch.object(literature, "command_literature_add_doi") as target:
            literature.command_literature_add(args)
        target.assert_called_once_with(args)
        self.assertEqual(args.doi, "https://doi.org/10.1103/PhysRevA.57.120")
        self.assertEqual(args.project, "someproject")
        self.assertFalse(args.no_link)

    def test_add_detects_arxiv_id(self) -> None:
        args = self.add_args("arXiv:2112.08863v2")
        with mock.patch.object(literature, "command_literature_add_arxiv") as target:
            literature.command_literature_add(args)
        target.assert_called_once_with(args)
        self.assertEqual(args.arxiv_id, "arXiv:2112.08863v2")

    def test_add_detects_isbn(self) -> None:
        args = self.add_args("978-0-13-468599-1")
        with mock.patch.object(literature, "command_literature_add_isbn") as target:
            literature.command_literature_add(args)
        target.assert_called_once_with(args)

    def test_add_falls_back_to_manual_with_title(self) -> None:
        args = self.add_args("", title="Unpublished notes")
        with mock.patch.object(literature, "command_literature_add_manual") as target:
            literature.command_literature_add(args)
        target.assert_called_once_with(args)
        self.assertEqual(args.type, "article")

    def test_add_fails_without_identifiable_source(self) -> None:
        args = self.add_args("not an identifier")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            literature.command_literature_add(args)
        self.assertIn("could not identify source", err.getvalue())


if __name__ == "__main__":
    unittest.main()
