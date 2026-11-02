import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import catalog, context, indexing, registry, relations


LOG = """# Log — Alpha

Newest entry first. An example entry, which is not one:

    ## YYYY-MM-DD · host
    - Did: what changed

## 2026-04-04 · mbp
- Did: fourth
- Decided: kept the grid

## 2026-03-03 · mbp
- Did: third

## 2026-02-02 · guillermo
- Did: second

## 2026-01-01 · mbp
- Did: first

## Summary of 2025
- Decided: the question is shuttling in SiMOS
"""


class ContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        # Resolved, as ws resolves its root: on macOS the temporary folder is
        # reached through a symlink.
        self.root = Path(self.tempdir.name).resolve() / "workspace"
        self.projects = self.root / "projects" / "items"
        self.stores = {
            "projects": self.root / "projects",
            "resources": self.root / "resources",
            "literature": self.root / "literature",
            "documents": self.root / "documents",
            "tasks": self.root / "tasks",
            "logistics": self.root / "logistics",
            "profile": self.root / "profile",
        }
        for folder in self.stores.values():
            folder.mkdir(parents=True)
        specs = {
            "person": {**catalog.SPECS["person"], "dir": self.root / "logistics" / "people"},
            "organisation": {**catalog.SPECS["organisation"], "dir": self.root / "logistics" / "organisations"},
            "event": {**catalog.SPECS["event"], "dir": self.root / "logistics" / "events"},
            "task": {**catalog.SPECS["task"], "dir": self.root / "tasks"},
            "document": {**catalog.SPECS["document"], "dir": self.root / "documents" / "items"},
            "resource": {**catalog.SPECS["resource"], "dir": self.root / "resources" / "items"},
            "profile": {**catalog.SPECS["profile"], "dir": self.root / "profile" / "items"},
        }
        self.patchers = [
            mock.patch.object(catalog, "SPECS", specs),
            mock.patch.object(catalog.project, "PROJECTS", self.projects),
            mock.patch.object(catalog.literature, "list_item_bibtex_files", return_value=[]),
            mock.patch.object(relations, "RELATIONS", self.root / "relations"),
            mock.patch.object(indexing, "INDEX", self.root / "index" / "index.sqlite"),
            mock.patch.object(context, "WORKSPACE", self.root),
            mock.patch.object(context, "STORES", self.stores),
        ]
        for patcher in self.patchers:
            patcher.start()
        self.cwd = os.getcwd()

        self.alpha = self.project("alpha", "Alpha", "## Purpose\n\nOld README purpose.\n")
        (self.alpha / ".context").mkdir()
        (self.alpha / ".context" / "purpose.md").write_text(
            "Find out whether shuttling works in SiMOS.\n\nAnd say so when it does not.\n",
            encoding="utf-8",
        )
        (self.alpha / ".context" / "log.md").write_text(LOG, encoding="utf-8")
        (self.alpha / "code").mkdir()
        thesis = self.project("thesis", "Thesis")
        (thesis / ".context").mkdir()
        (thesis / ".context" / "purpose.md").write_text("Finish the DPhil.\n", encoding="utf-8")
        self.beta = self.project("beta", "Beta", "## Purpose\n\nBuild the solver.\n\n## Current State\n\n- active\n")
        (self.beta / "LOG.md").write_text("# Log\n\n## 2026-05-05 · mbp\n- Did: started\n", encoding="utf-8")

        self.person = catalog.create_object("person", "Maria Schwarz", {})[0]
        self.open_task = catalog.create_object("task", "Run the grid", {"due": "2020-01-01", "priority": "high"})[0]
        self.done_task = catalog.create_object("task", "Old chore", {"status": "done"})[0]
        relations.create("project:alpha", "project:thesis", "contributes-to")
        relations.create("project:alpha", "project:beta", "depends-on")
        relations.create(self.person.ref, "project:alpha", "works-on")
        relations.create(self.open_task.ref, "project:alpha", "concerns")
        relations.create(self.done_task.ref, "project:alpha", "concerns")

    def tearDown(self) -> None:
        os.chdir(self.cwd)
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def project(self, key: str, title: str, readme: str = "") -> Path:
        folder = self.projects / key
        folder.mkdir(parents=True)
        (folder / "project.yaml").write_text(
            f"schema_version: 1\ntitle: {title}\nstatus: active\nfields: []\n", encoding="utf-8"
        )
        (folder / "README.md").write_text(f"# {title}\n\n{readme}", encoding="utf-8")
        return folder

    def brief(self, folder: Path) -> dict:
        objects = catalog.all_objects()
        return context.build(context.place_of_folder(folder, objects), objects)

    def test_a_folder_resolves_to_its_deepest_object_store_or_root(self) -> None:
        objects = catalog.all_objects()
        place = context.place_of_folder(self.alpha / "code", objects)
        self.assertEqual((place.level, place.store, place.obj.ref), ("object", "projects", "project:alpha"))
        self.assertEqual(context.place_of_folder(self.root / "projects", objects).level, "store")
        relations_folder = self.root / "relations"
        self.assertEqual(context.place_of_folder(relations_folder, objects).level, "workspace")
        self.assertIsNone(context.place_of_folder(self.root.parent, objects))

    def test_the_briefing_answers_five_questions_most_lasting_first(self) -> None:
        text = context.render(self.brief(self.alpha / "code"))
        self.assertTrue(text.startswith("WORKSPACE BRIEFING: project:alpha (Alpha)"))
        titles = ("\nWHERE YOU ARE", "\nHOUSE RULES", "\nPURPOSE", "\nUPCOMING", "\nLOG")
        positions = [text.index(title) for title in titles]
        self.assertEqual(positions, sorted(positions))
        # Shipped layers from the root down, each labelled with its origin.
        self.assertIn("[workspace · ws]", text)
        self.assertIn("[projects · ws]", text)
        self.assertIn("These rules are for the session the person is talking to", text)
        # The open task moved out of WHERE YOU ARE into UPCOMING.
        upcoming = text[text.index("\nUPCOMING"):text.index("\nLOG")]
        self.assertIn(self.open_task.ref, upcoming)
        self.assertNotIn(self.open_task.ref, text[:text.index("\nUPCOMING")])

    def test_a_layer_from_the_workspace_names_its_file(self) -> None:
        notes = self.root / ".context"
        notes.mkdir(exist_ok=True)
        (notes / "whereami.md").write_text("Owner's own note.\n", encoding="utf-8")
        brief = self.brief(self.root)
        own = [row for row in brief["whereami"] if not row["shipped"]]
        self.assertEqual([row["text"] for row in own], ["Owner's own note."])
        self.assertIn(f"[workspace · {own[0]['source']}]", context.render(brief))

    def test_a_store_leaves_out_what_it_cannot_have(self) -> None:
        text = context.render(self.brief(self.root / "projects"))
        self.assertIn("\nWHERE YOU ARE", text)
        self.assertIn("\nHOUSE RULES", text)
        for title in ("\nPURPOSE", "\nUPCOMING", "\nLOG"):
            self.assertNotIn(title, text)

    def test_a_store_that_keeps_a_log_shows_it(self) -> None:
        notes = self.root / "projects" / ".context"
        notes.mkdir(exist_ok=True)
        (notes / "log.md").write_text("# Log\n\n## 2026-06-06 · mbp\n- Did: triage\n", encoding="utf-8")
        text = context.render(self.brief(self.root / "projects"))
        self.assertIn("\nLOG", text)
        self.assertIn("2026-06-06 · mbp", text)
        self.assertNotIn("\nPURPOSE", text)

    def test_location_glosses_neighbours_and_lists_only_open_tasks(self) -> None:
        brief = self.brief(self.alpha)
        groups = {(group["relation"], group["direction"]): group for group in brief["neighbours"]}
        self.assertIn("change it in its own folder", groups[("depends-on", "out")]["meaning"])
        self.assertEqual(groups[("works-on", "in")]["items"][0]["ref"], self.person.ref)
        # The purpose chain shows under the purpose, tasks under their own heading.
        self.assertNotIn(("contributes-to", "out"), groups)
        self.assertEqual([row["ref"] for row in brief["tasks"]], [self.open_task.ref])
        self.assertTrue(brief["tasks"][0]["overdue"])

    def test_purpose_comes_from_context_and_follows_the_chain_upwards(self) -> None:
        brief = self.brief(self.alpha)
        self.assertEqual(brief["purpose"]["fallback"], "")
        self.assertIn("Find out whether shuttling works", brief["purpose"]["text"])
        self.assertEqual(
            brief["serves"],
            [{"ref": "project:thesis", "name": "Thesis", "purpose": "Finish the DPhil."}],
        )

    def test_a_purpose_cycle_ends_the_chain(self) -> None:
        relations.create("project:thesis", "project:alpha", "contributes-to")
        self.assertEqual([row["ref"] for row in self.brief(self.alpha)["serves"]], ["project:thesis"])

    def test_the_log_shows_the_latest_entries_and_every_summary(self) -> None:
        brief = self.brief(self.alpha)
        headings = [entry["heading"] for entry in brief["log"]["entries"]]
        self.assertEqual(len(headings), 5, "the indented example in the preamble is not an entry")
        text = "\n".join(context.log_lines(brief))
        for heading in ("2026-04-04 · mbp", "2026-03-03 · mbp", "2026-02-02 · guillermo", "Summary of 2025"):
            self.assertIn(heading, text)
        self.assertNotIn("2026-01-01", text)
        self.assertIn("1 older entries", text)

    def test_older_locations_are_read_and_marked(self) -> None:
        brief = self.brief(self.beta)
        self.assertEqual(brief["purpose"]["text"], "Build the solver.")
        self.assertIn("README.md", brief["purpose"]["fallback"])
        self.assertTrue(brief["log"]["older_location"])
        self.assertEqual(brief["log"]["entries"][0]["heading"], "2026-05-05 · mbp")
        # `ws show` reports only the object's own .context/ notes.
        self.assertEqual(context.show_summary(catalog.resolve("project:beta")), {})

    def test_a_record_only_object_has_neighbours_but_no_purpose_or_log(self) -> None:
        objects = catalog.all_objects()
        brief = context.build(context.place_of_ref(self.person.ref), objects)
        self.assertIsNone(brief["purpose"])
        self.assertIsNone(brief["log"])
        self.assertEqual(brief["neighbours"][0]["items"][0]["ref"], "project:alpha")
        text = context.render(brief)
        self.assertNotIn("\nPURPOSE", text)
        self.assertNotIn("\nLOG", text)
        # Asked for directly, the aspect still says why there is none.
        self.assertIn("a record-only object", "\n".join(context.purpose_lines(brief)))

    def test_the_root_briefs_the_agenda(self) -> None:
        brief = self.brief(self.root)
        self.assertEqual(brief["briefing"], "workspace")
        self.assertEqual([row["ref"] for row in brief["agenda"]["due"]], [self.open_task.ref])
        self.assertEqual(
            [row["ref"] for row in brief["agenda"]["active_projects"]],
            ["project:alpha", "project:beta", "project:thesis"],
        )
        text = context.render(brief)
        self.assertIn(self.open_task.ref, text[text.index("\nUPCOMING"):])
        self.assertIn("project:thesis", text[:text.index("\nHOUSE RULES")])

    def test_outside_the_workspace_nothing_is_printed(self) -> None:
        os.chdir(self.root.parent)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            context.command_context(argparse.Namespace(ref=None, json=False))
        self.assertEqual(buffer.getvalue(), "")

    def test_bare_context_briefs_the_current_folder(self) -> None:
        os.chdir(self.alpha / "code")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            context.command_context(argparse.Namespace(ref=None, json=True))
        self.assertEqual(json.loads(buffer.getvalue())["ref"], "project:alpha")

    def test_show_prints_one_aspect_in_full(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            catalog.command_show_any(argparse.Namespace(
                objects=["log", "of", "project:alpha"], relation=None, json=False,
            ))
        self.assertIn("2026-01-01 · mbp", buffer.getvalue())
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            catalog.command_show_any(argparse.Namespace(
                objects=["purpose", "project:alpha"], relation=None, json=True,
            ))
        self.assertEqual(json.loads(buffer.getvalue())["serves"][0]["ref"], "project:thesis")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            catalog.command_show_any(argparse.Namespace(objects=["log", "of"], relation=None, json=False))

    def test_show_adds_the_objects_own_purpose_and_log(self) -> None:
        summary = context.show_summary(catalog.resolve("project:alpha"))
        self.assertEqual(summary["purpose"], "Find out whether shuttling works in SiMOS.")
        self.assertEqual((summary["log"]["entries"], summary["log"]["latest"]), (5, "2026-04-04 · mbp"))

    def test_context_is_a_registered_objects_command(self) -> None:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ws_lib import cli as ws_cli

        parser = ws_cli.build_parser()
        self.assertEqual(registry.command_category(["context"]), "objects")
        findings = [row["message"] for row in registry.cli_findings(parser) if "context" in row["message"]]
        self.assertEqual(findings, [])
        record = registry.command_record(parser, ["context"])
        self.assertEqual(record["contract"], "contracts/context.md")
        self.assertFalse(record["effects"]["writes"])


if __name__ == "__main__":
    unittest.main()
