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
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import setup


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

    def test_setup_prints_the_steps_for_an_agent_and_writes_nothing(self):
        first = self.run_ws("setup").stdout
        self.assertIn("Required and still missing: workspace, identity, person.", first)
        self.assertIn("Start with: ws setup --step brain", first)
        order = [line.split()[0] for line in first.split("THE STEPS, IN ORDER")[1].splitlines() if line.startswith("  ")]
        self.assertEqual(order, [
            "brain", "objects", "finding", "workspace", "projects", "literature", "documents", "resources",
            "tasks", "identity", "person", "people", "relations", "agent", "briefing", "end",
        ])
        idea = self.run_ws("setup", "--step", "brain").stdout
        self.assertIn("Andrej Karpathy", idea)
        self.assertIn("ws setup --step objects", idea)
        place = self.run_ws("setup", "--step", "workspace").stdout
        self.assertIn("ws init", place)
        self.assertIn("ws setup --step projects", place)
        self.assertFalse(self.root.exists())

        self.assertIn("ws setup", self.run_ws("init").stdout.splitlines()[-1])
        self.assertIn("Required and still missing: identity, person.", self.run_ws("setup").stdout)
        self.assertIn("already in place", self.run_ws("setup", "--step", "workspace").stdout)
        identity = self.run_ws("setup", "--step", "identity").stdout
        self.assertIn("ws create profile NAME --type identity", identity)
        self.assertIn("--headline HEADLINE", identity)
        self.assertNotIn("{today}", identity)
        self.assertNotIn("(default: )", identity)

        self.add_identity()
        self.assertIn("ws add person NAME --owner --ensure", self.run_ws("setup", "--step", "person").stdout)

        self.add_owner()
        before = self.snapshot(self.root)
        done = self.run_ws("setup")
        self.assertIn("everything left is optional", done.stdout)
        pages = {
            "projects": "ws projects add-field FIELD",
            "literature": "ws literature search-arxiv --author NAME",
            "documents": "ws add document PATH --mode copy",
            "resources": "ws create resource NAME",
            "tasks": "ws create task TITLE",
            "relations": "ws relate REF to REF as WORDS",
            "agent": "OpenClaw",
            "briefing": ".context/instructions.md",
        }
        for name, words in pages.items():
            page = self.run_ws("setup", "--step", name).stdout
            self.assertIn(words, page)
            for token in ("{fields}", "{project_types}", "{document_types}", "{root}"):
                self.assertNotIn(token, page)
        end = self.run_ws("setup", "--step", "end").stdout
        self.assertIn("dashboard.html", end)
        self.assertIn("ws context", end)
        self.assertIn("Change these with care", end)
        self.assertNotIn("{system}", end)
        self.assertNotIn("{ws}", end)
        self.assertIn("ws setup --step end", self.run_ws("setup", "--step", "briefing").stdout)
        self.assertIn("no setup step called 'nonsense'", self.run_ws("setup", "--step", "nonsense", success=False).stderr)
        self.assertEqual(self.run_ws("setup").stdout, done.stdout)
        self.assertEqual(self.snapshot(self.root), before)

    def test_setup_resumes_at_whatever_is_missing(self):
        self.run_ws("init")
        self.add_owner()
        self.assertIn("Required and still missing: identity", self.run_ws("setup").stdout)
        self.add_identity()
        data = json.loads(self.run_ws("setup", "--json").stdout)
        self.assertTrue(data["complete"])
        self.assertEqual(data["step"], "")
        self.run_ws("edit", "person:alex", "--no-owner")
        data = json.loads(self.run_ws("setup", "--json").stdout)
        self.assertEqual(data["step"], "person")
        self.assertFalse(data["complete"])

    def test_the_terminal_wizard_goes_through_everything_in_order(self):
        chosen = self.base / "chosen"
        self.env.pop("WS_WORKSPACE_ROOT")
        paper = self.base / "first notes.txt"
        paper.write_text("notes\n")
        answers = "\n".join([
            "", "", "",
            str(chosen),
            "biology", "biology/genomics, bad", "", "", "",
            "biology", "biology/genomics", "survey", "Gene study", "Find out about genes.",
            "",
            "reading-list", f"'{paper}'",
            "Delft claim",
            "", "2026-12-01",
            "Write the report", "2026-12-01",
            "Alex Example", "Physicist", "public@example.org", "+43 1 234", "", "https://a.example, https://b.example", "",
            "", "Alex", "private@example.org, other@example.org, PUBLIC@example.org", "431234, +44 20 999", "Does physics.",
            "Example Institute", "Sam Colleague",
            "1,2,5",
            "",
            "Write the thesis.", "Be brief.", "Long jobs run on a server.",
        ]) + "\n"
        out = self.run_ws("setup", "--interactive", stdin=answers).stdout
        for earlier, later in (
            ("A SECOND BRAIN", "OBJECTS AND RELATIONS"),
            ("OBJECTS AND RELATIONS", "FINDING THINGS"),
            ("FINDING THINGS", "THE WORKSPACE FOLDER"),
            ("THE WORKSPACE FOLDER", "\nPROJECTS\n"),
            ("\nPROJECTS\n", "\nDOCUMENTS\n"),
            ("\nTASKS\n", "YOUR PUBLIC IDENTITY"),
            ("YOUR PUBLIC IDENTITY", "YOUR PRIVATE DETAILS"),
            ("YOUR PRIVATE DETAILS", "YOUR FIRST RELATIONS"),
            ("YOUR FIRST RELATIONS", "MAKING IT YOUR AGENT"),
            ("MAKING IT YOUR AGENT", "Your first knowledge graph"),
            ("Your first knowledge graph", "What your agent reads"),
            ("What your agent reads", "Change these with care"),
        ):
            self.assertLess(out.index(earlier), out.index(later), f"{earlier} before {later}")
        self.assertIn("Part 2 of 3: what it holds", out)
        self.assertIn("That did not work: Write a subfield", out)
        self.assertIn("That did not work: Name the task that date belongs to", out)
        self.assertIn("1. You work on Gene study", out)
        self.assertIn("Delft claim supports Gene study", out)
        self.assertIn("Made 3 relation(s).", out)
        self.assertIn("owner: Alex Example", out)
        self.assertIn("WORKSPACE BRIEFING: the workspace root", out)
        self.assertIn("Be brief.", out)
        self.assertNotIn("TEST RUN", out)

        held = json.loads(self.run_ws("owner", "--json").stdout)
        self.assertEqual(held["person"], "person:alex-example")
        self.assertEqual(held["person_details"]["preferred_name"], "Alex")
        self.assertEqual(held["identity_details"]["links"], ["https://a.example", "https://b.example"])
        # What the identity already holds stays off the person.
        self.assertEqual(held["person_details"]["emails"], ["private@example.org", "other@example.org"])
        self.assertEqual(held["person_details"]["phones"], ["+44 20 999"])

        taxonomy = (chosen / "projects/project-taxonomy.yaml").read_text()
        for value in ("biology", "genomics", "survey"):
            self.assertIn(value, taxonomy)
        self.assertIn("reading-list", (chosen / "documents/document-taxonomy.yaml").read_text())
        self.assertEqual(
            (chosen / "projects/items/gene-study/.context/purpose.md").read_text(), "Find out about genes.\n"
        )
        self.assertEqual((chosen / ".context/purpose.md").read_text(), "Write the thesis.\n")
        self.assertEqual((chosen / ".context/instructions.md").read_text(), "Be brief.\n")
        self.assertEqual((chosen / ".context/whereami.md").read_text(), "Long jobs run on a server.\n")
        self.assertTrue(paper.is_file())
        self.assertIn("document:first-notes", self.run_ws("list", "documents").stdout)
        self.assertIn("task:write-the-report", self.run_ws("list", "tasks").stdout)

        edges = json.loads(self.run_ws("show", "person:alex-example", "--json").stdout)["relations"]
        self.assertEqual(
            {(edge["relation"], edge["other"]) for edge in edges},
            {("works-on", "project:gene-study"), ("works-at", "organisation:example-institute")},
        )
        edges = json.loads(self.run_ws("show", "resource:delft-claim", "--json").stdout)["relations"]
        self.assertEqual({(edge["relation"], edge["other"]) for edge in edges}, {("supports", "project:gene-study")})
        self.assertIn("person:sam-colleague", self.run_ws("list", "people").stdout)
        self.assertIn("--works-on--> Gene", out)
        self.assertTrue((chosen / "dashboard.html").is_file())

    def test_the_wizard_insists_on_what_is_required(self):
        self.run_ws("init")
        answers = "\n".join(["skip", "", "Alex", "", "", "", "", "", "", "", "", "", "", ""]) + "\n"
        out = self.run_ws("setup", "--interactive", stdin=answers).stdout
        self.assertIn("This one is needed.", out)
        self.assertIn("owner: Alex", out)
        self.assertNotIn("\nPROJECTS\n", out)

    def test_skipping_to_the_end_still_asks_what_is_required(self):
        out = self.run_ws("setup", "--interactive", stdin="skip\n\nAlex\n\n\n\n\n\n\n\n\n\n\n\n").stdout
        self.assertIn("THE WORKSPACE FOLDER", out)
        self.assertIn("YOUR PUBLIC IDENTITY", out)
        self.assertIn("YOUR PRIVATE DETAILS", out)
        self.assertNotIn("\nPROJECTS\n", out)
        self.assertNotIn("MAKING IT YOUR AGENT", out)
        self.assertIn("owner: Alex", out)

    def test_a_complete_workspace_is_not_asked_again_and_can_skip_to_the_end(self):
        self.run_ws("init")
        self.add_identity()
        self.add_owner()
        out = self.run_ws("setup", "--interactive", stdin="skip\n").stdout
        self.assertIn("A SECOND BRAIN", out)
        self.assertNotIn("THE WORKSPACE FOLDER", out)
        self.assertNotIn("YOUR PUBLIC IDENTITY", out)
        self.assertNotIn("\nPROJECTS\n", out)
        self.assertIn("owner: Alex", out)

    def test_the_steps_keep_notes_already_there_and_ask_nothing_needless(self):
        self.run_ws("init")
        self.add_identity()
        self.add_owner()
        (self.root / ".context").mkdir()
        (self.root / ".context/whereami.md").write_text("Mine.\n")
        answers = "\n".join([
            "", "", "",
            "", "", "", "", "",
            "",
            "", "",
            "",
            "", "",
            "", "",
            "",
            "", "", "Second.",
        ]) + "\n"
        out = self.run_ws("setup", "--interactive", stdin=answers).stdout
        self.assertNotIn("YOUR PAPERS", out)
        self.assertNotIn("YOUR FIRST RELATIONS", out)
        self.assertEqual((self.root / ".context/whereami.md").read_text(), "Mine.\n\nSecond.\n")

    def test_the_name_they_publish_under_becomes_the_first_guess_for_a_cv(self):
        known = {"owner": None, "root": str(self.root), "test": False, "name": ""}
        session = setup.Session()
        name = setup.STEPS["identity"].questions[0]
        self.assertEqual(session.default_of(name, known), "")
        with mock.patch.object(setup, "_ws", lambda *args: "[]"):
            session.submit(setup.STEPS["literature"], {"author": "Alex Example"}, known)
        self.assertEqual(session.default_of(name, known), "Alex Example")
        self.assertEqual(session.default_of(name, {**known, "name": "Held Already"}), "Held Already")

    def test_finding_papers_and_proposing_them_as_relations(self):
        known = {"owner": {"person": "person:alex"}, "root": str(self.root), "test": False}
        rows = [
            {"id": "2501.00001v1", "title": "First", "year": "2025", "authors": "Alex and B and C and D and E and F"},
            {"id": "2501.00002v1", "title": "Second", "year": "2024", "authors": "Alex"},
            {"id": "2501.00003v1", "title": "Third", "year": "2023", "authors": "Alex"},
        ]

        def fake_ws(*args):
            if args[:2] == ("literature", "search-arxiv"):
                return json.dumps(rows)
            if args[:2] == ("add", "literature") and args[2] == "2501.00001v1":
                return "folder: /x/literature/items/Alex2025First\ncitation: /x\n"
            if args[:2] == ("add", "literature") and args[2] == "2501.00002v1":
                raise setup.SetupError("arXiv record already exists in /x/literature/items/Alex2024Second")
            raise setup.SetupError("no network")

        session = setup.Session()
        with mock.patch.object(setup, "_ws", fake_ws):
            session.submit(setup.STEPS["literature"], {"author": "Alex"}, known)
            step = setup.STEPS["papers"]
            choices = session.choices(step, known)
            self.assertEqual(session.current({**known, "step": "", "fields": []}), setup.STEPS["brain"])
            self.assertEqual([choice["checked"] for choice in choices], [False, False, False])
            self.assertEqual(choices[0]["label"], "First (2025), Alex, B, C, D and 2 more")
            session.submit(step, {"chosen": ["2501.00001v1", "2501.00002v1", "2501.00003v1"]}, known)
        self.assertIn("Added 2", session.message)
        self.assertIn("2501.00003v1: no network", session.message)
        proposed = session.choices(setup.STEPS["relations"], known)
        self.assertEqual(
            [choice["id"] for choice in proposed],
            ["person:alex co-authored literature:Alex2025First", "person:alex co-authored literature:Alex2024Second"],
        )
        self.assertTrue(all(choice["checked"] for choice in proposed))

    def test_an_arxiv_search_that_finds_or_reaches_nothing_says_so(self):
        known = {"owner": None, "root": str(self.root), "test": False}
        session = setup.Session()
        with mock.patch.object(setup, "_ws", lambda *args: "[]"):
            session.submit(setup.STEPS["literature"], {"author": "Nobody"}, known)
        self.assertIn("no papers under Nobody", session.message)
        self.assertEqual(session.choices(setup.STEPS["papers"], known), [])

        def unreachable(*args):
            raise setup.SetupError("no network")

        with mock.patch.object(setup, "_ws", unreachable), self.assertRaises(setup.SetupError) as caught:
            setup.Session().submit(setup.STEPS["literature"], {"author": "Alex"}, known)
        self.assertIn("Could not search arXiv", str(caught.exception))

    def test_a_detail_on_both_owner_records_is_reported_and_the_person_still_matches(self):
        self.run_ws("init")
        self.run_ws("create", "profile", "Alex Example", "--type", "identity", "--email", "public@example.org", "--phone", "+43 1 234")
        self.add_owner()
        self.assertEqual(self.run_ws("check", "logistics").stdout.strip().splitlines()[-1], "ok: logistics")
        # An address held only on the identity still finds the owner's person.
        same = self.run_ws("add", "person", "Dr A. Example", "--ensure", "--non-interactive", "--email", "public@example.org")
        self.assertIn("exists: person:alex", same.stdout)
        self.run_ws("edit", "person:alex", "--add-email", "PUBLIC@example.org", "--add-phone", "431234")
        report = self.run_ws("check", "logistics")
        self.assertIn("PUBLIC@example.org is on both", report.stdout + report.stderr)
        self.assertIn("431234 is on both", report.stdout + report.stderr)

    def test_a_new_workspace_tells_any_agent_to_read_the_briefing(self):
        self.run_ws("init")
        self.assertIn("WORKSPACE BRIEFING", (self.root / "AGENTS.md").read_text())

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
            "", "", "",
            str(answered),
            "chemistry", "", "", "A project", "",
            "",
            "", "",
            "",
            "", "",
            "Robin Test", "", "robin@example.org", "", "", "", "",
            "", "", "", "", "",
            "An organisation", "",
            "",
            "",
            "Goals.", "Rules.", "A note.",
        ]) + "\n"
        out = self.run_ws("setup", "--test", "--interactive", stdin=answers).stdout
        self.assertIn("TEST RUN", out)
        self.assertIn("Part 1 of 3: the idea", out)
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
        for name in ("brain", "objects", "finding"):
            self.call(address, "/answer", {"step": name, "answers": {}})
        self.call(address, "/answer", {"step": "workspace", "answers": {"root": str(self.base / "must-not-exist")}})
        self.call(address, "/answer", {"step": "projects", "answers": {"fields": "chemistry", "project": "A project"}})
        self.call(address, "/skip", {"step": "literature"})
        self.call(address, "/end-tour", {"step": "documents"})
        self.call(address, "/answer", {"step": "identity", "answers": {"name": "Robin Test"}})
        done = self.call(address, "/answer", {"step": "person", "answers": {"name": "Robin Test"}})
        self.assertIn("owner: Robin Test", done["done"]["owner"])
        self.assertIn("WORKSPACE BRIEFING", done["done"]["briefing"])
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
        self.assertEqual(first["step"]["name"], "brain")
        self.assertEqual(first["step"]["questions"], [])
        self.assertTrue(first["step"]["optional"])
        self.assertEqual(first["step"]["position"], "Part 1 of 3: the idea")
        self.assertEqual(first["step"]["progress"], 0)
        self.assertEqual(self.call(address, "/answer", {"step": "brain", "answers": {}})["step"]["name"], "objects")
        self.assertEqual(self.call(address, "/answer", {"step": "objects", "answers": {}})["step"]["name"], "finding")
        place = self.call(address, "/answer", {"step": "finding", "answers": {}})
        self.assertEqual(place["step"]["name"], "workspace")
        self.assertFalse(place["step"]["optional"])
        projects = self.call(address, "/answer", {"step": "workspace", "answers": {}})
        self.assertEqual(projects["step"]["name"], "projects")
        self.assertIn("physics", projects["step"]["explain"])
        bad = self.call(address, "/answer", {"step": "projects", "answers": {"subfields": "bad"}})
        self.assertIn("field/subfield", bad["error"])
        self.assertEqual(bad["answers"], {"subfields": "bad"})
        self.call(address, "/answer", {"step": "projects", "answers": {"fields": "biology", "project": "Gene study"}})
        self.call(address, "/answer", {"step": "literature", "answers": {}})
        self.call(address, "/skip", {"step": "documents"})
        self.call(address, "/answer", {"step": "resources", "answers": {"resource": "Delft claim"}})
        identity = self.call(address, "/answer", {"step": "tasks", "answers": {}})
        self.assertEqual(identity["step"]["name"], "identity")
        self.assertFalse(identity["step"]["optional"])
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
        people = self.call(address, "/answer", {"step": "person", "answers": {"name": "Alex Example", "email": "p@example.org"}})
        self.assertEqual(people["step"]["name"], "people")
        relations = self.call(address, "/answer", {"step": "people", "answers": {"organisations": "Example Institute"}})
        self.assertEqual(relations["step"]["name"], "relations")
        self.assertEqual(
            [(choice["id"], choice["checked"]) for choice in relations["step"]["choices"]],
            [
                ("person:alex-example works-on project:gene-study", True),
                ("person:alex-example works-at organisation:example-institute", True),
                ("resource:delft-claim supports project:gene-study", False),
            ],
        )
        agent = self.call(address, "/answer", {"step": "relations", "answers": {"chosen": ["person:alex-example works-on project:gene-study"]}})
        self.assertEqual(agent["message"], "Made 1 relation(s).")
        self.assertEqual(agent["step"]["name"], "agent")
        self.assertIn("OpenClaw", agent["step"]["explain"])
        self.call(address, "/answer", {"step": "agent", "answers": {}})
        done = self.call(address, "/answer", {"step": "briefing", "answers": {"note": "A note.", "rules": "Be brief."}})
        self.assertIn("WORKSPACE BRIEFING: the workspace root", done["done"]["briefing"])
        self.assertIn("A note.", done["done"]["briefing"])
        self.assertIn("Be brief.", done["done"]["briefing"])
        self.assertIn("This is what comes out", done["done"]["reads"])
        self.assertIn("owner: Alex Example", done["done"]["owner"])
        self.assertEqual(done["done"]["over"], "")
        self.assertIn("  --works-on--> Gene Study", done["done"]["graph"])
        token = parse_qs(urlparse(address).query)["t"][0]
        base = address.split("/?")[0]
        self.assertIn("graph-card", urlopen(f"{base}/graph?t={token}", timeout=30).read().decode())
        with self.assertRaises(HTTPError):
            urlopen(f"{base}/graph", timeout=30)
        self.call(address, "/finish", {})
        self.assertEqual(server.wait(timeout=30), 0)
        self.assertIn("person: person:alex-example", self.run_ws("owner").stdout)
        self.assertIn("biology", (self.root / "projects/project-taxonomy.yaml").read_text())
        self.assertEqual((self.root / ".context/whereami.md").read_text(), "A note.\n")
        self.assertEqual((self.root / ".context/instructions.md").read_text(), "Be brief.\n")

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
