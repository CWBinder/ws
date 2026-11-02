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

                expected = {"ref": f"{kind}:{catalog.key_slug(name)}", "kind": kind, "name": name, "status": ""}
                if kind == "task":
                    expected["due"] = ""
                self.assertEqual(rows, [expected])

    def test_empty_store_reports_none(self) -> None:
        for kind, (argv, _, _) in LISTINGS.items():
            with self.subTest(kind=kind):
                self.assertEqual(self._run(argv).strip(), "none")

    def _task(self, name: str, **fields) -> str:
        key = catalog.key_slug(name)
        records.atomic_write(
            self.stores["task"] / f"{key}.yaml",
            {"schema_version": 1, "id": f"task_{key}", "key": key, "kind": "task",
             "name": name, "aliases": [], **fields},
        )
        return f"task:{key}"

    def _task_refs(self, argv: list[str]) -> set[str]:
        return {row["ref"] for row in json.loads(self._run(["list", "tasks", *argv, "--json"]))}

    def test_open_tasks_leave_out_closed_ones(self) -> None:
        pay = self._task("Pay the formal", status="open", due="2026-10-25")
        later = self._task("Look into GESDA")
        waiting = self._task("Hear back from Zhu", status="waiting")
        self._task("Book the train", status="done")
        self._task("Old plan", status="Dropped")

        self.assertEqual(self._task_refs(["--open"]), {pay, later, waiting})

    def test_status_matches_one_word_and_open_includes_unset(self) -> None:
        pay = self._task("Pay the formal", status="open")
        later = self._task("Look into GESDA")
        done = self._task("Book the train", status="Done")

        self.assertEqual(self._task_refs(["--status", "done"]), {done})
        self.assertEqual(self._task_refs(["--status", "open"]), {pay, later})
        self.assertEqual(self._task_refs(["--status", "waiting"]), set())

    def test_task_rows_carry_the_due_date(self) -> None:
        pay = self._task("Pay the formal", status="open", due="2026-10-25")

        self.assertEqual(self._run(["list", "tasks", "--open"]).strip(), f"{pay}\tPay the formal\topen\t2026-10-25")
        self.assertEqual(json.loads(self._run(["list", "tasks", "--json"]))[0]["due"], "2026-10-25")


if __name__ == "__main__":
    unittest.main()
