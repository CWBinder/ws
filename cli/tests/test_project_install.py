import argparse
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import project

LOG_MD_AGENTS = """# AGENTS — {name}

Read first:
- README.md
- LOG.md (newest entries first; read until you know the current state)
- project.yaml
- this file

Folders:
- in/: inputs the work consumes (device designs, external data, parameters)
- put material in the folder that fits; add a new top-level folder only when none does, and record it with the reason in LOG.md

Log:
- before ending a working session, add an entry at the top of LOG.md: date, host, what you did, what was decided and why, what comes next

Rules:
- ask before destructive changes
- keep LOG.md entries short

Agent instructions:
- this file is project-wide context
- do not store agent memory or session state in this file; that goes in LOG.md
"""

LOG_MD_README = """# {name}

## Purpose

{purpose}

## Current State

- Status: `active`

## Important Files

- `AGENTS.md` - project-wide instructions for agents and humans
- `LOG.md` - what happened, newest first; read it when resuming
- `README.md` - human-readable overview
"""

OLD_LOG = "# Log — Old\n\n## 2026-11-01 · mbp\n\n- Did: created the project.\n"


class ProjectInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.slide_generator = self.root / "SlideGenerator"
        self.slide_generator.mkdir()
        (self.slide_generator / "pyproject.toml").write_text(
            '[project]\nname = "slide-factory"\n', encoding="utf-8"
        )
        self.config_values: dict = {}
        self.patchers = [
            mock.patch.object(project, "PROJECTS", self.projects),
            mock.patch.object(project, "LITERATURE_ITEMS", self.root / "literature"),
            mock.patch.object(project, "PROJECT_TAXONOMY", self.root / "project-taxonomy.yaml"),
            mock.patch.object(project, "SLIDE_GENERATOR_PATH", self.slide_generator),
            mock.patch.object(project.ws_config, "get", self.config_get),
            mock.patch.object(project, "_relate_project_links"),
        ]
        for patcher in self.patchers:
            patcher.start()

    def config_get(self, path: str, default=None):
        return self.config_values.get(path, default)

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def create_project(self, name: str, **overrides: bool) -> Path:
        values = {
            "name": name,
            "title": None,
            "type": None,
            "status": "active",
            "description": "Temporary project install test.",
            "field": None,
            "keyword": None,
            "host": None,
            "has_code": False,
            "has_paper": False,
            "has_data": False,
            "server_compute": False,
            "python": False,
            "venv": False,
            "use_project": None,
            "interactive": False,
            "non_interactive": True,
            "projects_dir": None,
        }
        values.update(overrides)
        with contextlib.redirect_stdout(io.StringIO()):
            project.command_new_project(argparse.Namespace(**values))
        return project.PROJECTS / project.project_slug(values["name"])

    def _fake_run(self, calls: list):
        def run(cmd, **_kwargs):
            calls.append(cmd)
            if cmd[:3] == [sys.executable, "-m", "venv"]:
                (Path(cmd[3]) / "bin").mkdir(parents=True)
                (Path(cmd[3]) / "bin" / "python").write_text("", encoding="utf-8")
            return mock.Mock(returncode=0)

        return run

    def run_install(
        self, *tokens: str, name: str | None = None, use_project: list[str] | None = None
    ) -> tuple[list, str]:
        calls: list = []
        namespace = argparse.Namespace(tokens=list(tokens), projects_dir=None, use_project=use_project)
        if name is not None:
            namespace.name = name
        with mock.patch.object(project.subprocess, "run", side_effect=self._fake_run(calls)):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                project.command_project_install(namespace)
        return calls, stdout.getvalue()

    def create_installable_dependency(self, name: str) -> Path:
        dep = self.projects / name
        dep.mkdir()
        (dep / "project.yaml").write_text(f"schema_version: 1\nname: {name}\n", encoding="utf-8")
        (dep / "pyproject.toml").write_text(f'[project]\nname = "{name}"\n', encoding="utf-8")
        return dep

    def test_slides_retrofit_records_and_installs(self) -> None:
        root = self.create_project("talk-demo")
        yaml_before = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertIn("has_slides: false", yaml_before)

        calls, output = self.run_install("slides", name="talk-demo")

        yaml_after = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertIn("has_slides: true", yaml_after)
        self.assertIn("  python: true", yaml_after)
        self.assertIn("  venv: .venv", yaml_after)
        # slides implies venv implies python implies code
        self.assertTrue((root / "code").is_dir())
        self.assertTrue((root / "slides" / ".gitkeep").exists())
        self.assertTrue((root / "pyproject.toml").exists())
        venv_py = str(root / ".venv" / "bin" / "python")
        self.assertIn([venv_py, "-m", "pip", "install", "-e", str(self.slide_generator)], calls)
        self.assertIn("updated:", output)
        meta = project.parse_project_yaml(root / "project.yaml")
        self.assertEqual(meta["has_slides"], "true")
        self.assertEqual(meta["runtime"], {"python": "true", "venv": ".venv"})

    def test_bare_install_converges_recorded_state(self) -> None:
        root = self.create_project("talk-heal")
        self.run_install("slides", name="talk-heal")
        shutil.rmtree(root / ".venv")

        calls, output = self.run_install(name="talk-heal")

        self.assertTrue((root / ".venv" / "bin" / "python").exists())
        venv_py = str(root / ".venv" / "bin" / "python")
        self.assertIn([venv_py, "-m", "pip", "install", "-e", str(self.slide_generator)], calls)
        self.assertNotIn("updated:", output)

    def test_folder_capabilities_do_not_touch_venv(self) -> None:
        root = self.create_project("notes-only")

        calls, _output = self.run_install("paper", "data", name="notes-only")

        self.assertTrue((root / "paper").is_dir())
        self.assertTrue((root / "data").is_dir())
        self.assertFalse((root / ".venv").exists())
        self.assertEqual(calls, [])
        yaml_after = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertIn("has_paper: true", yaml_after)
        self.assertIn("has_data: true", yaml_after)

    def test_nothing_recorded_reports_and_stops(self) -> None:
        self.create_project("empty-project")

        calls, output = self.run_install(name="empty-project")

        self.assertEqual(calls, [])
        self.assertIn("nothing recorded to install", output)

    def make_legacy_layout(self, name: str) -> Path:
        """A project as the templates before the project log left it: no
        log or purpose, no in/ or out/, `out/` ignored wholesale, and the old
        AGENTS.md rules."""
        root = self.create_project(name)
        shutil.rmtree(root / ".context")
        for folder in ("in", "out"):
            (root / folder / ".gitkeep").unlink()
            (root / folder).rmdir()
        (root / ".gitignore").write_text(
            ".DS_Store\n\n# Generated outputs and scratch\nout/\ntmp/\n\ndata/**\n!data/**/\n",
            encoding="utf-8",
        )
        (root / "AGENTS.md").write_text(
            f"# AGENTS — {name}\n\nRead first:\n- README.md\n- project.yaml\n- this file\n\n"
            "Rules:\n- do not create unauthorized top-level folders\n- put stable docs in docs/\n"
            "- put transient notes in notes/\n- put generated outputs in out/\n"
            "- put disposable scratch in tmp/\n- ask before destructive changes\n- never push to main\n\n"
            "Agent instructions:\n- this file is project-wide context\n- do not store agent memory in this file\n",
            encoding="utf-8",
        )
        (root / "notes").mkdir()
        (root / "notes" / "keep.md").write_text("old notes\n", encoding="utf-8")
        return root

    def test_bare_install_migrates_a_legacy_layout(self) -> None:
        root = self.make_legacy_layout("legacy-layout")

        _calls, output = self.run_install(name="legacy-layout")

        log = (root / ".context" / "log.md").read_text(encoding="utf-8")
        self.assertIn("- Did: started this log. Earlier history is in the git log and README.md.", log)
        self.assertFalse((root / "LOG.md").exists())
        self.assertEqual(project.note_text(root / ".context" / "purpose.md"), "")  # placeholder
        for folder in ("in", "out"):
            self.assertTrue((root / folder / ".gitkeep").exists(), folder)
        ignore = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertNotIn("out/", ignore)
        self.assertEqual(ignore[ignore.index("out/**"):ignore.index("out/**") + 4],
                         ["out/**", "!out/**/", "!out/**/*.md", "!out/**/.gitkeep"])
        self.assertIn("slides/**/*.pptx", ignore)
        self.assertNotIn("# Generated outputs and scratch", ignore)
        self.assertEqual(output.count(".context/log.md"), 1)
        self.assertNotIn("ws projects migrate", output)
        agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("put transient notes in notes/", agents)
        self.assertNotIn("unauthorized", agents)
        self.assertIn("- README.md\n- .context/purpose.md (what this project is for", agents)
        self.assertIn("`ws context project:legacy-layout` for the full briefing", agents)
        self.assertLess(agents.index("Folders:"), agents.index("Rules:"))
        self.assertIn("Context:\n- .context/purpose.md says what the project is for", agents)
        self.assertIn("- never push to main", agents)  # project-specific rules survive
        self.assertIn("session state in this file; that goes in .context/log.md", agents)
        self.assertNotIn("LOG.md", agents)
        # additive only: nothing moved or deleted
        self.assertEqual((root / "notes" / "keep.md").read_text(encoding="utf-8"), "old notes\n")
        self.assertIn("nothing recorded to install", output)

    def test_layout_migration_is_idempotent(self) -> None:
        root = self.make_legacy_layout("legacy-twice")
        self.run_install(name="legacy-twice")
        names = (".context/log.md", ".context/purpose.md", ".gitignore", "AGENTS.md")
        snapshot = {name: (root / name).read_text(encoding="utf-8") for name in names}

        _calls, output = self.run_install(name="legacy-twice")

        for name, text in snapshot.items():
            self.assertEqual((root / name).read_text(encoding="utf-8"), text, name)
        self.assertNotIn("updated:", output)
        self.assertNotIn("created:", output)

    def test_customized_agents_md_without_rules_block_gets_appended_rules(self) -> None:
        root = self.create_project("custom-agents")
        (root / "AGENTS.md").write_text("# Custom\n\nOur own instructions.\n", encoding="utf-8")

        self.run_install(name="custom-agents")

        agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue(agents.startswith("# Custom\n\nOur own instructions.\n\nFolders:\n"))
        self.assertIn("Context:\n", agents)

    def make_log_md_layout(self, name: str, purpose: str = "Find out whether it works.") -> Path:
        """A project as creation left it while the log was a root LOG.md and
        the purpose sat in the README and in project.yaml, with one
        hand-written LOG.md rule."""
        root = self.create_project(name)
        shutil.rmtree(root / ".context")
        (root / "LOG.md").write_text(OLD_LOG, encoding="utf-8")
        (root / "README.md").write_text(LOG_MD_README.format(name=name, purpose=purpose), encoding="utf-8")
        (root / "AGENTS.md").write_text(LOG_MD_AGENTS.format(name=name), encoding="utf-8")
        self.describe(root, purpose)
        return root

    def describe(self, root: Path, text: str, name: str = "project.yaml") -> None:
        """Give a metadata file the `description:` block older creation wrote."""
        path = root / name
        lines = path.read_text(encoding="utf-8").splitlines()
        at = next(number for number, line in enumerate(lines) if line.startswith("created:")) + 1
        lines[at:at] = ["description: >", f"  {text}"]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_migrate(self, apply: bool = False) -> str:
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            project.command_project_migrate(argparse.Namespace(refs=[], apply=apply, projects_dir=None))
        return stdout.getvalue()

    def snapshot(self, root: Path) -> dict:
        return {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file() and ".git" not in path.relative_to(root).parts
        }

    def test_migrate_without_apply_prints_the_plan_and_writes_nothing(self) -> None:
        root = self.make_log_md_layout("older")
        before = self.snapshot(root)

        output = self.run_migrate()

        self.assertEqual(self.snapshot(root), before)
        self.assertIn("project:older\n  will: move LOG.md to .context/log.md\n", output)
        self.assertIn("will: write .context/purpose.md from README.md's Purpose section, verbatim", output)
        self.assertIn("will: README.md: replace the Purpose section", output)
        self.assertIn("will: AGENTS.md: rewrite 5 template lines to name .context/ instead of LOG.md", output)
        self.assertIn("will: README.md: rewrite 1 template line to name .context/ instead of LOG.md", output)
        self.assertIn("will: project.yaml: remove description, a copy of .context/purpose.md", output)
        self.assertIn("left for you: AGENTS.md line 18 still names LOG.md: edit it by hand", output)
        self.assertIn("dry run: 6 changes in 1 project, nothing written; rerun with --apply", output)

    def test_migrate_moves_the_log_and_purpose_into_context(self) -> None:
        root = self.make_log_md_layout("older")

        output = self.run_migrate(apply=True)

        self.assertFalse((root / "LOG.md").exists())
        self.assertEqual((root / ".context" / "log.md").read_text(encoding="utf-8"), OLD_LOG)
        self.assertEqual((root / ".context" / "purpose.md").read_text(encoding="utf-8"), "Find out whether it works.\n")
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"## Purpose\n\n{project.README_PURPOSE_POINTER}\n\n## Current State", readme)
        self.assertNotIn("Find out whether it works.", readme)
        self.assertNotIn("LOG.md", readme)
        for line in project.README_CONTEXT_FILES:
            self.assertIn(line, readme)
        agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        template = (project.TEMPLATES / "AGENTS.md").read_text(encoding="utf-8").replace("<project-name>", "older")
        for block in ("Context:", "- README.md\n- .context/purpose.md", "`ws context project:older`"):
            self.assertIn(block, agents)
        for line in agents.splitlines():
            if line.startswith("- ") and ".context/" in line:
                self.assertIn(line, template)  # migration writes what creation writes
        self.assertEqual([line for line in agents.splitlines() if "LOG.md" in line], ["- keep LOG.md entries short"])
        metadata = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertNotIn("description", metadata)
        self.assertNotIn("Find out whether it works.", metadata)
        self.assertIn("created: ", metadata)
        self.assertIn("\nfields: []\n", metadata)
        self.assertIn("done: move LOG.md to .context/log.md", output)
        self.assertIn("left for you: AGENTS.md line 21 still names LOG.md", output)  # counted after the changes
        self.assertIn("migrated 1 project", output)

        after = self.snapshot(root)
        again = self.run_migrate(apply=True)
        self.assertEqual(self.snapshot(root), after, "a second run changes nothing")
        self.assertNotIn("done:", again)
        self.assertIn("nothing to move; what is listed is left for you", again)

    def test_migrate_leaves_what_it_cannot_decide(self) -> None:
        root = self.make_log_md_layout("tangled")
        (root / ".context").mkdir()
        (root / ".context" / "log.md").write_text("# Log\n", encoding="utf-8")
        (root / ".context" / "purpose.md").write_text("A different purpose.\n", encoding="utf-8")

        output = self.run_migrate(apply=True)

        self.assertTrue((root / "LOG.md").exists())
        self.assertEqual((root / ".context" / "log.md").read_text(encoding="utf-8"), "# Log\n")
        self.assertEqual((root / ".context" / "purpose.md").read_text(encoding="utf-8"), "A different purpose.\n")
        self.assertIn("Find out whether it works.", (root / "README.md").read_text(encoding="utf-8"))
        self.assertIn("left for you: both LOG.md and .context/log.md exist", output)
        self.assertIn("left for you: README.md's Purpose section differs from .context/purpose.md", output)
        # project.yaml's copy goes: the README, which stays, keeps the same text
        self.assertIn("done: project.yaml: remove description, a copy of README.md's Purpose section, which keeps it", output)
        self.assertIsNone(project.yaml_description(root / "project.yaml"))

    def test_migrate_handles_each_kind_of_project_yaml_description(self) -> None:
        placeholder = self.create_project("placeholder", description=None)
        self.describe(placeholder, project.DESCRIPTION_PLACEHOLDER)
        only_yaml = self.create_project("only-yaml", description=None)
        (only_yaml / ".context" / "purpose.md").unlink()
        self.describe(only_yaml, "Track every black box in the lab.")
        differs = self.create_project("differs", description="An agent's draft of the purpose.")
        self.describe(differs, "the persons own first words")
        before = (differs / "project.yaml").read_text(encoding="utf-8")

        output = self.run_migrate(apply=True)

        self.assertIn("project:placeholder\n  done: project.yaml: remove description, the template's placeholder", output)
        self.assertNotIn("description", (placeholder / "project.yaml").read_text(encoding="utf-8"))
        self.assertEqual(project.note_text(placeholder / ".context" / "purpose.md"), "")  # still not set
        self.assertIn("done: write .context/purpose.md from project.yaml's description, verbatim", output)
        self.assertEqual(
            (only_yaml / ".context" / "purpose.md").read_text(encoding="utf-8"), "Track every black box in the lab.\n"
        )
        self.assertIsNone(project.yaml_description(only_yaml / "project.yaml"))
        # A description that differs may be the person's own first words: it stays.
        self.assertEqual((differs / "project.yaml").read_text(encoding="utf-8"), before)
        self.assertIn(
            "project:differs\n  left for you: project.yaml's description differs from .context/purpose.md",
            output,
        )

    def test_dropping_a_description_keeps_every_other_line(self) -> None:
        path = self.root / "project.yaml"
        path.write_text(
            "schema_version: 1\nname: x\ncreated: 2026-01-01\ndescription: >\n  First paragraph\n  goes on.\n\n"
            "  Second paragraph.\n\nfields: [physics]\nsync:\n  primary_host: mac\n",
            encoding="utf-8",
        )
        self.assertEqual(project.yaml_description(path), "First paragraph goes on.\nSecond paragraph.".replace("\n", " "))

        project._drop_yaml_description(path)

        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "schema_version: 1\nname: x\ncreated: 2026-01-01\n\nfields: [physics]\nsync:\n  primary_host: mac\n",
        )

    def test_migrate_fills_a_placeholder_purpose_from_the_readme(self) -> None:
        root = self.make_log_md_layout("placeheld")
        (root / ".context").mkdir()
        (root / ".context" / "purpose.md").write_text(
            (project.TEMPLATES / "purpose.md").read_text(encoding="utf-8"), encoding="utf-8"
        )

        self.run_migrate(apply=True)

        self.assertEqual((root / ".context" / "purpose.md").read_text(encoding="utf-8"), "Find out whether it works.\n")
        self.assertEqual(project.readme_purpose(root / "README.md"), "")

    def test_migrate_covers_subprojects_and_starts_missing_notes(self) -> None:
        parent = self.create_project("host-project")
        with contextlib.redirect_stdout(io.StringIO()):
            project.command_project_sub(argparse.Namespace(
                name=["study"], project="host-project", description="Measure it.", projects_dir=None,
            ))
        sub = parent / "study"
        (sub / ".context" / "log.md").rename(sub / "LOG.md")
        self.describe(sub, "Measure it.", name="subproject.yaml")
        bare = self.create_project("bare-project")
        shutil.rmtree(bare / ".context")

        output = self.run_migrate(apply=True)

        self.assertIn("project:host-project/study\n  done: move LOG.md to .context/log.md", output)
        self.assertTrue((sub / ".context" / "log.md").exists())
        self.assertIn("done: subproject.yaml: remove description, a copy of .context/purpose.md", output)
        self.assertIsNone(project.yaml_description(sub / "subproject.yaml"))
        self.assertIn("done: create .context/log.md with a first entry", output)
        self.assertIn("done: create .context/purpose.md as a placeholder: not set yet", output)
        self.assertEqual(project.note_text(bare / ".context" / "purpose.md"), "")
        self.assertIn("migrated 2 projects", output)

    def test_unknown_feature_fails(self) -> None:
        self.create_project("typo-target")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                self.run_install("slidez", "slides", name="typo-target")
        self.assertIn("unknown install feature: slidez", stderr.getvalue())

    def test_enclosing_project_resolution(self) -> None:
        root = self.create_project("cwd-project")
        cwd = os.getcwd()
        try:
            os.chdir(root)
            self.run_install("data")
        finally:
            os.chdir(cwd)
        self.assertTrue((root / "data").is_dir())

    def test_slides_installs_configured_theme_packages_after_the_generator(self) -> None:
        themes = self.projects / "my-themes"
        themes.mkdir()
        (themes / "pyproject.toml").write_text('[project]\nname = "my-themes"\n', encoding="utf-8")
        loose = self.root / "loose-themes"
        loose.mkdir()
        (loose / "pyproject.toml").write_text('[project]\nname = "loose-themes"\n', encoding="utf-8")
        self.config_values["slides.themes"] = ["project:my-themes", {"project": "my-themes"}, str(loose), "project:absent"]
        self.create_project("talk-themed")
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            calls, _ = self.run_install("slides", name="talk-themed")
        venv_py = str(self.projects / "talk-themed" / ".venv" / "bin" / "python")
        installs = [call[-1] for call in calls if call[:5] == [venv_py, "-m", "pip", "install", "-e"]]
        self.assertEqual(installs, [str(self.slide_generator), str(themes), str(themes), str(loose)])
        self.assertIn("slide theme package not found: project:absent", stderr.getvalue())

    def test_shipped_slide_generator_is_brand_free_and_present(self) -> None:
        shipped = Path(project.__file__).resolve().parents[2] / "packages" / "slide_factory"
        self.assertTrue((shipped / "pyproject.toml").is_file())
        self.assertTrue((shipped / "slide_factory" / "factory.py").is_file())
        self.assertFalse((shipped / "assets").exists(), "logos belong in theme packages, not in ws")

    def test_missing_has_slides_line_inserted_after_has_data(self) -> None:
        root = self.create_project("legacy-project")
        path = root / "project.yaml"
        lines = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("has_slides:")
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.run_install("slides", name="legacy-project")

        after = path.read_text(encoding="utf-8").splitlines()
        self.assertIn("has_slides: true", after)
        self.assertEqual(after[after.index("has_data: false") + 1], "has_slides: true")

    def test_use_project_records_installs_and_creates_edge(self) -> None:
        dep = self.create_installable_dependency("library-tool")
        root = self.create_project("consumer")

        calls, output = self.run_install(name="consumer", use_project=["project:library-tool:package"])

        yaml_after = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertIn("project_dependencies:", yaml_after)
        self.assertIn("  - project: library-tool", yaml_after)
        self.assertIn("    kind: package", yaml_after)
        self.assertNotIn("project_dependencies: []", yaml_after)
        self.assertIn("  venv: .venv", yaml_after)
        self.assertIn("recorded dependency: library-tool", output)
        venv_py = str(root / ".venv" / "bin" / "python")
        self.assertIn([venv_py, "-m", "pip", "install", "-e", str(dep)], calls)
        project._relate_project_links.assert_called_once_with("consumer", ["project:library-tool"], [])

    def test_use_project_is_recorded_once(self) -> None:
        self.create_installable_dependency("library-tool")
        root = self.create_project("consumer")

        self.run_install(name="consumer", use_project=["project:library-tool"])
        _calls, output = self.run_install(name="consumer", use_project=["project:library-tool"])

        self.assertIn("already recorded: library-tool", output)
        yaml_after = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertEqual(yaml_after.count("  - project: library-tool"), 1)
        self.assertEqual(project._relate_project_links.call_count, 1)

    def test_use_project_appends_to_existing_block(self) -> None:
        self.create_installable_dependency("first-lib")
        self.create_installable_dependency("second-lib")
        root = self.create_project("consumer")

        self.run_install(name="consumer", use_project=["project:first-lib"])
        self.run_install(name="consumer", use_project=["project:second-lib"])

        meta = project.parse_project_yaml(root / "project.yaml")
        self.assertEqual(
            [dep["project"] for dep in meta["project_dependencies"]],
            ["first-lib", "second-lib"],
        )

    def test_use_project_unknown_ref_fails_before_writing(self) -> None:
        root = self.create_project("consumer")
        yaml_before = (root / "project.yaml").read_text(encoding="utf-8")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                self.run_install(name="consumer", use_project=["project:no-such-project"])
        self.assertEqual((root / "project.yaml").read_text(encoding="utf-8"), yaml_before)

    def test_use_project_on_legacy_yaml_missing_key(self) -> None:
        self.create_installable_dependency("library-tool")
        root = self.create_project("legacy-deps")
        path = root / "project.yaml"
        lines = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("project_dependencies:")
        ]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.run_install(name="legacy-deps", use_project=["project:library-tool"])

        meta = project.parse_project_yaml(path)
        self.assertEqual([dep["project"] for dep in meta["project_dependencies"]], ["library-tool"])

    def test_capability_update_preserves_unrelated_text(self) -> None:
        root = self.create_project("stable-yaml")
        path = root / "project.yaml"
        before = path.read_text(encoding="utf-8").splitlines()

        self.run_install("slides", name="stable-yaml")

        after = path.read_text(encoding="utf-8").splitlines()
        changed = {"has_code: false", "has_slides: false", "  python: false", '  venv: ""'}
        changed_to = {"has_code: true", "has_slides: true", "  python: true", "  venv: .venv"}
        self.assertEqual(
            [line for line in before if line not in changed],
            [line for line in after if line not in changed_to],
        )


if __name__ == "__main__":
    unittest.main()
