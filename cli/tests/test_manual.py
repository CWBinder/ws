import contextlib
import io
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import cli as ws_cli
from ws_lib import manual, paths, registry

SOURCE_ROOT = Path(__file__).resolve().parents[2]


class ManualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = ws_cli.build_parser()

    def help_text(self, *words):
        args = self.parser.parse_args(["help", *words])
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        return buffer.getvalue()

    def test_shipped_pages_follow_the_rules(self):
        # Every page documents something real, has a title, links only by
        # `ws help ...`, and every such reference resolves.
        self.assertEqual(manual.findings(self.parser), [])

    def test_bare_help_is_the_overview_then_the_map_then_the_manuals(self):
        text = self.help_text()
        overview = text.index("# The workspace")
        the_map = text.index("## Map")
        manuals = text.index("## Manuals")
        self.assertLess(overview, the_map)
        self.assertLess(the_map, manuals)
        for kind in manual.KIND_ORDER:
            self.assertIn(registry.KIND_PLURALS[kind], text[manuals:])
        self.assertIn("ws help relations", text[manuals:])
        # The map does not point at the manual it is printed inside.
        self.assertNotIn("The full overview and every manual", text)

    def test_bare_ws_prints_the_map_with_a_pointer_to_the_manual(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            registry.print_overview()
        self.assertIn("ws help", buffer.getvalue())
        self.assertNotIn("# The workspace", buffer.getvalue())

    def test_a_kind_page_lists_every_command_for_the_kind(self):
        text = self.help_text("projects")
        self.assertTrue(text.startswith("# Projects"))
        commands = text[text.index("## Commands"):]
        for record in registry.kind_capability_records(self.parser, "projects"):
            self.assertIn(record["command"], commands)

    def test_kind_words_work_in_either_number(self):
        self.assertEqual(self.help_text("project"), self.help_text("projects"))
        self.assertEqual(self.help_text("relation"), self.help_text("relations"))

    def test_a_command_page_carries_its_body_flags_and_kind_pointer(self):
        text = self.help_text("create", "project")
        self.assertTrue(text.startswith("# Creating a project"))
        usage = text.index("## Usage")
        self.assertIn("--has-code", text[usage:])
        self.assertIn("About projects: `ws help projects`", text)

    def test_a_parent_command_lists_the_pages_below_it(self):
        text = self.help_text("create")
        for child in ("project", "subproject", "task", "resource", "profile"):
            self.assertIn(f"ws help create {child}", text)
        # Compatibility spellings are not advertised.
        self.assertNotIn("ws help create agent", text)

    def test_a_command_without_a_page_still_prints_its_flags(self):
        text = self.help_text("projects", "add-field")
        self.assertIn("usage: ws projects add-field", text)

    def test_short_help_stays_the_flags_alone(self):
        parser = registry.resolve_parser(self.parser, ("create", "project"))
        self.assertNotIn("# Creating a project", parser.format_help())

    def test_unknown_paths_are_refused(self):
        self.assertIsNone(manual.render(self.parser, ("no-such-thing",)))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.help_text("no-such-thing")

    def test_findings_catch_broken_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "help"
            (base / "create").mkdir(parents=True)
            (base / "ws.md").write_text("# Overview\n", encoding="utf-8")
            (base / "create" / "nothing.md").write_text("# Nothing\n", encoding="utf-8")
            (base / "untitled.md").write_text("no title\n", encoding="utf-8")
            (base / "linked.md").write_text(
                "# Linked\n\nSee [there](elsewhere.md) and `ws help no-such-page`.\n",
                encoding="utf-8",
            )
            with mock.patch.object(paths, "SYSTEM", Path(tmp)):
                messages = " | ".join(row["message"] for row in manual.findings(self.parser))
        self.assertIn("create/nothing.md: no command", messages)
        self.assertIn("untitled.md: no `# ` title", messages)
        self.assertIn("linked.md: file link", messages)
        self.assertIn("`ws help no-such-page` resolves to nothing", messages)

    def test_completion_offers_pages_after_help(self):
        def complete(*words):
            args = self.parser.parse_args(["__complete-path", *words])
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                args.func(args)
            return buffer.getvalue().split()

        first = complete("help")
        for word in ("projects", "people", "relations", "create", "rebuild"):
            self.assertIn(word, first)
        self.assertIn("project", complete("help", "create"))

    def test_every_help_folder_is_packaged(self):
        # setuptools data-files globs do not recurse, so each folder of
        # pages needs its own entry or an installed ws loses those pages.
        pyproject = (SOURCE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        packaged = set(re.findall(r'"share/ws/(help[^"]*)" = \["help', pyproject))
        folders = {
            path.relative_to(SOURCE_ROOT).as_posix()
            for path in [SOURCE_ROOT / "help", *(SOURCE_ROOT / "help").rglob("*")]
            if path.is_dir()
        }
        self.assertEqual(folders, packaged)

    def test_describe_names_the_page_and_the_command_that_prints_it(self):
        record = registry.command_record(self.parser, ["create", "project"])
        self.assertEqual(record["guide"], "help/create/project.md")
        self.assertEqual(record["manual"], "ws help create project")
        # A command without a page of its own falls back to its kind's page.
        record = registry.command_record(self.parser, ["projects", "add-field"])
        self.assertEqual(record["guide"], "help/projects.md")
        # Every command routes to a page that ships.
        for words in registry._canonical_capability_paths(self.parser):
            guide = registry.command_record(self.parser, words)["guide"]
            self.assertTrue((SOURCE_ROOT / guide).is_file(), guide)


if __name__ == "__main__":
    unittest.main()
