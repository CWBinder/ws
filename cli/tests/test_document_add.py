import contextlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import catalog, document_taxonomy, indexing, paths


def load_ws_module():
    path = Path(__file__).resolve().parents[1] / "ws"
    loader = importlib.machinery.SourceFileLoader("ws_cli_documents", str(path))
    spec = importlib.util.spec_from_loader("ws_cli_documents", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ws_cli = load_ws_module()


class DocumentAddTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.inbox = root / "inbox"
        self.documents = root / "documents"
        self.files = self.documents / "files"
        self.items = self.documents / "items"
        for directory in (self.inbox, self.files, self.items):
            directory.mkdir(parents=True)
        specs = {
            type_name: {
                **spec,
                "dir": self.items if type_name == "document" else root / "data" / spec["plural"],
            }
            for type_name, spec in catalog.SPECS.items()
        }
        self.patchers = [
            mock.patch.object(catalog, "SPECS", specs),
            mock.patch.object(paths, "DOCUMENTS", self.documents),
            mock.patch.object(paths, "DOCUMENT_FILES", self.files),
            mock.patch.object(paths, "DOCUMENT_OBJECTS", self.items),
            # No anatomy file: the engine's built-in defaults apply.
            mock.patch.object(paths, "FOLDER_ANATOMY", root / "no-anatomy.yaml"),
            mock.patch.object(paths, "ORGANISATIONS", root / "logistics" / "organisations"),
            mock.patch.object(paths, "RELATIONS", root / "relations"),
            mock.patch.object(
                document_taxonomy, "TAXONOMY", self.documents / "document-taxonomy.yaml"
            ),
            mock.patch.object(indexing, "INDEX", root / "index.sqlite"),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.parser = ws_cli.build_parser()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def add(self, *parts) -> dict:
        args = self.parser.parse_args(
            ["add", "document", *parts, "--non-interactive", "--json"]
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        return json.loads(buffer.getvalue())

    def test_add_moves_the_file_and_stores_no_digest(self) -> None:
        source = self.inbox / "report.pdf"
        source.write_bytes(b"quarterly report")
        result = self.add(str(source))
        self.assertTrue(result["created"])
        key = result["ref"].partition(":")[2]
        record = catalog.records.load_record(self.items / f"{key}.yaml")
        self.assertNotIn("content_sha256", record)
        self.assertFalse(source.exists())
        self.assertTrue((self.files / "report.pdf").exists())

    def test_ensure_matches_a_reference_add_by_path(self) -> None:
        source = self.inbox / "report.pdf"
        source.write_bytes(b"quarterly report")
        first = self.add(str(source), "--mode", "reference")
        second = self.add(str(source), "--mode", "reference", "--ensure")
        self.assertFalse(second["created"])
        self.assertEqual(second["ref"], first["ref"])
        self.assertTrue(source.exists())
        self.assertEqual(len(list(self.items.glob("*.yaml"))), 1)

    def test_ensure_matches_a_copy_add_by_source_path(self) -> None:
        # The case --ensure exists for: re-running against the ORIGINAL source
        # after the file already sits in files/. The destination guard has to
        # defer here instead of failing before the ensure lookup runs.
        source = self.inbox / "report.pdf"
        source.write_bytes(b"quarterly report")
        first = self.add(str(source), "--mode", "copy")
        second = self.add(str(source), "--mode", "copy", "--ensure")
        self.assertFalse(second["created"])
        self.assertEqual(second["ref"], first["ref"])
        self.assertTrue(source.exists())
        self.assertEqual(len(list(self.items.glob("*.yaml"))), 1)

    def test_ensure_still_refuses_a_different_file_of_the_same_name(self) -> None:
        source = self.inbox / "report.pdf"
        source.write_bytes(b"quarterly report")
        self.add(str(source), "--mode", "copy")
        nested = self.inbox / "nested"
        nested.mkdir()
        clash = nested / "report.pdf"
        clash.write_bytes(b"an entirely different report")
        with self.assertRaises(SystemExit):
            self.add(str(clash), "--mode", "copy", "--ensure")
        self.assertEqual(len(list(self.items.glob("*.yaml"))), 1)
        self.assertEqual((self.files / "report.pdf").read_bytes(), b"quarterly report")

    def test_ensure_still_creates_for_new_content(self) -> None:
        source = self.inbox / "minutes.pdf"
        source.write_bytes(b"different bytes")
        result = self.add(str(source), "--ensure")
        self.assertTrue(result["created"])
        self.assertFalse(source.exists())


if __name__ == "__main__":
    unittest.main()
