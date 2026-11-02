"""`ws rebuild [TARGET]` regenerates every derived layer through one handler."""

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import anatomy, cli, dashboard, indexing, rebuild, registry, wiki


VIEW_COUNTS = {
    "projects": {"by-type": 3, "by-status": 2},
    "documents": {"documents": 4, "links": 9, "missing": 1},
    "literature": {"by-author": 5},
    "profile": {"by-type": 1},
    "resources": {"by-project": 0},
}


class RebuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = cli.build_parser()

    def setUp(self) -> None:
        # Every builder is replaced; the log records what ran, in order.
        self.calls: list[str] = []

        def logged(name, result):
            def run(*_args, **_kwargs):
                self.calls.append(name)
                return result
            return run

        self.patchers = [
            mock.patch.object(
                anatomy, f"rebuild_{domain}", side_effect=logged(f"views {domain}", counts)
            )
            for domain, counts in VIEW_COUNTS.items()
        ] + [
            mock.patch.object(indexing, "rebuild", side_effect=logged(
                "index", {"path": "/ws/index/index.sqlite", "objects": 7, "relationships": 2}
            )),
            mock.patch.object(wiki, "build", side_effect=logged(
                "wiki", {"path": "/ws/wiki/generated", "projects": 1, "literature": 2,
                         "registered": 3, "relations": 2, "fields": 1}
            )),
            mock.patch.object(dashboard, "build", side_effect=logged(
                "dashboard", {"path": "/ws/dashboard.html", "objects": 7, "relations": 2,
                              "connected": 4, "open_tasks": 1}
            )),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()

    def run_ws(self, *words):
        args = self.parser.parse_args(list(words))
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                args.func(args)
            except SystemExit as exc:
                code = exc.code
        return out.getvalue(), err.getvalue(), code

    def test_bare_rebuild_runs_every_layer_in_order(self):
        out, err, code = self.run_ws("rebuild")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(
            self.calls,
            [f"views {domain}" for domain in registry.VIEW_DOMAINS]
            + ["index", "wiki", "dashboard"],
        )
        self.assertIn("links: 9  skipped, file missing: 1", out)
        self.assertIn("rebuilt index: /ws/index/index.sqlite  objects: 7  relations: 2", out)

    def test_one_target_runs_only_that_layer(self):
        for target in ("index", "wiki", "dashboard"):
            with self.subTest(target=target):
                self.calls.clear()
                self.run_ws("rebuild", target)
                self.assertEqual(self.calls, [target])
        self.calls.clear()
        self.run_ws("rebuild", "views")
        self.assertEqual(self.calls, [f"views {domain}" for domain in registry.VIEW_DOMAINS])
        self.calls.clear()
        self.run_ws("rebuild", "views", "documents")
        self.assertEqual(self.calls, ["views documents"])

    def test_json_is_keyed_by_target(self):
        out, _, _ = self.run_ws("rebuild", "views", "literature", "--json")
        self.assertEqual(
            json.loads(out),
            {"views": {"literature": {
                "root": str(rebuild._view_root("literature")),
                "links": 5,
                "trees": {"by-author": 5},
            }}},
        )
        out, _, _ = self.run_ws("rebuild", "--json")
        self.assertEqual(list(json.loads(out)), list(registry.REBUILD_TARGETS))

    def test_broken_anatomy_fails_views_and_still_rebuilds_the_rest(self):
        with mock.patch.object(
            anatomy, "rebuild_projects", side_effect=anatomy.AnatomyError("bad ring")
        ):
            out, err, code = self.run_ws("rebuild", "--json")
        self.assertEqual(code, 1)
        self.assertIn("error: views: bad ring", err)
        result = json.loads(out)
        self.assertEqual(result["views"], {"error": "bad ring"})
        self.assertEqual(self.calls, ["index", "wiki", "dashboard"])

    def test_older_spellings_run_the_same_handler(self):
        for older, current in registry.OLDER_REBUILD_SPELLINGS.items():
            with self.subTest(older=older):
                args = self.parser.parse_args(older.split())
                self.assertIs(args.func, rebuild.command_rebuild)
                self.assertEqual(args.current_spelling, current)
                self.calls.clear()
                _, err, code = self.run_ws(*older.split())
                self.assertEqual(code, 0)
                self.assertIn(f"the current spelling is `ws {current}`", err)
                _, target, *domain = current.split()
                expected = f"{target} {domain[0]}" if domain else target
                self.assertEqual(self.calls, [expected])

    def test_listings_offer_only_the_current_spelling(self):
        canonical = {
            " ".join(words) for words in registry._canonical_capability_paths(self.parser)
        }
        self.assertTrue(
            {"rebuild", "rebuild views", "rebuild index", "rebuild wiki", "rebuild dashboard"}
            <= canonical
        )
        for older in registry.OLDER_REBUILD_SPELLINGS:
            with self.subTest(older=older):
                self.assertNotIn(older, canonical)
                self.assertTrue(registry.is_compatibility_path(tuple(older.split())))
        everything = {path for path, _ in registry.leaf_commands(self.parser, include_compatibility=True)}
        self.assertTrue(set(registry.OLDER_REBUILD_SPELLINGS) <= everything)

    def test_each_target_describes_its_own_layer(self):
        for words, contract, guide in (
            (["rebuild"], "contracts/workspace.md", "help/rebuild.md"),
            (["rebuild", "views"], "contracts/folder-anatomy.md", "help/rebuild/views.md"),
            (["rebuild", "index"], "contracts/search.md", "help/rebuild.md"),
            (["rebuild", "wiki"], "contracts/wiki.md", "help/rebuild/wiki.md"),
            (["rebuild", "dashboard"], "contracts/dashboard.md", "help/rebuild/dashboard.md"),
        ):
            with self.subTest(words=words):
                record = registry.command_record(self.parser, words)
                self.assertEqual(record["category"], "maintenance")
                self.assertEqual(record["contract"], contract)
                self.assertEqual(record["guide"], guide)
                self.assertTrue(record["effects"]["writes"])

    def test_rebuilding_never_invalidates_the_index(self):
        spellings = [
            ["rebuild"], ["rebuild", "views"], ["rebuild", "wiki"],
            *(older.split() for older in registry.OLDER_REBUILD_SPELLINGS),
        ]
        for words in spellings:
            with self.subTest(words=words):
                with mock.patch.object(sys, "argv", ["ws", *words]), \
                        mock.patch.object(indexing, "invalidate") as invalidate, \
                        contextlib.redirect_stdout(io.StringIO()), \
                        contextlib.redirect_stderr(io.StringIO()):
                    cli.main()
                invalidate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
