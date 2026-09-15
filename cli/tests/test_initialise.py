import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "ws"


class InitialiseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / "workspace with spaces"
        self.config = self.base / "config.yaml"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("WS_")}
        self.env["WS_CONFIG"] = str(self.config)

    def run_ws(self, *args, success=True, env=None):
        result = subprocess.run([sys.executable, str(CLI), *args],
                                env=env or self.env, cwd=self.base,
                                text=True, capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_fresh_init_remembers_root_and_preserves_personal_files(self):
        self.config.write_text('# kept comment\nother: "leave this alone"\n')
        self.run_ws("init", "--root", str(self.root))
        self.assertIn(str(self.root), self.config.read_text())
        self.assertIn('# kept comment\nother: "leave this alone"', self.config.read_text())
        report = json.loads(self.run_ws("check", "--json").stdout)
        self.assertTrue(report["ok"])
        self.assertFalse((self.root / ".git").exists())
        self.assertEqual(list((self.root / "documents/items").iterdir()), [])
        self.run_ws("create", "project", "example", "--type", "other", "--non-interactive")
        project = self.root / "projects/items/example"
        self.assertTrue((project / "project.yaml").exists())
        self.assertNotIn("<ws-root>", (project / "AGENTS.md").read_text())
        (self.root / "AGENTS.md").write_text("My own rules.\n")
        (self.root / "README.md").write_text("My own overview.\n")
        taxonomy = self.root / "projects/project-taxonomy.yaml"
        taxonomy.write_text(taxonomy.read_text() + "\n# personal annotation\n")
        snapshot = {p: p.read_bytes() for p in [self.config, self.root / "AGENTS.md",
                                             self.root / "README.md", taxonomy,
                                             project / "project.yaml"]}
        self.run_ws("init")
        self.assertEqual(snapshot, {p: p.read_bytes() for p in snapshot})

    def test_environment_override_and_explicit_root_precedence(self):
        self.run_ws("init", "--root", str(self.root))
        other = self.base / "other"
        env = {**self.env, "WS_WORKSPACE_ROOT": str(other)}
        self.run_ws("init", env=env)
        self.assertTrue((other / "README.md").exists())
        chosen = self.base / "chosen"
        self.run_ws("init", "--root", str(chosen), env=env)
        self.assertIn(str(chosen), self.config.read_text())
        self.run_ws("create", "task", "saved-root-task")
        self.assertTrue(any((chosen / "tasks").glob("*.yaml")))
        self.assertFalse(any((other / "tasks").glob("*.yaml")))

    def test_conflicting_layout_is_refused_before_writing(self):
        self.root.mkdir()
        (self.root / "documents").write_text("keep me")
        result = self.run_ws("init", "--root", str(self.root), success=False)
        self.assertIn("expected a real directory", result.stderr)
        self.assertEqual((self.root / "documents").read_text(), "keep me")
        self.assertFalse((self.root / "projects").exists())
        self.assertFalse(self.config.exists())

    def test_symlinked_store_does_not_import_external_content(self):
        self.root.mkdir()
        outside = self.base / "outside"
        outside.mkdir()
        (self.root / "documents").symlink_to(outside, target_is_directory=True)
        self.run_ws("init", "--root", str(self.root), success=False)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertFalse(self.config.exists())

    def test_refuses_workspace_inside_code_checkout(self):
        self.run_ws("init", "--root", str(CLI.parent.parent / "workspace"), success=False)
        self.assertFalse(self.config.exists())


if __name__ == "__main__":
    unittest.main()
