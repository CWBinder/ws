import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CLI = Path(__file__).resolve().parents[1] / "ws"


class OwnerAndSetupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / "workspace"
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("WS_")}
        self.env["WS_CONFIG"] = str(self.base / "config.yaml")
        self.env["WS_WORKSPACE_ROOT"] = str(self.root)

    def run_ws(self, *args, success=True, cwd=None):
        result = subprocess.run(
            [sys.executable, str(CLI), *args],
            env=self.env, cwd=cwd or self.base, text=True, capture_output=True,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def add_identity(self):
        self.run_ws("create", "profile", "Alex Example", "--type", "identity", "--email", "public@example.org")

    def add_owner(self, name="Alex"):
        self.run_ws("add", "person", name, "--owner", "--email", "private@example.org", "--non-interactive")

    def test_owner_is_silent_until_a_record_exists(self):
        self.run_ws("init")
        result = self.run_ws("owner")
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertIsNone(json.loads(self.run_ws("owner", "--json").stdout))

    def test_owner_also_works_before_the_workspace_exists(self):
        self.assertEqual(self.run_ws("owner").stdout, "")

    def test_owner_prints_each_record_it_finds_and_prefers_the_persons_name(self):
        self.run_ws("init")
        self.add_identity()
        text = self.run_ws("owner").stdout
        self.assertIn("owner: Alex Example", text)
        self.assertIn("identity: profile:alex-example", text)
        self.assertNotIn("person:", text)
        self.add_owner()
        text = self.run_ws("owner").stdout
        self.assertIn("owner: Alex\n", text)
        self.assertIn("person: person:alex", text)
        self.assertIn("private@example.org", text)
        self.assertIn("public@example.org", text)
        self.assertNotIn("provenance", text)
        data = json.loads(self.run_ws("owner", "--json").stdout)
        self.assertEqual(data["person"], "person:alex")
        self.assertEqual(data["person_details"]["emails"], ["private@example.org"])
        self.assertEqual(data["identity_details"]["emails"], ["public@example.org"])

    def test_a_second_owner_is_refused_until_the_first_is_cleared(self):
        self.run_ws("init")
        self.add_owner()
        self.run_ws("add", "person", "Sam", "--non-interactive")
        refused = self.run_ws("add", "person", "Robin", "--owner", "--non-interactive", success=False)
        self.assertIn("person:alex is already the owner", refused.stderr)
        self.assertEqual(len(json.loads(self.run_ws("list", "people", "--json").stdout)), 2)
        self.run_ws("edit", "person:sam", "--owner", success=False)
        self.run_ws("edit", "person:alex", "--owner")
        self.run_ws("edit", "person:alex", "--no-owner")
        self.assertNotIn("owner", (self.root / "logistics/people/alex.yaml").read_text())
        self.run_ws("edit", "person:sam", "--owner")
        self.assertIn("person:sam", self.run_ws("owner").stdout)

    def test_check_reports_a_second_owner_written_by_hand(self):
        self.run_ws("init")
        self.add_owner()
        self.run_ws("add", "person", "Sam", "--non-interactive")
        record = self.root / "logistics/people/sam.yaml"
        record.write_text(record.read_text() + "owner: true\n")
        report = self.run_ws("check", "logistics", success=False)
        self.assertIn("at most one person may be the owner", report.stdout + report.stderr)

    def test_merging_an_owner_carries_the_label(self):
        self.run_ws("init")
        self.add_owner()
        self.run_ws("add", "person", "Alex Example", "--non-interactive")
        self.run_ws("logistics", "people", "merge", "person:alex", "--into", "person:alex-example")
        self.assertIn("person: person:alex-example", self.run_ws("owner").stdout)

    def test_the_briefing_names_the_owner_from_the_records(self):
        self.run_ws("init")
        self.assertNotIn("[workspace · owner]", self.run_ws("context", cwd=self.root).stdout)
        self.add_owner()
        self.assertIn(
            "This is the workspace of Alex. For their details: ws owner",
            self.run_ws("context", cwd=self.root).stdout,
        )

    def test_setup_walks_the_steps_from_the_state_of_the_workspace(self):
        first = self.run_ws("setup").stdout
        self.assertIn("step 1 of 3", first)
        self.assertIn("ws init", first)
        self.assertIn("What ws is", first)
        self.assertFalse(self.root.exists())

        self.assertIn("ws setup", self.run_ws("init").stdout.splitlines()[-1])
        second = self.run_ws("setup").stdout
        self.assertIn("step 2 of 3", second)
        self.assertIn("--type identity", second)
        self.assertNotIn("{today}", second)

        self.add_identity()
        third = self.run_ws("setup").stdout
        self.assertIn("step 3 of 3", third)
        self.assertIn("--owner", third)

        self.add_owner()
        done = self.run_ws("setup")
        self.assertIn("WS SETUP: complete", done.stdout)
        self.assertNotIn("{system}", done.stdout)
        self.assertNotIn("What ws is", done.stdout)
        self.assertEqual(self.run_ws("setup").stdout, done.stdout)

    def test_setup_resumes_at_whatever_is_missing(self):
        self.run_ws("init")
        self.add_owner()
        self.assertIn("step 2 of 3", self.run_ws("setup").stdout)
        self.add_identity()
        data = json.loads(self.run_ws("setup", "--json").stdout)
        self.assertTrue(data["complete"])
        self.assertEqual(data["step"], "")
        self.run_ws("edit", "person:alex", "--no-owner")
        data = json.loads(self.run_ws("setup", "--json").stdout)
        self.assertEqual(data["step"], "person")
        self.assertFalse(data["complete"])

    def test_setup_changes_nothing(self):
        self.run_ws("init")
        before = sorted(str(path) for path in self.root.rglob("*"))
        self.run_ws("setup")
        self.assertEqual(sorted(str(path) for path in self.root.rglob("*")), before)


if __name__ == "__main__":
    unittest.main()
