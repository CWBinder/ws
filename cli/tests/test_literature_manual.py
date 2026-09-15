import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.machinery
import importlib.util

from ws_lib import literature


def load_ws_module():
    path = Path(__file__).resolve().parents[1] / "ws"
    loader = importlib.machinery.SourceFileLoader("ws_cli_lit_manual", str(path))
    spec = importlib.util.spec_from_loader("ws_cli_lit_manual", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ws_cli = load_ws_module()


class ManualEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.items = self.root / "items"
        self.items.mkdir()
        self.patchers = [
            mock.patch.object(literature, "LITERATURE", self.root),
            mock.patch.object(literature, "LITERATURE_ITEMS", self.items),
            mock.patch.object(
                literature.paths, "FOLDER_ANATOMY", self.root / "no-anatomy.yaml"
            ),
            mock.patch.object(
                literature,
                "load_taxonomy",
                return_value={"fields": ["physics", "spin-qubits", "ai"]},
            ),
            # Non-interactive: no wizard, and unknown fields must hard-fail.
            mock.patch.object(literature.sys.stdin, "isatty", return_value=False),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.parser = ws_cli.build_parser()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def add(self, *parts) -> str:
        args = self.parser.parse_args(["add", "literature", *parts])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        return buffer.getvalue()

    BASE = (
        "--kind", "manual", "--entry-type", "article",
        "--title", "A Manual Article", "--author", "Ada Lovelace", "--year", "2020",
    )

    def test_article_carries_journal_volume_number_and_pages(self) -> None:
        # An @article without a journal is malformed BibTeX; the manual path
        # had no way to supply one.
        self.add(*self.BASE, "--key", "Manual2020", "--journal", "Journal of Testing",
                 "--volume", "3", "--number", "5", "--pages", "601--642")

        bibtex = (self.items / "Manual2020" / "citation.bib").read_text()

        self.assertIn("journal = {Journal of Testing},", bibtex)
        self.assertIn("volume = {3},", bibtex)
        self.assertIn("number = {5},", bibtex)
        self.assertIn("pages = {601--642},", bibtex)

    def test_inproceedings_uses_booktitle(self) -> None:
        self.add("--kind", "manual", "--entry-type", "inproceedings", "--key", "Conf2021",
                 "--title", "A Conference Paper", "--author", "Grace Hopper",
                 "--year", "2021", "--journal", "Proceedings of Testing")

        bibtex = (self.items / "Conf2021" / "citation.bib").read_text()

        self.assertIn("booktitle = {Proceedings of Testing},", bibtex)
        self.assertNotIn("journal =", bibtex)

    def test_unknown_field_fails_before_creating_the_item(self) -> None:
        # Validation used to run after the item was written, so the add both
        # errored and left a created-but-unclassified item behind.
        with self.assertRaises(SystemExit):
            self.add(*self.BASE, "--key", "Rejected2020", "--field", "nonsense-field")

        self.assertEqual(list(self.items.glob("*")), [])

    def test_known_field_still_classifies(self) -> None:
        self.add(*self.BASE, "--key", "Accepted2020", "--field", "physics")

        info = (self.items / "Accepted2020" / "info.yaml").read_text()

        self.assertIn("physics", info)


if __name__ == "__main__":
    unittest.main()
