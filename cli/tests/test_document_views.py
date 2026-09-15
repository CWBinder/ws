import tempfile
import unittest
from pathlib import Path
from unittest import mock


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import anatomy, catalog, paths, records, relations


class DocumentViewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / "documents"
        self.files = self.root / "files"
        self.items = self.root / "items"
        self.organisations = Path(self.tempdir.name) / "logistics" / "organisations"
        self.relations = Path(self.tempdir.name) / "relations"
        self.files.mkdir(parents=True)
        self.items.mkdir()
        self.patchers = [
            mock.patch.object(paths, "DOCUMENTS", self.root),
            mock.patch.object(paths, "DOCUMENT_FILES", self.files),
            mock.patch.object(paths, "DOCUMENT_OBJECTS", self.items),
            # No anatomy file: the engine's built-in defaults apply.
            mock.patch.object(
                paths, "FOLDER_ANATOMY", Path(self.tempdir.name) / "no-anatomy.yaml"
            ),
            mock.patch.dict(catalog.SPECS["organisation"], {"dir": self.organisations}),
            mock.patch.object(relations, "RELATIONS", self.relations),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def _document(self, classification=None) -> Path:
        source = self.files / "brief.pdf"
        source.write_bytes(b"pdf")
        records.atomic_write(
            self.items / "doc_example.yaml",
            {
                "schema_version": 1,
                "id": "doc_example",
                "type": "document",
                "title": "Brief",
                "status": "active",
                "path": "files/brief.pdf",
                "path_root": "documents",
                "classification": classification or {},
            },
        )
        return source

    def test_missing_facets_have_visible_fallback_views(self) -> None:
        source = self._document()

        result = anatomy.rebuild_documents()

        # One root fallback per declared ring: type, organisation, event,
        # project, year.
        self.assertEqual(result, {"documents": 1, "links": 5, "missing": 0})
        for link in (
            self.root / "by-type" / "unclassified" / "brief.pdf",
            self.root / "by-year" / "unclassified" / "brief.pdf",
            self.root / "by-organisation" / "unclassified" / "brief.pdf",
            self.root / "by-event" / "unclassified" / "brief.pdf",
            self.root / "by-project" / "unclassified" / "brief.pdf",
        ):
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), source.resolve())

    def test_classification_and_relationships_materialize_facets(self) -> None:
        source = self._document(
            {"type": "presentation", "date": "2026-07-30"}
        )
        self.organisations.mkdir(parents=True)
        self.relations.mkdir()
        records.atomic_write(
            self.organisations / "org_example-society.yaml",
            {
                "schema_version": 1,
                "id": "org_example-society",
                "type": "organisation",
                "title": "EXAMPLE",
                "status": "active",
            },
        )
        records.atomic_write(
            self.relations / "rel_example.yaml",
            {
                "schema_version": 1,
                "id": "rel_example",
                "subject": "doc_example",
                "object": "org_example-society",
                "relation": "related",
                "status": "active",
            },
        )

        anatomy.rebuild_documents()

        for link in (
            self.root / "by-type" / "presentation" / "brief.pdf",
            self.root / "by-year" / "2026" / "by-month" / "07-July" / "brief.pdf",
            self.root / "by-organisation" / "EXAMPLE" / "brief.pdf",
            # The set nests into itself: rings recur below each value.
            self.root / "by-type" / "presentation" / "by-organisation" / "EXAMPLE" / "brief.pdf",
            self.root / "by-organisation" / "EXAMPLE" / "by-year" / "2026" / "brief.pdf",
        ):
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), source.resolve())
        self.assertFalse((self.root / "by-type" / "unclassified").exists())


if __name__ == "__main__":
    unittest.main()
