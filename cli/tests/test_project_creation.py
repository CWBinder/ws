import argparse
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import project


class ProjectCreationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.patchers = [
            mock.patch.object(project, "PROJECTS", self.projects),
            mock.patch.object(project, "LITERATURE_ITEMS", self.root / "literature"),
            mock.patch.object(project, "PROJECT_TAXONOMY", self.root / "project-taxonomy.yaml"),
            mock.patch.object(project, "_relate_project_links"),
        ]
        for patcher in self.patchers:
            patcher.start()

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
            "description": "Temporary project creation test.",
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

    def test_subproject_creation_and_invisibility(self) -> None:
        self.create_project("studies")
        with contextlib.redirect_stdout(io.StringIO()):
            project.command_project_sub(argparse.Namespace(
                name=["corner shuttling"], project="studies", description=None, projects_dir=None,
            ))
        sub = self.projects / "studies" / "corner-shuttling"
        self.assertTrue((sub / "subproject.yaml").exists())
        for folder in ("code", "data", "results"):
            self.assertTrue((sub / folder).is_dir())
        self.assertFalse((sub / ".venv").exists())
        self.assertTrue((sub / ".git").is_dir())
        self.assertIn(
            "corner-shuttling/",
            (self.projects / "studies" / ".gitignore").read_text().splitlines(),
        )
        # a subproject is not a project: invisible to discovery, listed under its parent
        self.assertEqual(project.existing_project_names(), ["studies"])
        self.assertEqual(project.subproject_names(self.projects / "studies"), ["corner-shuttling"])

    def test_subproject_grouping_folders(self) -> None:
        self.create_project("studies")
        with contextlib.redirect_stdout(io.StringIO()):
            project.command_project_sub(argparse.Namespace(
                name=["shuttling/corner"], project="studies", description=None, projects_dir=None,
            ))
        sub = self.projects / "studies" / "shuttling" / "corner"
        self.assertTrue((sub / "subproject.yaml").exists())
        self.assertIn("venv: ../../.venv", (sub / "subproject.yaml").read_text())
        # cwd inside the grouping folder: bare name lands there
        cwd = os.getcwd()
        try:
            os.chdir(self.projects / "studies" / "shuttling")
            with contextlib.redirect_stdout(io.StringIO()):
                project.command_project_sub(argparse.Namespace(
                    name=["linear"], project=None, description=None, projects_dir=None,
                ))
        finally:
            os.chdir(cwd)
        self.assertEqual(
            project.subproject_names(self.projects / "studies"),
            ["shuttling/corner", "shuttling/linear"],
        )
        # no nesting inside a subproject, no grouping via content folders
        for name in ("shuttling/corner/deeper", "data/hidden"):
            with self.subTest(name=name), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    project.command_project_sub(argparse.Namespace(
                        name=[name], project="studies", description=None, projects_dir=None,
                    ))

    def check_output(self) -> tuple:
        buffer = io.StringIO()
        code = 0
        try:
            with contextlib.redirect_stdout(buffer):
                project.command_project_check(argparse.Namespace(projects_dir=None))
        except SystemExit as exc:
            code = exc.code
        return buffer.getvalue(), code

    def test_check_passes_clean_project_and_flags_problems(self) -> None:
        self.create_project("cleanproj")
        out, code = self.check_output()
        self.assertEqual(code, 0)
        self.assertIn("ok: cleanproj", out)
        # break it: dangling cross-references and a missing required file
        root = self.projects / "cleanproj"
        meta = (root / "project.yaml").read_text()
        meta += "depends_on: [ghost-project]\nrelated_literature: [GhostKey2026]\n"
        (root / "project.yaml").write_text(meta)
        (root / "README.md").unlink()
        out, code = self.check_output()
        self.assertEqual(code, 1)
        self.assertIn("depends_on references unknown project: ghost-project", out)
        self.assertIn("related_literature references unknown item: GhostKey2026", out)
        self.assertIn("missing README.md", out)

    def make_legacy_nested_project(self, relpath: str) -> Path:
        """Hand-build a nested project: creation refuses paths, but discovery
        stays tolerant so legacy trees keep resolving."""
        root = self.projects / relpath
        root.mkdir(parents=True)
        (root / "project.yaml").write_text(
            "schema_version: 1\ntitle: Legacy\nstatus: active\nfields: []\n",
            encoding="utf-8",
        )
        return root

    def test_create_refuses_path_names(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.create_project("exampleco-simulations/shuttling/corner-shuttling")
        self.assertEqual(project.existing_project_names(), [])

    def test_legacy_nested_projects_discovered_by_relative_path(self) -> None:
        self.create_project("flatproj")
        self.make_legacy_nested_project("exampleco-simulations/shuttling/corner-shuttling")
        self.make_legacy_nested_project("sige/shuttling/corner-shuttling")
        self.assertEqual(
            project.existing_project_names(),
            [
                "exampleco-simulations/shuttling/corner-shuttling",
                "flatproj",
                "sige/shuttling/corner-shuttling",
            ],
        )

    def test_resolution_by_full_path_and_unique_leaf(self) -> None:
        self.create_project("flatproj")
        self.make_legacy_nested_project("exampleco-simulations/shuttling/corner-shuttling")
        self.assertEqual(
            project.resolve_project_name("exampleco-simulations/shuttling/corner-shuttling"),
            "exampleco-simulations/shuttling/corner-shuttling",
        )
        self.assertEqual(
            project.resolve_project_name("corner-shuttling"),
            "exampleco-simulations/shuttling/corner-shuttling",
        )
        self.assertEqual(project.resolve_project_name("flatproj"), "flatproj")

    def test_ambiguous_leaf_is_rejected(self) -> None:
        self.make_legacy_nested_project("exampleco-simulations/shuttling/corner-shuttling")
        self.make_legacy_nested_project("sige/shuttling/corner-shuttling")
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                project.resolve_project_name("corner-shuttling")

    def test_normalize_ref_resolves_leaf_and_path(self) -> None:
        self.make_legacy_nested_project("exampleco-simulations/shuttling/corner-shuttling")
        known = set(project.existing_project_names())
        self.assertEqual(
            project.normalize_ref("corner-shuttling", known),
            "exampleco-simulations/shuttling/corner-shuttling",
        )
        self.assertEqual(
            project.normalize_ref("exampleco-simulations/shuttling/corner-shuttling", known),
            "exampleco-simulations/shuttling/corner-shuttling",
        )
        self.assertIsNone(project.normalize_ref("nonexistent", known))

    def test_create_inside_store_subfolder_lands_at_store_root(self) -> None:
        stray = self.projects / "exampleco-simulations" / "shuttling"
        stray.mkdir(parents=True)
        prev = os.getcwd()
        try:
            os.chdir(stray)
            self.create_project("corner-shuttling")
        finally:
            os.chdir(prev)
        self.assertEqual(project.existing_project_names(), ["corner-shuttling"])
        self.assertTrue((self.projects / "corner-shuttling" / "project.yaml").exists())

    def test_creation_refused_inside_existing_project(self) -> None:
        self.create_project("host-project")
        prev = os.getcwd()
        try:
            os.chdir(self.projects / "host-project")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    self.create_project("nested-inside")
        finally:
            os.chdir(prev)
        self.assertNotIn("host-project/nested-inside", project.existing_project_names())

    def test_bare_project_name_prompts_when_terminal_is_interactive(self) -> None:
        args = argparse.Namespace(
            title=None,
            type=None,
            status=None,
            description=None,
            field=None,
            keyword=None,
            host=None,
            use_project=None,
            has_code=False,
            has_paper=False,
            has_data=False,
            server_compute=False,
            python=False,
            venv=False,
            interactive=False,
            non_interactive=False,
        )

        with mock.patch.object(project.sys, "stdin", mock.Mock(isatty=lambda: True)):
            self.assertTrue(project.should_prompt_for_project_setup(args))
        args.non_interactive = True
        with mock.patch.object(project.sys, "stdin", mock.Mock(isatty=lambda: True)):
            self.assertFalse(project.should_prompt_for_project_setup(args))
        args.non_interactive = False
        args.python = True
        with mock.patch.object(project.sys, "stdin", mock.Mock(isatty=lambda: True)):
            self.assertFalse(project.should_prompt_for_project_setup(args))

    def test_choice_prompt_accepts_unique_prefix(self) -> None:
        with mock.patch("builtins.input", return_value="explo\t"):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(
                    project.ask_choice("Type", ["exploration", "paper", "software", "other"], "exploration"),
                    "exploration",
                )

    def test_wizard_question_set_is_type_aware(self) -> None:
        self.assertEqual(project.wizard_question_set("organizatorial"), set())
        self.assertEqual(project.wizard_question_set("other"), set())
        self.assertIn("venv", project.wizard_question_set("research"))
        self.assertNotIn("venv", project.wizard_question_set("teaching"))
        self.assertEqual(
            project.wizard_question_set("community-extended"), set(project.FULL_QUESTION_SET)
        )

    def test_ask_choice_offers_to_extend_the_taxonomy(self) -> None:
        answers = iter(["community", "y"])
        with mock.patch("builtins.input", side_effect=lambda *_: next(answers)), \
                mock.patch.object(project, "add_taxonomy_value") as added, \
                contextlib.redirect_stdout(io.StringIO()):
            choice = project.ask_choice(
                "Type", ["research", "other"], "research", taxonomy_key="type"
            )
        self.assertEqual(choice, "community")
        added.assert_called_once_with("type", "community")

    def test_ask_choice_rejects_unknown_value_when_extension_declined(self) -> None:
        answers = iter(["community", "n", "other"])
        with mock.patch("builtins.input", side_effect=lambda *_: next(answers)), \
                mock.patch.object(project, "add_taxonomy_value") as added, \
                contextlib.redirect_stdout(io.StringIO()):
            choice = project.ask_choice(
                "Type", ["research", "other"], "research", taxonomy_key="type"
            )
        self.assertEqual(choice, "other")
        added.assert_not_called()

    def test_default_scaffold_is_minimal(self) -> None:
        root = self.create_project("minimal-project")

        for filename in ["project.yaml", "README.md", "AGENTS.md", "CLAUDE.md", ".gitignore"]:
            self.assertTrue((root / filename).exists(), filename)
        self.assertTrue((root / ".git").is_dir())
        optional_dirs = {path.name for path in root.iterdir() if path.is_dir() and path.name != ".git"}
        self.assertEqual(optional_dirs, set())

    def test_project_records_broad_fields_and_compatible_subfields(self) -> None:
        root = self.create_project(
            "classified-project",
            field=["physics"],
            subfield=["spin-qubits", "shuttling"],
        )
        meta = project.parse_project_yaml(root / "project.yaml")
        self.assertEqual(meta["fields"], ["physics"])
        self.assertEqual(meta["subfields"], ["spin-qubits", "shuttling"])

    def test_project_rejects_subfield_without_a_compatible_field(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.create_project(
                "invalid-classification",
                field=["mathematics"],
                subfield=["spin-qubits"],
            )
        self.assertFalse((self.projects / "invalid-classification").exists())

    def test_capability_flags_create_only_requested_folders(self) -> None:
        cases = [
            ("code-project", {"has_code": True}, {"code"}),
            ("paper-project", {"has_paper": True}, {"paper"}),
            ("data-project", {"has_data": True}, {"data"}),
            (
                "combined-project",
                {"has_code": True, "has_paper": True, "has_data": True},
                {"code", "paper", "data"},
            ),
        ]

        for name, flags, expected in cases:
            with self.subTest(name=name):
                root = self.create_project(name, **flags)
                optional_dirs = {path.name for path in root.iterdir() if path.is_dir() and path.name != ".git"}
                self.assertEqual(optional_dirs, expected)

    def test_spaced_name_is_slugified(self) -> None:
        root = self.create_project(["Test", "Project"])

        self.assertEqual(root.name, "test-project")
        self.assertTrue((root / "project.yaml").exists())
        self.assertIn("name: test-project", (root / "project.yaml").read_text(encoding="utf-8"))

    def test_projects_dir_override_controls_parent_folder(self) -> None:
        alternate = self.root / "chosen-projects"
        alternate.mkdir()

        root = self.create_project(["chosen", "folder"], projects_dir=str(alternate))

        self.assertEqual(root.parent, alternate)
        self.assertTrue((root / "project.yaml").exists())

    def test_python_venv_setup_records_runtime_and_creates_files(self) -> None:
        calls = []

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            if cmd[:3] == [sys.executable, "-m", "venv"]:
                (Path(cmd[3]) / "bin").mkdir(parents=True)
                (Path(cmd[3]) / "bin" / "python").write_text("", encoding="utf-8")
            return mock.Mock(returncode=0)

        with mock.patch.object(project.subprocess, "run", side_effect=fake_run):
            root = self.create_project("python-project", python=True, venv=True)

        project_yaml = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertTrue((root / "code").is_dir())
        self.assertTrue((root / "pyproject.toml").exists())
        self.assertTrue((root / ".venv").is_dir())
        self.assertIn("runtime:\n  python: true\n  venv: .venv", project_yaml)
        self.assertIn([sys.executable, "-m", "venv", str(root / ".venv")], calls)

    def test_use_project_records_typed_dependency_and_depends_on(self) -> None:
        dep = self.projects / "library-tool"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: library-tool\n", encoding="utf-8")
        (dep / "code").mkdir()

        root = self.create_project("uses-library", use_project=["project:library-tool:package:code"])

        project_yaml = (root / "project.yaml").read_text(encoding="utf-8")
        meta = project.parse_project_yaml(root / "project.yaml")
        self.assertNotIn("depends_on", project_yaml)
        project._relate_project_links.assert_called_with("uses-library", ["project:library-tool"], [])
        self.assertIn("project_dependencies:", project_yaml)
        self.assertEqual(meta["project_dependencies"][0]["project"], "library-tool")
        self.assertEqual(meta["project_dependencies"][0]["kind"], "package")
        self.assertEqual(meta["project_dependencies"][0]["path"], "code")

    def test_interactive_package_dependency_prompt_records_editable_install(self) -> None:
        dep = self.projects / "virtuallab"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: virtuallab\n", encoding="utf-8")
        (dep / "pyproject.toml").write_text("[project]\nname = \"virtuallab\"\n", encoding="utf-8")

        answers = ["y", "project:virtuallab", "y", "n"]
        with mock.patch("builtins.input", side_effect=answers):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                venv_enabled, dependencies = project.ask_project_dependencies(True, [])

        self.assertTrue(venv_enabled)
        self.assertEqual(dependencies, [{"project": "virtuallab", "kind": "package", "path": "."}])
        self.assertIn("Editable install command:", stdout.getvalue())
        self.assertIn(".venv/bin/python -m pip install -e", stdout.getvalue())

    def test_interactive_dependency_prompt_accepts_ref_as_implicit_yes(self) -> None:
        dep = self.projects / "virtuallab"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: virtuallab\n", encoding="utf-8")
        (dep / "pyproject.toml").write_text("[project]\nname = \"virtuallab\"\n", encoding="utf-8")

        answers = ["project:virtuallab", "y", "n"]
        with mock.patch("builtins.input", side_effect=answers):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                venv_enabled, dependencies = project.ask_project_dependencies(True, [])

        self.assertTrue(venv_enabled)
        self.assertEqual(dependencies, [{"project": "virtuallab", "kind": "package", "path": "."}])
        self.assertIn("Editable install command:", stdout.getvalue())

    def test_package_dependency_installs_editable_into_created_venv(self) -> None:
        dep = self.projects / "library-tool"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: library-tool\n", encoding="utf-8")
        (dep / "pyproject.toml").write_text("[project]\nname = \"library-tool\"\n", encoding="utf-8")
        calls = []

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            if cmd[:3] == [sys.executable, "-m", "venv"]:
                (Path(cmd[3]) / "bin").mkdir(parents=True)
                (Path(cmd[3]) / "bin" / "python").write_text("", encoding="utf-8")
            return mock.Mock(returncode=0)

        with mock.patch.object(project.subprocess, "run", side_effect=fake_run):
            root = self.create_project("uses-package", python=True, venv=True, use_project=["project:library-tool:package"])

        self.assertIn(
            [str(root / ".venv" / "bin" / "python"), "-m", "pip", "install", "-e", str(dep)],
            calls,
        )

    def test_resolve_project_name_accepts_capitalized_folders(self) -> None:
        legacy = self.projects / "Ferminet"
        legacy.mkdir()
        (legacy / "project.yaml").write_text("schema_version: 1\nname: ferminet\n", encoding="utf-8")

        self.assertEqual(project.resolve_project_name("Ferminet"), "Ferminet")
        self.assertEqual(project.resolve_project_name("ferminet"), "Ferminet")
        self.assertEqual(project.resolve_project_name(["ferminet"]), "Ferminet")
        with self.assertRaises(SystemExit):
            project.resolve_project_name("missing-project")

    def test_create_has_no_relation_flags(self) -> None:
        # Relations are created exclusively with `ws relate`; creation-time
        # edge flags were removed.
        root = self.create_project("plain")
        project_yaml = (root / "project.yaml").read_text(encoding="utf-8")
        self.assertNotIn("depends_on", project_yaml)
        self.assertNotIn("related:", project_yaml)
        project._relate_project_links.assert_not_called()

    def test_use_project_defaults_to_package_kind(self) -> None:
        dep = self.projects / "plainlib"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: plainlib\n", encoding="utf-8")
        parsed = project.parse_project_dependencies(["project:plainlib"])
        self.assertEqual(parsed, [{"project": "plainlib", "kind": "package", "path": "."}])

    def test_use_project_rejects_retired_kinds(self) -> None:
        dep = self.projects / "plainlib"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: plainlib\n", encoding="utf-8")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            project.parse_project_dependencies(["project:plainlib:knowledge"])
        self.assertIn("ws relate", err.getvalue())

    def test_use_project_resolves_capitalized_dependency_names(self) -> None:
        dep = self.projects / "CoolLib"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: coollib\n", encoding="utf-8")

        root = self.create_project("uses-coollib", use_project=["project:CoolLib:package"])

        meta = project.parse_project_yaml(root / "project.yaml")
        self.assertEqual(meta["project_dependencies"][0]["project"], "CoolLib")
        project._relate_project_links.assert_called_with("uses-coollib", ["project:CoolLib"], [])

    def test_custom_package_install_steps_replace_default(self) -> None:
        dep = self.projects / "special-lib"
        dep.mkdir()
        (dep / "project.yaml").write_text(
            'schema_version: 1\nname: special-lib\npackage_install:\n'
            '  - "{python} -m pip install custom-build-dep"\n'
            '  - "{python} -m pip install -e {path} --no-build-isolation"\n',
            encoding="utf-8",
        )
        (dep / "pyproject.toml").write_text("[project]\nname = \"special-lib\"\n", encoding="utf-8")
        calls = []

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            if cmd[:3] == [sys.executable, "-m", "venv"]:
                (Path(cmd[3]) / "bin").mkdir(parents=True)
                (Path(cmd[3]) / "bin" / "python").write_text("", encoding="utf-8")
            return mock.Mock(returncode=0)

        with mock.patch.object(project.subprocess, "run", side_effect=fake_run):
            root = self.create_project("uses-special", python=True, venv=True, use_project=["project:special-lib:package"])

        venv_py = str(root / ".venv" / "bin" / "python")
        self.assertIn([venv_py, "-m", "pip", "install", "custom-build-dep"], calls)
        self.assertIn([venv_py, "-m", "pip", "install", "-e", str(dep), "--no-build-isolation"], calls)
        self.assertNotIn([venv_py, "-m", "pip", "install", "-e", str(dep)], calls)

    def test_project_install_command_reruns_recorded_installs(self) -> None:
        dep = self.projects / "library-tool"
        dep.mkdir()
        (dep / "project.yaml").write_text("schema_version: 1\nname: library-tool\n", encoding="utf-8")
        (dep / "pyproject.toml").write_text("[project]\nname = \"library-tool\"\n", encoding="utf-8")

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            if cmd[:3] == [sys.executable, "-m", "venv"]:
                (Path(cmd[3]) / "bin").mkdir(parents=True)
                (Path(cmd[3]) / "bin" / "python").write_text("", encoding="utf-8")
            return mock.Mock(returncode=0)

        calls: list = []
        with mock.patch.object(project.subprocess, "run", side_effect=fake_run):
            root = self.create_project("reinstall-me", python=True, venv=True, use_project=["project:library-tool:package"])

        calls = []
        with mock.patch.object(project.subprocess, "run", side_effect=fake_run):
            with contextlib.redirect_stdout(io.StringIO()) as stdout:
                project.command_project_install(argparse.Namespace(name=["reinstall-me"], projects_dir=None))

        venv_py = str(root / ".venv" / "bin" / "python")
        self.assertIn([venv_py, "-m", "pip", "install", "-e", str(dep)], calls)
        self.assertIn("installed editable dependency: library-tool", stdout.getvalue())

    def test_find_enclosing_project_walks_up(self) -> None:
        root = self.projects / "deep-project"
        (root / "code" / "src").mkdir(parents=True)
        (root / "project.yaml").write_text("schema_version: 1\n", encoding="utf-8")

        self.assertEqual(project.find_enclosing_project(root / "code" / "src"), root.resolve())
        self.assertIsNone(project.find_enclosing_project(self.root))

    def test_resolve_project_name_rejects_ambiguous_input(self) -> None:
        for name in ["valley-studies", "Valley studies"]:
            path = self.projects / name
            path.mkdir()
            (path / "project.yaml").write_text("schema_version: 1\n", encoding="utf-8")

        self.assertEqual(project.resolve_project_name("Valley studies"), "Valley studies")
        self.assertEqual(project.resolve_project_name("valley-studies"), "valley-studies")
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stderr(io.StringIO()):
                project.resolve_project_name("valley studies")

    def test_taxonomy_problems_rejects_unknown_subfield_parent(self) -> None:
        problems = project.taxonomy_problems({
            "fields": ["physics"],
            "subfields": {"physics": ["spin-qubits"], "chemistry": ["spectroscopy"]},
        })
        self.assertEqual(
            problems,
            ["subfield group(s) have unknown parent fields: chemistry"],
        )


if __name__ == "__main__":
    unittest.main()
