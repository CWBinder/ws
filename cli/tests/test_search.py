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

from ws_lib import catalog, indexing, paths, records, relations


def load_ws_module():
    path = Path(__file__).resolve().parents[1] / "ws"
    loader = importlib.machinery.SourceFileLoader("ws_cli_search", str(path))
    spec = importlib.util.spec_from_loader("ws_cli_search", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ws_cli = load_ws_module()


class SearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        root = Path(self.tempdir.name)
        self.people = root / "logistics" / "people"
        self.people.mkdir(parents=True)
        specs = {
            type_name: {
                **spec,
                "dir": self.people if type_name == "person" else root / "data" / spec["plural"],
            }
            for type_name, spec in catalog.SPECS.items()
        }
        self.patchers = [
            mock.patch.object(catalog, "SPECS", specs),
            mock.patch.object(paths, "PROJECTS", root / "projects" / "items"),
            mock.patch.object(paths, "LITERATURE_ITEMS", root / "literature" / "items"),
            mock.patch.object(paths, "CAREER", root / "profile" / "career"),
            mock.patch.object(relations, "RELATIONS", root / "relations"),
            mock.patch.object(indexing, "INDEX", root / "search" / "index.sqlite"),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.parser = ws_cli.build_parser()
        records.atomic_write(
            self.people / "person_example.yaml",
            {
                "schema_version": 1,
                "id": "person_example",
                "key": "maria-schwarz",
                "kind": "person",
                "name": "Maria Schwarz",
                "aliases": ["MS"],
            },
        )
        task_store = Path(specs["task"]["dir"])
        task_store.mkdir(parents=True)
        records.atomic_write(
            task_store / "ms-follow-up.yaml",
            {
                "schema_version": 1,
                "id": "task_example",
                "key": "ms-follow-up",
                "kind": "task",
                "name": "MS follow-up",
                "aliases": [],
            },
        )

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def _run(self, *parts) -> str:
        args = self.parser.parse_args(["search", *parts])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        return buffer.getvalue()

    def test_kind_first_word_scopes_the_search(self) -> None:
        people_only = self._run("people", "MS")
        self.assertIn("person:maria-schwarz", people_only)
        self.assertNotIn("task:", people_only)

        tasks_only = self._run("tasks", "MS")
        self.assertIn("task:ms-follow-up", tasks_only)
        self.assertNotIn("person:", tasks_only)

    def test_global_search_still_spans_kinds(self) -> None:
        output = self._run("MS")
        self.assertIn("person:maria-schwarz", output)
        self.assertIn("task:ms-follow-up", output)

    def test_kind_word_alone_points_at_list(self) -> None:
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self._run("people")

    def test_hit_is_printed_as_text(self) -> None:
        # The text branch is the one that regressed: --json never touched the
        # row keys, so a passing --json test said nothing about this path.
        output = self._run("schwarz")

        self.assertIn("person:maria-schwarz", output)
        self.assertIn("person", output)
        self.assertIn("Maria Schwarz", output)

    def test_hit_is_returned_as_json(self) -> None:
        # Same {id, kind, name} shape the catalog commands emit; the index
        # column is still called `title`, but that is internal to the cache.
        rows = json.loads(self._run("schwarz", "--json"))

        self.assertEqual(
            rows, [{"ref": "person:maria-schwarz", "kind": "person", "name": "Maria Schwarz"}]
        )

    def test_miss_reports_none(self) -> None:
        self.assertEqual(self._run("nothing-matches-this").strip(), "none")

    def test_alias_search_returns_the_same_canonical_ref(self) -> None:
        rows = json.loads(self._run("MS", "--json"))
        self.assertEqual(rows[0]["ref"], "person:maria-schwarz")

    def test_unquoted_multiword_query_is_joined(self) -> None:
        rows = json.loads(self._run("Maria", "Schwarz", "--json"))
        self.assertEqual(rows[0]["ref"], "person:maria-schwarz")

    def test_exact_alias_ranks_before_prefix_matches(self) -> None:
        lines = self._run("MS").splitlines()
        self.assertTrue(lines[0].startswith("person:maria-schwarz"))

    def test_internal_id_is_not_a_search_term(self) -> None:
        self.assertEqual(self._run("person_example").strip(), "none")

    def test_repeated_search_reuses_the_derived_index(self) -> None:
        if indexing.INDEX.exists():
            indexing.INDEX.unlink()
        with mock.patch.object(indexing, "rebuild", wraps=indexing.rebuild) as rebuild:
            self._run("Maria")
            self._run("Schwarz")
        self.assertEqual(rebuild.call_count, 1)


class SearchTypeFilterTests(SearchTests):
    """`--type` means the kind's own classifier, exactly as on `ws list`."""

    def setUp(self) -> None:
        super().setUp()
        documents = Path(catalog.SPECS["document"]["dir"])
        documents.mkdir(parents=True, exist_ok=True)
        for key, doc_type in (("march-slides", "presentation"), ("march-invoice", "invoice")):
            records.atomic_write(
                documents / f"{key}.yaml",
                {
                    "schema_version": 1,
                    "id": f"doc_{key}",
                    "key": key,
                    "kind": "document",
                    "name": f"March {doc_type}",
                    "aliases": [],
                    "classification": {"type": doc_type},
                },
            )

    def _fails(self, *parts) -> str:
        args = self.parser.parse_args(["search", *parts])
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer), self.assertRaises(SystemExit):
            args.func(args)
        return buffer.getvalue()

    def test_type_filters_by_classifier_not_by_kind(self) -> None:
        # The regression: --type once meant the kind, so a real classifier
        # value silently matched nothing.
        presentations = self._run("documents", "march", "--type", "presentation")
        self.assertIn("document:march-slides", presentations)
        self.assertNotIn("document:march-invoice", presentations)

    def test_unknown_type_names_the_allowed_values(self) -> None:
        with mock.patch.object(
            indexing, "_classifier_values", return_value=["presentation", "invoice"]
        ):
            message = self._fails("documents", "march", "--type", "presentaton")
        self.assertIn("unknown document type", message)
        self.assertIn("presentation", message)

    def test_type_without_a_kind_says_to_name_the_kind(self) -> None:
        message = self._fails("march", "--type", "presentation")
        self.assertIn("name the kind first", message)

    def test_type_on_a_kind_without_classifiers_is_refused(self) -> None:
        message = self._fails("people", "MS", "--type", "anything")
        self.assertIn("no type classifier", message)

    def test_enumeration_hint_carries_the_filters_already_typed(self) -> None:
        # Enumeration is list's job, but the hint must hand over a command
        # that does what was asked -- not one that drops the filter.
        message = self._fails("documents", "--type", "presentation")
        self.assertIn("ws list documents --type presentation", message)
        plain = self._fails("documents")
        self.assertIn("ws list documents`", plain)
        with_json = self._fails("documents", "--type", "presentation", "--json")
        self.assertIn("ws list documents --type presentation --json", with_json)


if __name__ == "__main__":
    unittest.main()
