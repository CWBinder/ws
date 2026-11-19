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

from ws_lib import catalog, context, indexing, project, registry, relations


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
        self.assertIn("1 older entry: ws show log of project:alpha", text)

    def test_older_locations_are_read_and_marked(self) -> None:
        brief = self.brief(self.beta)
        self.assertEqual(brief["purpose"]["text"], "Build the solver.")
        self.assertIn("README.md", brief["purpose"]["fallback"])
        self.assertTrue(brief["log"]["older_location"])
        self.assertEqual(brief["log"]["entries"][0]["heading"], "2026-05-05 · mbp")
        # `ws show` reports only the object's own .context/ notes.
        self.assertEqual(context.show_summary(catalog.resolve("project:beta")), {})
        text = "\n".join(context.purpose_lines(brief) + context.log_lines(brief))
        self.assertEqual(text.count("`ws projects migrate` moves it"), 2)

    def test_a_placeholder_purpose_reads_as_not_set_yet(self) -> None:
        gamma = self.project("gamma", "Gamma", f"## Purpose\n\n{project.README_PURPOSE_POINTER}\n")
        (gamma / ".context").mkdir()
        (gamma / ".context" / "purpose.md").write_text(
            (project.TEMPLATES / "purpose.md").read_text(encoding="utf-8"), encoding="utf-8"
        )

        brief = self.brief(gamma)

        self.assertIsNone(brief["purpose"], "neither the placeholder nor the README's pointer is a purpose")
        text = "\n".join(context.purpose_lines(brief))
        self.assertIn(f"not set yet: {context._home_path(gamma)}/.context/purpose.md holds it", text)
        self.assertIn("ask them, never invent it", text)
        self.assertEqual(context.show_summary(catalog.resolve("project:gamma")), {})

    def test_an_unset_purpose_comes_first_as_the_next_step(self) -> None:
        gamma = self.project("gamma", "Gamma")
        (gamma / ".context").mkdir()
        (gamma / ".context" / "purpose.md").write_text(
            (project.TEMPLATES / "purpose.md").read_text(encoding="utf-8"), encoding="utf-8"
        )

        lines = context.render(self.brief(gamma)).splitlines()

        self.assertTrue(lines[0].startswith("WORKSPACE BRIEFING: project:gamma"))
        nxt = (
            "Next: the purpose is not set. Ask the person, then write their words into "
            f"{context._home_path(gamma)}/.context/purpose.md"
        )
        self.assertEqual(lines[3], nxt)
        self.assertEqual(lines[5], "WHERE YOU ARE")
        purpose = lines.index("PURPOSE")
        self.assertIn("not set yet", lines[purpose + 1])  # the section still says so in its place
        for folder in (self.alpha, self.beta, self.root, self.root / "projects"):
            # A purpose (also one in an older location), the root and a store: no such line.
            self.assertNotIn("Next:", context.render(self.brief(folder)).split("WHERE YOU ARE")[0], folder)

    def test_a_projects_description_is_its_purpose(self) -> None:
        metadata = self.alpha / "project.yaml"
        metadata.write_text(metadata.read_text(encoding="utf-8") + "description: >\n  Stale copy.\n", encoding="utf-8")

        data = indexing.searchable_data(catalog.resolve("project:alpha"))

        self.assertEqual(data["description"], "Find out whether shuttling works in SiMOS.\n\nAnd say so when it does not.")
        self.assertNotIn("Stale copy.", json.dumps(data))

    def test_comments_are_left_out_of_a_filled_purpose(self) -> None:
        delta = self.project("delta", "Delta")
        (delta / ".context").mkdir()
        (delta / ".context" / "purpose.md").write_text(
            "<!-- Not set yet. -->\nFind out whether it scales.\n", encoding="utf-8"
        )

        brief = self.brief(delta)

        self.assertEqual(brief["purpose"]["text"], "Find out whether it scales.")

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

    def test_without_an_owner_no_line_is_printed(self) -> None:
        brief = self.brief(self.root)
        self.assertIsNone(brief["owner"])
        self.assertNotIn("[workspace · owner]", context.render(brief))

    def test_every_briefing_names_the_owner_after_the_workspace_layers(self) -> None:
        identity = catalog.create_object("profile", "Maria Example Schwarz", {"type": "identity"})[0]
        self.assertEqual(
            self.brief(self.root)["owner"],
            {"name": "Maria Example Schwarz", "person": "", "identity": identity.ref},
        )
        catalog.edit_object(self.person, {"owner": True})
        self.assertEqual(
            self.brief(self.alpha)["owner"],
            {"name": "Maria Schwarz", "person": self.person.ref, "identity": identity.ref},
        )
        (self.root / ".context").mkdir()
        (self.root / ".context" / "whereami.md").write_text("Root note.\n", encoding="utf-8")
        (self.stores["projects"] / ".context").mkdir()
        (self.stores["projects"] / ".context" / "whereami.md").write_text("Store note.\n", encoding="utf-8")
        text = context.render(self.brief(self.alpha))
        owner_at = text.index("[workspace · owner]")
        self.assertLess(text.index("Root note."), owner_at)
        self.assertLess(owner_at, text.index("Store note."))
        self.assertIn("This is the workspace of Maria Schwarz. For their details: ws owner", text)

    def test_outside_the_workspace_nothing_is_printed(self) -> None:
        os.chdir(self.root.parent)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            context.command_context(argparse.Namespace(ref=None, json=False, full=False))
        self.assertEqual(buffer.getvalue(), "")

    def test_bare_context_briefs_the_current_folder(self) -> None:
        os.chdir(self.alpha / "code")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            context.command_context(argparse.Namespace(ref=None, json=True, full=False))
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

    def run_context(self, ref: str | None, full: bool = False, as_json: bool = False) -> str:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            context.command_context(argparse.Namespace(ref=ref, json=as_json, full=full))
        return buffer.getvalue()

    def write_log(self, folder: Path, sizes: list[int], summary: int = 0) -> None:
        """A log whose entries, newest first, hold about the given number of
        characters each, in lines of 100."""
        parts = ["# Log\n"]
        for number, size in enumerate(sizes):
            lines = "\n".join(f"- Did: step {number}.{line} " + "x" * 80 for line in range(max(1, size // 100)))
            parts.append(f"## 2026-06-{30 - number:02d} · mbp\n{lines}\n")
        if summary:
            parts.append("## Summary of 2025\n" + "\n".join("- Found: " + "y" * 90 for _ in range(summary // 100)) + "\n")
        (folder / ".context").mkdir(exist_ok=True)
        (folder / ".context" / "log.md").write_text("\n".join(parts), encoding="utf-8")

    @staticmethod
    def groups(words: list[str], count: int) -> list[dict]:
        """Neighbour groups of `count` objects with long names, one per word."""
        return [
            {
                "relation": word,
                "direction": "in",
                "meaning": "",
                "count": count,
                "items": [
                    {"ref": f"document:{word}-{number:02d}-" + "x" * 60, "name": "A rather long document title " * 3}
                    for number in range(count)
                ],
            }
            for word in words
        ]

    def assert_fits(self, text: str) -> str:
        """The closing line of a briefing that fits under the limit."""
        self.assertLess(len(text) + 1, context.BRIEFING_LIMIT)
        self.assertTrue(text.startswith("WORKSPACE BRIEFING: "))
        closing = text.splitlines()[-1]
        self.assertTrue(closing.startswith("Trimmed to stay under 9,500 characters: "), closing)
        return closing

    def test_a_briefing_that_fits_is_printed_whole(self) -> None:
        brief = self.brief(self.alpha)
        self.assertEqual(context.fit(brief), context.render(brief))
        self.assertNotIn("Trimmed", self.run_context("project:alpha"))

    def test_older_log_entries_are_given_up_first(self) -> None:
        self.write_log(self.alpha, [2800, 2800, 2800], summary=2800)

        text = context.fit(self.brief(self.alpha))

        closing = self.assert_fits(text)
        self.assertIn("2026-06-30 · mbp", text, "the newest entry stays")
        self.assertNotIn("Summary of 2025", text, "the oldest entry shown goes first")
        self.assertIn("older log entries", closing)
        self.assertNotIn("related", closing)
        self.assertIn(self.person.ref, text, "related objects are untouched while the log suffices")
        self.assertRegex(text, r"\.\.\. \d older entries: ws show log of project:alpha")
        self.assertTrue(closing.endswith("Everything: ws context project:alpha --full"))

    def test_related_objects_come_next_each_list_pointing_to_the_rest(self) -> None:
        brief = self.brief(self.alpha)
        brief["neighbours"] = self.groups(["presents", "describes", "supports", "cites", "reviews", "mentions"], 12)

        text = context.fit(brief)

        closing = self.assert_fits(text)
        self.assertRegex(closing, r": \d+ related objects\. ")
        self.assertIn("2026-04-04 · mbp", text)
        for word in ("presents", "mentions"):
            self.assertRegex(text, rf"\.\.\. \d+ more: ws show project:alpha --as {word}\n")

    def test_then_the_longest_note_becomes_a_pointer_to_its_file(self) -> None:
        note = self.alpha / ".context" / "instructions.md"
        note.write_text("Work carefully here.\n\n" + ("Rule: " + "z" * 94 + "\n") * 80, encoding="utf-8")
        (self.root / ".context").mkdir()
        (self.root / ".context" / "instructions.md").write_text("Short root rule. " * 40, encoding="utf-8")

        text = context.fit(self.brief(self.alpha))

        closing = self.assert_fits(text)
        source = context._home_path(note)
        self.assertIn(f"Read it before working here: {source}", text)
        self.assertNotIn("Work carefully here.", text)
        self.assertIn("Short root rule.", text, "only the notes needed are given up, longest first")
        self.assertIn("These rules are for the session the person is talking to", text, "shipped text stays")
        # What was trimmed on the way and still fits comes back.
        self.assertIn("Summary of 2025", text)
        self.assertIn(self.person.ref, text)
        self.assertEqual(closing, f"Trimmed to stay under 9,500 characters: the note {source}. "
                                  "Everything: ws context project:alpha --full")

    def test_a_newest_entry_too_long_to_fit_is_shortened(self) -> None:
        # Few lines, each of them long: the line limit alone does not help.
        long_lines = "\n".join(f"- Found: result {line} " + "w " * 1000 for line in range(6))
        (self.alpha / ".context" / "log.md").write_text(
            f"# Log\n\n## 2026-06-30 · mbp\n{long_lines}\n\n## 2026-06-29 · mbp\n- Did: less\n", encoding="utf-8"
        )

        text = context.fit(self.brief(self.alpha))

        closing = self.assert_fits(text)
        self.assertIn("2026-06-30 · mbp", text)
        self.assertIn(" …\n  ... the rest of the entry above and 1 older entry: ws show log of project:alpha", text)
        self.assertIn("the end of the newest log entry", closing)
        self.assertIn(self.person.ref, text, "related objects outlast the newest history")

    def test_as_a_last_resort_the_end_is_cut(self) -> None:
        brief = self.brief(self.alpha)
        brief["description"] = "A description far too long for any briefing. " * 300

        text = context.fit(brief)

        closing = self.assert_fits(text)
        self.assertIn("the end of the briefing", closing)
        self.assertIn("[projects · ws]", text, "the most lasting part stays")
        self.assertTrue(text.endswith(f"\n  ...\n\n{closing}"))

    def test_full_prints_everything_and_json_stays_whole(self) -> None:
        self.write_log(self.alpha, [2400] * 30)
        brief = self.brief(self.alpha)
        brief_json = json.loads(self.run_context("project:alpha", as_json=True))

        trimmed = self.run_context("project:alpha")
        full = self.run_context("project:alpha", full=True)

        self.assert_fits(trimmed.rstrip("\n"))
        self.assertGreater(len(full), context.BRIEFING_LIMIT)
        self.assertNotIn("Trimmed", full)
        self.assertNotIn("older entr", full)
        for entry in brief["log"]["entries"]:
            self.assertIn(entry["heading"], full)
        self.assertEqual(json.loads(self.run_context("project:alpha", full=True, as_json=True)), brief_json)
        self.assertEqual(len(brief_json["log"]["entries"]), 30)

    def test_a_store_or_the_root_points_to_its_log_file(self) -> None:
        for folder in (self.stores["projects"], self.root):
            self.write_log(folder, [100] * 5)
            path = context._home_path(folder / ".context" / "log.md")
            text = "\n".join(context.log_lines(self.brief(folder)))
            self.assertIn(f"... 2 older entries: read {path}", text)
            self.assertNotIn("ws show log of", text)
        brief = self.brief(self.root)
        brief["agenda"]["active_projects"] = [{"ref": f"project:p{n:03d}", "name": "x" * 90} for n in range(200)]
        closing = self.assert_fits(context.fit(brief))
        self.assertIn("active projects", closing)
        self.assertTrue(closing.endswith(f"Everything: `ws context --full`, run in {context._home_path(self.root)}"))

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
