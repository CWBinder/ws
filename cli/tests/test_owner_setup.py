import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


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
        # Without a root, ws falls back to the home folder's workspace, and
        # that must never be the real one.
        self.home = self.base / "home"
        self.home.mkdir()
        self.env["HOME"] = str(self.home)

    def run_ws(self, *args, success=True, cwd=None, stdin=""):
        result = subprocess.run(
            [sys.executable, str(CLI), *args],
            env=self.env, cwd=cwd or self.base, text=True, capture_output=True, input=stdin,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def snapshot(self, folder):
        return {
            path: path.read_bytes() if path.is_file() else None
            for path in sorted(folder.rglob("*"))
        }

    def start_web(self, *flags):
        server = subprocess.Popen(
            [sys.executable, str(CLI), "setup", "--web", "--no-browser", *flags],
            env=self.env, cwd=self.base, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        self.addCleanup(server.stdout.close)
        self.addCleanup(server.kill)
        for line in server.stdout:
            if line.strip().startswith("http://"):
                return server, line.strip()
        self.fail("the setup server printed no address")

    def call(self, address, path, body=None):
        url = urlparse(address)
        request = Request(
            f"{url.scheme}://{url.netloc}{path}",
            data=None if body is None else json.dumps(body).encode(),
            headers={"X-Token": parse_qs(url.query)["t"][0], "Content-Type": "application/json"},
        )
        with urlopen(request, timeout=60) as response:
            return json.load(response)

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

    def test_setup_prints_each_step_for_an_agent_and_writes_nothing(self):
        first = self.run_ws("setup").stdout
        self.assertIn("step 1 of 3", first)
        self.assertIn("ws init", first)
        self.assertIn("What ws is", first)
        self.assertFalse(self.root.exists())

        self.assertIn("ws setup", self.run_ws("init").stdout.splitlines()[-1])
        second = self.run_ws("setup").stdout
        self.assertIn("step 2 of 3", second)
        self.assertIn("ws create profile NAME --type identity", second)
        self.assertIn("--headline HEADLINE", second)
        self.assertNotIn("{today}", second)

        self.add_identity()
        third = self.run_ws("setup").stdout
        self.assertIn("step 3 of 3", third)
        self.assertIn("ws add person NAME --owner --ensure", third)

        self.add_owner()
        before = self.snapshot(self.root)
        done = self.run_ws("setup")
        self.assertIn("WS SETUP: complete", done.stdout)
        self.assertNotIn("{system}", done.stdout)
        self.assertNotIn("{ws}", done.stdout)
        self.assertNotIn("What ws is", done.stdout)
        self.assertIn("ws projects add-field FIELD", done.stdout)
        self.assertIn(".context/whereami.md", done.stdout)
        self.assertEqual(self.run_ws("setup").stdout, done.stdout)
        self.assertEqual(self.snapshot(self.root), before)

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

    def test_the_terminal_wizard_asks_and_runs_the_commands(self):
        chosen = self.base / "chosen"
        self.env.pop("WS_WORKSPACE_ROOT")
        answers = "\n".join([
            str(chosen),
            "Alex Example", "Physicist", "public@example.org", "", "", "https://a.example, https://b.example", "",
            "", "Alex", "private@example.org, other@example.org", "", "Does physics.",
            "biology", "biology/genomics, bad",
            "biology", "biology/genomics",
            "Long jobs run on a server.",
        ]) + "\n"
        out = self.run_ws("setup", "--interactive", stdin=answers).stdout
        self.assertIn("Step 1 of 3", out)
        self.assertIn("Optional: your fields", out)
        self.assertIn("That did not work: Write a subfield", out)
        self.assertIn("owner: Alex Example", out)
        self.assertNotIn("TEST RUN", out)
        owner = json.loads(self.run_ws("owner", "--json").stdout)
        self.assertEqual(owner["person"], "person:alex-example")
        self.assertEqual(owner["person_details"]["emails"], ["private@example.org", "other@example.org"])
        self.assertEqual(owner["person_details"]["preferred_name"], "Alex")
        self.assertEqual(owner["identity_details"]["links"], ["https://a.example", "https://b.example"])
        taxonomy = (chosen / "projects/project-taxonomy.yaml").read_text()
        self.assertIn("biology", taxonomy)
        self.assertIn("genomics", taxonomy)
        self.assertEqual((chosen / ".context/whereami.md").read_text(), "Long jobs run on a server.\n")

    def test_the_wizard_insists_on_what_is_required_and_keeps_an_existing_note(self):
        self.run_ws("init")
        (self.root / ".context").mkdir()
        (self.root / ".context/whereami.md").write_text("Mine.\n")
        answers = "\n".join(["", "Alex", "", "", "", "", "", "", "", "", "", "", "", "", "", "Second.", ""]) + "\n"
        out = self.run_ws("setup", "--interactive", stdin=answers).stdout
        self.assertIn("This one is needed.", out)
        self.assertEqual((self.root / ".context/whereami.md").read_text(), "Mine.\n\nSecond.\n")

    def test_a_complete_workspace_only_gets_the_optional_steps(self):
        self.run_ws("init")
        self.add_identity()
        self.add_owner()
        out = self.run_ws("setup", "--interactive", stdin="\n\n\n").stdout
        self.assertNotIn("Step 1 of 3", out)
        self.assertNotIn("second brain", out)
        self.assertIn("Optional: your fields", out)
        self.assertIn("owner: Alex", out)

    def real_setup(self):
        """A workspace that must survive a test run, and a home to watch."""
        self.run_ws("init")
        self.add_identity()
        self.add_owner()
        temporary = self.base / "temporary"
        temporary.mkdir()
        self.env["TMPDIR"] = str(temporary)
        return temporary, self.snapshot(self.base)

    def test_a_terminal_test_run_changes_nothing_and_ignores_the_location(self):
        temporary, before = self.real_setup()
        answered = self.base / "must-not-exist"
        answers = "\n".join([
            str(answered),
            "Robin Test", "", "robin@example.org", "", "", "", "",
            "", "", "", "", "",
            "chemistry", "", "A note.",
        ]) + "\n"
        out = self.run_ws("setup", "--test", "--interactive", stdin=answers).stdout
        self.assertIn("TEST RUN", out)
        self.assertIn("Step 1 of 3", out)
        self.assertIn("[~/workspace]", out)
        self.assertIn("owner: Robin Test", out)
        self.assertIn("nothing was kept", out)
        self.assertFalse(answered.exists())
        self.assertEqual(list(temporary.iterdir()), [])
        self.assertEqual(self.snapshot(self.base), before)
        self.assertIn("owner: Alex\n", self.run_ws("owner").stdout)

    def test_a_browser_test_run_changes_nothing(self):
        temporary, before = self.real_setup()
        server, address = self.start_web("--test")
        self.assertTrue(self.call(address, "/state")["test"])
        self.call(address, "/answer", {"step": "workspace", "answers": {"root": str(self.base / "must-not-exist")}})
        self.call(address, "/answer", {"step": "identity", "answers": {"name": "Robin Test"}})
        self.call(address, "/answer", {"step": "person", "answers": {"name": "Robin Test"}})
        self.call(address, "/skip", {"step": "fields"})
        done = self.call(address, "/skip", {"step": "note"})
        self.assertIn("owner: Robin Test", done["done"]["owner"])
        self.assertIn("nothing was kept", done["done"]["over"])
        self.call(address, "/finish", {})
        self.assertEqual(server.wait(timeout=30), 0)
        self.assertEqual(list(temporary.iterdir()), [])
        self.assertEqual(self.snapshot(self.base), before)

    def test_a_test_run_needs_someone_to_answer(self):
        refused = self.run_ws("setup", "--test", success=False)
        self.assertIn("needs someone to answer", refused.stderr)
        self.assertFalse(self.root.exists())

    def test_the_browser_version_sets_up_for_real_and_reports_errors(self):
        server, address = self.start_web()
        first = self.call(address, "/state")
        self.assertFalse(first["test"])
        self.assertEqual(first["step"]["name"], "workspace")
        self.assertEqual(self.call(address, "/answer", {"step": "workspace", "answers": {}})["step"]["name"], "identity")
        missing = self.call(address, "/answer", {"step": "identity", "answers": {"name": " "}})
        self.assertIn("needed", missing["error"])
        self.assertEqual(missing["step"]["name"], "identity")
        person = self.call(address, "/answer", {
            "step": "identity", "answers": {"name": "Alex Example", "link": "https://a.example, https://b.example"},
        })
        self.assertEqual(person["step"]["name"], "person")
        name = next(question for question in person["step"]["questions"] if question["key"] == "name")
        self.assertEqual(name["default"], "Alex Example")
        # A step already answered, as from a double click, changes nothing.
        self.call(address, "/answer", {"step": "identity", "answers": {"name": "Someone Else"}})
        fields = self.call(address, "/answer", {"step": "person", "answers": {"name": "Alex Example", "email": "p@example.org"}})
        self.assertEqual(fields["step"]["name"], "fields")
        self.assertTrue(fields["step"]["optional"])
        bad = self.call(address, "/answer", {"step": "fields", "answers": {"subfields": "bad"}})
        self.assertIn("field/subfield", bad["error"])
        self.assertEqual(bad["answers"], {"subfields": "bad"})
        self.call(address, "/answer", {"step": "fields", "answers": {"fields": "biology"}})
        done = self.call(address, "/answer", {"step": "note", "answers": {"note": "A note."}})
        self.assertIn("owner: Alex Example", done["done"]["owner"])
        self.assertEqual(done["done"]["over"], "")
        self.call(address, "/finish", {})
        self.assertEqual(server.wait(timeout=30), 0)
        self.assertIn("person: person:alex-example", self.run_ws("owner").stdout)
        self.assertIn("biology", (self.root / "projects/project-taxonomy.yaml").read_text())
        self.assertEqual((self.root / ".context/whereami.md").read_text(), "A note.\n")

    def test_the_browser_version_answers_only_with_its_token_and_host(self):
        server, address = self.start_web()
        url = urlparse(address)
        base = f"{url.scheme}://{url.netloc}"
        token = parse_qs(url.query)["t"][0]
        for request in (
            Request(f"{base}/"),
            Request(f"{base}/?t=wrong"),
            Request(f"{base}/state"),
            Request(f"{base}/state", headers={"X-Token": "wrong"}),
            Request(f"{base}/state", headers={"X-Token": token, "Host": "evil.example"}),
            Request(f"{base}/answer", data=b"{}", headers={"Content-Type": "application/json"}),
            Request(f"{base}/finish", data=b"{}"),
        ):
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=30)
            self.assertEqual(caught.exception.code, 404)
        page = urlopen(address, timeout=30).read().decode()
        self.assertIn("<title>Set up ws</title>", page)
        self.assertEqual(url.hostname, "127.0.0.1")
        self.call(address, "/finish", {})
        self.assertEqual(server.wait(timeout=30), 0)

    def test_the_shipped_subfields_are_generic(self):
        self.run_ws("init")
        taxonomy = (self.root / "projects/project-taxonomy.yaml").read_text()
        for personal in ("spin-qubits", "shuttling", "quantum-chemistry", "quantum-computing"):
            self.assertNotIn(personal, taxonomy)

    def test_setup_is_a_registered_command_with_a_manual_page(self):
        self.assertIn("Setting up", self.run_ws("help", "setup").stdout)
        self.assertIn("The owner", self.run_ws("help", "owner").stdout)
        self.run_ws("check", "cli")


if __name__ == "__main__":
    unittest.main()
