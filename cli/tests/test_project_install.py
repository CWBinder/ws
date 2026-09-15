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
        self.patchers = [
            mock.patch.object(project, "PROJECTS", self.projects),
            mock.patch.object(project, "LITERATURE_ITEMS", self.root / "literature"),
            mock.patch.object(project, "PROJECT_TAXONOMY", self.root / "project-taxonomy.yaml"),
            mock.patch.object(project, "SLIDE_GENERATOR_PATH", self.slide_generator),
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
