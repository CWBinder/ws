import datetime as dt
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import catalog, dashboard, indexing, literature, records, relations


class DashboardTests(unittest.TestCase):
    """`ws rebuild dashboard` renders one derived page from the records alone."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        specs = {
            name: {**spec, "dir": self.root / "data" / spec["plural"]}
            for name, spec in catalog.SPECS.items()
        }
        self.patchers = [
            mock.patch.object(catalog, "SPECS", specs),
            mock.patch.object(catalog.project, "existing_project_names", return_value=[]),
            mock.patch.object(literature, "LITERATURE_ITEMS", self.root / "literature" / "items"),
            mock.patch.object(relations, "RELATIONS", self.root / "relations"),
            mock.patch.object(indexing, "INDEX", self.root / "index.sqlite"),
            mock.patch.object(dashboard, "DASHBOARD", self.root / "dashboard.html"),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.person = self.record("person", "maria-schwarz", "Maria </script> Schwarz")
        self.org = self.record("organisation", "exampleco", "ExampleCo")
        self.record("task", "send-report", "Send the report", due="2026-01-02", priority="high")
        self.record("task", "old-task", "Old task", status="done", due="2025-01-01")
        self.record("task", "someday", "Someday task")
        self.record("event", "workshop", "Workshop", start="2099-05-04")
        relations.create(self.person.id, self.org.id, "works-at")

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def record(self, kind: str, key: str, name: str, **fields):
        store = Path(catalog.SPECS[kind]["dir"])
        store.mkdir(parents=True, exist_ok=True)
        records.atomic_write(store / f"{key}.yaml", {
            "schema_version": 1, "id": f"{catalog.SPECS[kind]['prefix']}_{key}", "key": key,
            "kind": kind, "name": name, "aliases": [], "created_at": "2026-09-01T10:00:00+02:00", **fields,
        })
        return next(ref for ref in catalog.all_objects() if ref.ref == f"{kind}:{key}")

    def payload(self) -> dict:
        html = (self.root / "dashboard.html").read_text(encoding="utf-8")
        raw = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1)
        return json.loads(raw)

    def test_build_writes_the_page_with_every_object_and_relation(self) -> None:
        result = dashboard.build()
        self.assertEqual(result["objects"], 6)
        self.assertEqual(result["relations"], 1)
        data = self.payload()
        self.assertEqual({n["ref"] for n in data["nodes"]} >= {"person:maria-schwarz", "organisation:exampleco"}, True)
        self.assertEqual(data["links"][0]["w"], "works-at")
        self.assertEqual(data["vocab"], [{"w": "works-at", "n": 1, "pairs": [["person → organisation", 1]]}])

    def test_names_cannot_end_the_data_script_early(self) -> None:
        dashboard.build()
        html = (self.root / "dashboard.html").read_text(encoding="utf-8")
        # One closing tag for the data block, one for the program: the name's
        # `</script>` is escaped inside the JSON.
        self.assertEqual(html.count("</script>"), 2)
        names = [n["name"] for n in self.payload()["nodes"]]
        self.assertIn("Maria </script> Schwarz", names)

    def test_only_open_tasks_are_listed_and_dated_ones_keep_their_date(self) -> None:
        dashboard.build()
        data = self.payload()
        tasks = {data["nodes"][t["i"]]["ref"]: t for t in data["tasks"]}
        self.assertEqual(set(tasks), {"task:send-report", "task:someday"})
        self.assertEqual(tasks["task:send-report"]["due"], "2026-01-02")
        self.assertEqual(tasks["task:send-report"]["priority"], "high")
        self.assertEqual(tasks["task:someday"]["due"], "")
        self.assertEqual([data["nodes"][e["i"]]["ref"] for e in data["events"]], ["event:workshop"])

    def test_unconnected_objects_are_counted(self) -> None:
        result = dashboard.build()
        self.assertEqual(result["objects"] - result["connected"], 4)

    def test_the_page_is_self_contained(self) -> None:
        dashboard.build()
        html = (self.root / "dashboard.html").read_text(encoding="utf-8")
        self.assertNotRegex(html, r"<(script|link)[^>]+(src|href)=\"https?://")
        self.assertNotIn("__DATA__", html)

    def test_building_changes_no_record(self) -> None:
        before = sorted(p.read_bytes() for p in (self.root / "data").rglob("*.yaml"))
        dashboard.build()
        after = sorted(p.read_bytes() for p in (self.root / "data").rglob("*.yaml"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
