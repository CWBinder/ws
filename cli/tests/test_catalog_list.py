import contextlib
import importlib.machinery
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import catalog, records


def load_ws_module():
    path = Path(__file__).resolve().parents[1] / "ws"
    loader = importlib.machinery.SourceFileLoader("ws_cli", str(path))
    spec = importlib.util.spec_from_loader("ws_cli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ws_cli = load_ws_module()


# Every catalog-backed `list` reaches the same command_list. A populated store
# is the case that matters: an empty one takes the "none" fallback and hides
# whatever the row formatter does.
LISTINGS = {
    "person": (["list", "people"], "person_example", "Maria Schwarz"),
    "organisation": (["list", "organisations"], "org_example", "Example Company"),
    "event": (["list", "events"], "event_example", "Group Meeting"),
    "task": (["list", "tasks"], "task_example", "Draft the appendix"),
    "document": (["list", "documents"], "doc_example", "Brief"),
}


class CatalogListTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.parser = ws_cli.build_parser()
        self.stores = {}
        self.patchers = []
        for kind in LISTINGS:
            store = Path(self.tempdir.name) / kind
            store.mkdir(parents=True)
            self.stores[kind] = store
            self.patchers.append(mock.patch.dict(catalog.SPECS[kind], {"dir": store}))
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def _record(self, kind: str) -> str:
        _, object_id, name = LISTINGS[kind]
        key = catalog.key_slug(name)
        records.atomic_write(
            self.stores[kind] / f"{key}.yaml",
            {
                "schema_version": 1,
                "id": object_id,
                "key": key,
                "kind": kind,
                "name": name,
                "aliases": [],
            },
        )
        return name

    def _run(self, argv: list[str]) -> str:
        args = self.parser.parse_args(argv)
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            args.func(args)
        return stream.getvalue()

    def test_populated_store_lists_the_object_name(self) -> None:
        for kind, (argv, object_id, _) in LISTINGS.items():
            with self.subTest(kind=kind):
                name = self._record(kind)

                output = self._run(argv)

                self.assertIn(f"{kind}:{catalog.key_slug(name)}", output)
                self.assertIn(name, output)

    def test_populated_store_lists_as_json(self) -> None:
        for kind, (argv, object_id, _) in LISTINGS.items():
            with self.subTest(kind=kind):
                name = self._record(kind)

                rows = json.loads(self._run(argv + ["--json"]))

                self.assertEqual(
                    rows, [{"ref": f"{kind}:{catalog.key_slug(name)}", "kind": kind, "name": name, "status": ""}]
                )

    def test_empty_store_reports_none(self) -> None:
        for kind, (argv, _, _) in LISTINGS.items():
            with self.subTest(kind=kind):
                self.assertEqual(self._run(argv).strip(), "none")


if __name__ == "__main__":
    unittest.main()
