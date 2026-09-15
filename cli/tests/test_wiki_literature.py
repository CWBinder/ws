"""Wiki rendering for literature metadata and derived profile selection."""

import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import literature, wiki


class WikiLiteratureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.items = self.root / "literature" / "items"
        self.knowledgebase = self.root / "literature" / "knowledgebase"
        self.generated = self.knowledgebase / "generated"
        self.patchers = [
            mock.patch.object(literature, "LITERATURE_ITEMS", self.items),
            mock.patch.object(wiki, "WORKSPACE", self.root),
            mock.patch.object(wiki, "KNOWLEDGEBASE", self.knowledgebase),
            mock.patch.object(wiki, "GENERATED", self.generated),
            mock.patch.object(wiki.project, "PROJECTS", self.root / "projects"),
            mock.patch.object(wiki.project, "existing_project_names", return_value=[]),
            mock.patch.object(wiki.project, "load_taxonomy", return_value={"fields": []}),
            mock.patch.object(wiki.career, "load_profile", return_value={}),
            mock.patch.object(wiki.career, "CAREER", self.root / "career"),
            mock.patch.object(wiki.career, "ITEMS", self.root / "career" / "items"),
            mock.patch.object(wiki.career, "TAXONOMY", self.root / "career" / "profile-taxonomy.yaml"),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def write_item(self) -> None:
        item = self.items / "Smith2024AI"
        item.mkdir(parents=True)
        (item / "citation.bib").write_text(
            """@article{Smith2024AI,
  title = {AI for Quantum Chemistry},
  author = {Smith, Alice},
  year = {2024},
  doi = {10.1000/journal.abc},
}
""",
            encoding="utf-8",
        )
        (item / "info.yaml").write_text(
            "schema_version: 1\nkeywords: []\nfields: [ai, quantum-chemistry]\n",
            encoding="utf-8",
        )

    def test_wiki_indexes_authors_year_and_fields_without_collections(self) -> None:
        self.write_item()

        with contextlib.redirect_stdout(io.StringIO()):
            wiki.command_wiki(argparse.Namespace())

        literature_index = (self.generated / "Literature.md").read_text(encoding="utf-8")
        literature_page = (self.generated / "literature" / "literature-Smith2024AI.md").read_text(encoding="utf-8")

        self.assertIn("[[literature-Smith2024AI|AI for Quantum Chemistry]]", literature_index)
        self.assertIn("Alice Smith", literature_index)
        self.assertIn("2024", literature_index)
        self.assertIn("ai, quantum-chemistry", literature_index)
        self.assertIn("Smith, Alice", literature_page)
        self.assertFalse((self.generated / "Collections.md").exists())


if __name__ == "__main__":
    unittest.main()
