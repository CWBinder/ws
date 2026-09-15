import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import literature


class LiteratureCitationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.items = self.root / "items"
        self.items.mkdir()
        self.patchers = [
            mock.patch.object(literature, "LITERATURE_ITEMS", self.items),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def make_item(self, key: str, bibtex: str, references: str = "") -> Path:
        root = self.items / key
        root.mkdir()
        (root / "citation.bib").write_text(bibtex, encoding="utf-8")
        if references:
            (root / "references.txt").write_text(references, encoding="utf-8")
        return root

    def run_command(self, func, **kwargs) -> tuple[str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            func(argparse.Namespace(**kwargs))
        return out.getvalue(), err.getvalue()

    def test_parse_identifier_normalizes_common_forms(self) -> None:
        cases = {
            "https://doi.org/10.1103/PhysRevA.57.120.": "doi:10.1103/physreva.57.120",
            "doi:10.1000/ABC-def": "doi:10.1000/abc-def",
            "10.1000/plain": "doi:10.1000/plain",
            "arXiv:2301.01234v2": "arxiv:2301.01234",
            "2301.01234": "arxiv:2301.01234",
            "https://arxiv.org/abs/quant-ph/9705052v1": "arxiv:quant-ph/9705052",
            "10.48550/arXiv.2301.01234": "arxiv:2301.01234",
            "isbn: 978-0-13-468599-1": "isbn:9780134685991",
            "not an identifier": "",
            "": "",
        }
        for raw, expected in cases.items():
            self.assertEqual(literature.parse_identifier(raw), expected, raw)

    def test_identifier_aliases_bridge_arxiv_and_doi_forms(self) -> None:
        self.assertIn(
            "doi:10.48550/arxiv.2301.01234",
            literature.identifier_aliases("arxiv:2301.01234"),
        )
        self.assertIn(
            "arxiv:2301.01234",
            literature.identifier_aliases("doi:10.48550/arxiv.2301.01234"),
        )

    def test_citations_prints_deduplicated_reference_list(self) -> None:
        self.make_item(
            "smith2020spin",
            "@article{smith2020spin,\n  doi = {10.1000/smith},\n}\n",
            references="\n".join(
                [
                    "# header comment",
                    "doi:10.1000/one  # First cited paper",
                    "https://doi.org/10.1000/one",
                    "arXiv:2301.01234v2",
                    "garbage line",
                    "",
                ]
            ),
        )
        out, _ = self.run_command(
            literature.command_literature_citations,
            key="smith2020spin",
            in_library=False,
            fetch=False,
        )
        self.assertEqual(
            out.splitlines(),
            ["doi:10.1000/one  # First cited paper", "arxiv:2301.01234"],
        )

    def test_citations_in_library_matches_doi_and_arxiv_aliases(self) -> None:
        self.make_item(
            "citing2024",
            "@article{citing2024,\n  doi = {10.1000/citing},\n}\n",
            references="\n".join(
                [
                    "doi:10.1000/held-paper",
                    "10.48550/arXiv.2301.01234",
                    "doi:10.1000/not-in-library",
                ]
            ),
        )
        self.make_item(
            "held2020",
            "@article{held2020,\n  doi = {10.1000/held-paper},\n}\n",
        )
        self.make_item(
            "eprint2023",
            "@article{eprint2023,\n  eprint = {2301.01234},\n  archivePrefix = {arXiv},\n}\n",
        )
        out, _ = self.run_command(
            literature.command_literature_citations,
            key="citing2024",
            in_library=True,
            fetch=False,
        )
        self.assertEqual(
            out.splitlines(),
            [
                "literature:held2020  (doi:10.1000/held-paper)",
                "literature:eprint2023  (arxiv:2301.01234)",
            ],
        )

    def test_citations_in_library_reports_no_matches_on_stderr(self) -> None:
        self.make_item(
            "alone2024",
            "@article{alone2024,\n  doi = {10.1000/alone},\n}\n",
            references="doi:10.1000/unknown\n",
        )
        out, err = self.run_command(
            literature.command_literature_citations,
            key="alone2024",
            in_library=True,
            fetch=False,
        )
        self.assertEqual(out, "")
        self.assertIn("no cited works are in the library", err)

    def test_citations_missing_references_fails_with_fetch_hint(self) -> None:
        self.make_item(
            "bare2024",
            "@article{bare2024,\n  doi = {10.1000/bare},\n}\n",
        )
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            literature.command_literature_citations(
                argparse.Namespace(key="bare2024", in_library=False, fetch=False)
            )
        self.assertIn("--fetch", err.getvalue())

    def test_cited_by_scans_other_items_references(self) -> None:
        self.make_item(
            "target2020",
            "@article{target2020,\n  eprint = {2301.01234},\n  archivePrefix = {arXiv},\n}\n",
        )
        self.make_item(
            "citer2024",
            "@article{citer2024,\n  doi = {10.1000/citer},\n}\n",
            references="10.48550/arXiv.2301.01234\n",
        )
        self.make_item(
            "bystander2024",
            "@article{bystander2024,\n  doi = {10.1000/bystander},\n}\n",
            references="doi:10.1000/unrelated\n",
        )
        out, _ = self.run_command(
            literature.command_literature_cited_by, key="target2020"
        )
        self.assertEqual(out.splitlines(), ["literature:citer2024"])

    def test_cited_by_reports_no_citing_items_on_stderr(self) -> None:
        self.make_item(
            "quiet2020",
            "@article{quiet2020,\n  doi = {10.1000/quiet},\n}\n",
        )
        out, err = self.run_command(
            literature.command_literature_cited_by, key="quiet2020"
        )
        self.assertEqual(out, "")
        self.assertIn("no library item cites this one", err)

    def test_fetch_writes_references_file(self) -> None:
        root = self.make_item(
            "fetched2023",
            "@article{fetched2023,\n  eprint = {2401.05678},\n  archivePrefix = {arXiv},\n}\n",
        )
        payload = {
            "data": [
                {
                    "citedPaper": {
                        "externalIds": {"DOI": "10.1000/Cited-One"},
                        "title": "Cited  One",
                    }
                },
                {
                    "citedPaper": {
                        "externalIds": {"ArXiv": "2301.01234v3"},
                        "title": "Cited Two",
                    }
                },
                {"citedPaper": {"externalIds": {}, "title": "No identifier"}},
            ]
        }
        with mock.patch.object(
            literature, "http_get_text", return_value=json.dumps(payload)
        ) as fetched:
            out, _ = self.run_command(
                literature.command_literature_citations,
                key="fetched2023",
                in_library=False,
                fetch=True,
            )
        self.assertIn("arXiv:2401.05678", fetched.call_args[0][0])
        content = (root / "references.txt").read_text(encoding="utf-8")
        self.assertIn("doi:10.1000/cited-one  # Cited One", content)
        self.assertIn("arxiv:2301.01234  # Cited Two", content)
        self.assertIn("1 cited works without one", content)
        self.assertIn("wrote", out)
        self.assertIn("2 identifiers", out)
        self.assertEqual(
            [line for line in out.splitlines() if line.startswith(("doi:", "arxiv:"))],
            ["doi:10.1000/cited-one  # Cited One", "arxiv:2301.01234  # Cited Two"],
        )

    def test_fetch_falls_back_to_openalex_when_semantic_scholar_is_empty(self) -> None:
        root = self.make_item(
            "fallback2023",
            "@article{fallback2023,\n  doi = {10.1000/fallback},\n}\n",
        )
        responses = [
            {"data": []},
            {
                "referenced_works": [
                    "https://openalex.org/W1",
                    "https://openalex.org/W2",
                    "https://openalex.org/W3",
                ]
            },
            {
                "results": [
                    {
                        "id": "https://openalex.org/W1",
                        "doi": "https://doi.org/10.1000/OPENALEX-ONE",
                        "display_name": "OpenAlex One",
                        "locations": [],
                    },
                    {
                        "id": "https://openalex.org/W2",
                        "doi": None,
                        "display_name": "OpenAlex Preprint",
                        "locations": [
                            {"landing_page_url": "https://arxiv.org/abs/2301.01234v2"}
                        ],
                    },
                    {
                        "id": "https://openalex.org/W3",
                        "doi": None,
                        "display_name": "No stable identifier",
                        "locations": [],
                    },
                ]
            },
        ]
        with mock.patch.object(
            literature,
            "http_get_text",
            side_effect=[json.dumps(value) for value in responses],
        ) as fetched:
            out, _ = self.run_command(
                literature.command_literature_citations,
                key="fallback2023",
                in_library=False,
                fetch=True,
            )
        self.assertEqual(fetched.call_count, 3)
        self.assertIn("api.openalex.org/works/doi:10.1000%2Ffallback", fetched.call_args_list[1][0][0])
        content = (root / "references.txt").read_text(encoding="utf-8")
        self.assertIn("from OpenAlex", content)
        self.assertIn("doi:10.1000/openalex-one  # OpenAlex One", content)
        self.assertIn("arxiv:2301.01234  # OpenAlex Preprint", content)
        self.assertIn("1 cited works without one", content)
        self.assertIn("source: OpenAlex", out)

    def test_empty_fetch_does_not_overwrite_existing_references(self) -> None:
        root = self.make_item(
            "preserved2023",
            "@article{preserved2023,\n  doi = {10.1000/preserved},\n}\n",
            references="doi:10.1000/keep  # Keep me\n",
        )
        original = (root / "references.txt").read_text(encoding="utf-8")
        with mock.patch.object(
            literature,
            "http_get_text",
            side_effect=[
                json.dumps({"data": []}),
                json.dumps({"referenced_works": []}),
            ],
        ), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            literature.command_literature_citations(
                argparse.Namespace(
                    key="preserved2023",
                    in_library=False,
                    fetch=True,
                )
            )
        self.assertEqual(
            (root / "references.txt").read_text(encoding="utf-8"),
            original,
        )


if __name__ == "__main__":
    unittest.main()
