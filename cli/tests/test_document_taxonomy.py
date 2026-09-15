import tempfile
import unittest
import sys
import contextlib
import io
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import document_taxonomy, indexing, paths, records


class DocumentTaxonomyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.taxonomy = self.root / "document-taxonomy.yaml"
        self.documents = self.root / "documents"
        self.patchers = [
            mock.patch.object(document_taxonomy, "TAXONOMY", self.taxonomy),
            mock.patch.object(paths, "DOCUMENT_OBJECTS", self.documents),
            # Taxonomy renames invalidate the search index; keep the real
            # derived index out of reach of the test run.
            mock.patch.object(indexing, "INDEX", self.root / "index.sqlite"),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def test_default_types_are_seeded_and_unique_prefix_resolves(self) -> None:
        document_taxonomy.ensure()

        self.assertTrue(self.taxonomy.is_file())
        self.assertEqual(document_taxonomy.resolve("pr"), "presentation")
        self.assertIn("contract", document_taxonomy.type_ids())

    def test_interactive_unknown_type_can_extend_taxonomy(self) -> None:
        output = io.StringIO()
        with (
            mock.patch("builtins.input", side_effect=["briefing", "y"]),
            contextlib.redirect_stdout(output),
        ):
            selected = document_taxonomy.prompt_type()

        self.assertEqual(selected, "briefing")
        self.assertEqual(document_taxonomy.resolve("brief"), "briefing")
        self.assertIn("Valid document types:", output.getvalue())
        self.assertIn("presentation", output.getvalue())
        self.assertNotIn("?", output.getvalue())

    def test_unknown_noninteractive_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            document_taxonomy.TaxonomyError,
            "ws documents types add briefing",
        ):
            document_taxonomy.accept_type("briefing")

    def test_rename_migrates_existing_document_classification(self) -> None:
        document_taxonomy.ensure()
        self.documents.mkdir()
        record = self.documents / "doc_example.yaml"
        records.atomic_write(
            record,
            {
                "schema_version": 1,
                "id": "doc_example",
                "type": "document",
                "title": "Slides",
                "classification": {"type": "presentation"},
            },
        )

        old_id, new_id, affected = document_taxonomy.rename_type(
            "presentation", "slide-deck"
        )

        self.assertEqual((old_id, new_id, affected), ("presentation", "slide-deck", 1))
        self.assertEqual(
            records.load_record(record)["classification"]["type"], "slide-deck"
        )
        self.assertIsNone(document_taxonomy.resolve("presentation"))
        self.assertIn("slide-deck", document_taxonomy.type_ids())

    def test_remove_refuses_used_type_and_removes_unused_type(self) -> None:
        document_taxonomy.ensure()
        document_taxonomy.add_type("briefing")
        self.documents.mkdir()
        records.atomic_write(
            self.documents / "doc_example.yaml",
            {
                "schema_version": 1,
                "id": "doc_example",
                "type": "document",
                "title": "Brief",
                "classification": {"type": "briefing"},
            },
        )

        with self.assertRaisesRegex(document_taxonomy.TaxonomyError, "used by 1"):
            document_taxonomy.remove_type("briefing")

        (self.documents / "doc_example.yaml").unlink()
        removed, affected = document_taxonomy.remove_type("briefing")
        self.assertEqual((removed, affected), ("briefing", 0))
        self.assertIsNone(document_taxonomy.resolve("briefing"))


if __name__ == "__main__":
    unittest.main()
