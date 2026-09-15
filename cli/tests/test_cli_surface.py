import argparse
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import unittest
from unittest import mock
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import catalog, registry


def load_ws_module():
    path = Path(__file__).resolve().parents[1] / "ws"
    loader = importlib.machinery.SourceFileLoader("ws_cli", str(path))
    spec = importlib.util.spec_from_loader("ws_cli", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


ws_cli = load_ws_module()


def subcommands(parser: argparse.ArgumentParser) -> dict:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


class CliSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = ws_cli.build_parser()
        cls.top = subcommands(cls.parser)

    def parse(self, *parts):
        return self.parser.parse_args(list(parts))

    def test_canonical_domains_are_registered(self):
        self.assertTrue(
            {
                "projects", "tasks", "literature",
                "documents", "resources", "logistics", "profile",
            }.issubset(self.top)
        )

    def test_canonical_global_namespaces_are_registered(self):
        self.assertTrue(
            {
                "relations", "search", "check", "wiki",
                "completions",
            }.issubset(self.top)
        )

    def test_verb_semantics(self):
        # One spelling per command: the generic verbs live only at the top,
        # the domains keep their specialists.
        create_kinds = subcommands(self.top["create"])
        self.assertTrue({"project", "subproject", "task", "resource", "profile"}.issubset(create_kinds))
        add_kinds = subcommands(self.top["add"])
        self.assertTrue({"person", "organisation", "event", "document", "literature", "resource"}.issubset(add_kinds))
        for domain, generics in {
            "projects": ("create", "list", "show"),
            "tasks": ("create", "list", "search", "show", "edit", "delete"),
            "documents": ("add", "list", "search", "show", "edit", "delete"),
            "resources": ("create", "add", "list", "search", "show", "edit", "delete"),
            "literature": ("add", "show", "edit", "search"),
            "profile": ("create", "list", "show", "edit", "delete"),
        }.items():
            actions = subcommands(self.top[domain])
            for generic in generics:
                with self.subTest(domain=domain, generic=generic):
                    self.assertNotIn(generic, actions)
        self.assertIn("ensure", subcommands(self.top["tasks"]))
        logistics = subcommands(self.top["logistics"])
        for plural in ("people", "organisations", "events"):
            with self.subTest(plural=plural):
                actions = subcommands(logistics[plural])
                self.assertEqual(set(actions), {"ensure", "merge"})
        # The bare kind words are no longer top-level commands.
        for gone in ("people", "organizations", "events", "person", "task", "career"):
            self.assertNotIn(gone, self.top)

    def test_document_add_moves_into_workspace_by_default(self):
        args = self.parse("add", "document", "/tmp/example.pdf")
        self.assertEqual(args.mode, "move")

    def test_add_commands_expose_idempotent_ensure(self):
        ensured = self.parse("add", "person", "Maria Schwarz", "--ensure")
        self.assertTrue(ensured.ensure)
        self.assertIs(ensured.func, catalog.command_create)
        plain = self.parse("add", "event", "Conference")
        self.assertFalse(plain.ensure)
        document_add = self.parse("add", "document", "/tmp/example.pdf", "--ensure")
        self.assertTrue(document_add.ensure)
        standalone = self.parse("logistics", "people", "ensure", "Maria Schwarz")
        self.assertIs(standalone.func, catalog.command_ensure)

    def test_search_accepts_unquoted_words_with_kind_scope_first(self):
        args = self.parse("search", "organizations", "Quantum", "Motion")
        self.assertEqual(args.query, ["organizations", "Quantum", "Motion"])

    def test_describe_exposes_contract_and_effects(self):
        args = self.parse(
            "describe", "add", "document", "--json"
        )
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        record = json.loads(buffer.getvalue())
        self.assertEqual(record["kind"], "domain")
        self.assertEqual(record["contract"], "contracts/documents.md")
        self.assertTrue(record["effects"]["writes"])
        # Creation never touches the relation store: edges come from `ws relate`.
        self.assertFalse(record["effects"]["relations"])

    def test_add_resource_is_the_hoisted_file_ingest(self):
        hoisted = self.parse("add", "resource", "resource:exampleco-travel", "receipt.pdf")
        self.assertEqual(hoisted.resource, "resource:exampleco-travel")
        self.assertEqual(hoisted.mode, "move")
        # The sentence form: a REF right after `add` targets that object.
        sentence = catalog.expand_add_target(["add", "resource:exampleco-travel", "receipt.pdf"])
        self.assertEqual(sentence, ["add", "resource", "resource:exampleco-travel", "receipt.pdf"])
        parsed = self.parse(*sentence)
        self.assertIs(parsed.func, hoisted.func)
        # Kind words and other tools pass through untouched.
        self.assertEqual(
            catalog.expand_add_target(["add", "document", "receipt.pdf"]),
            ["add", "document", "receipt.pdf"],
        )
        self.assertEqual(
            catalog.expand_add_target(["show", "resource:exampleco-travel"]),
            ["show", "resource:exampleco-travel"],
        )

    def test_capabilities_lists_hoisted_canon_once(self):
        def listing(*extra):
            args = self.parse("capabilities", *extra)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                args.func(args)
            rows = buffer.getvalue().splitlines()
            # Category headings frame the listing; the commands are the rest.
            return [row for row in rows if row.startswith("ws ")]

        default = listing()
        # The universal grammar leads, one row per command.
        self.assertEqual(default[0], "ws create project")
        self.assertIn("ws add document", default)
        self.assertIn("ws show", default)
        self.assertIn("ws list tasks", default)
        self.assertEqual(len(default), len(set(default)))
        # The old domain spellings are gone from the parser itself.
        for gone in (
            "ws documents add",
            "ws tasks create",
            "ws literature show",
            "ws people merge",
            "ws organizations edit",
            "ws add people",
            "ws create tasks",
            "ws resources add",
            "ws relations show",
        ):
            self.assertNotIn(gone, default)
        # Domain specialists and home spellings stay.
        self.assertIn("ws add resource", default)
        self.assertIn("ws logistics people merge", default)
        self.assertIn("ws literature enrich", default)
        everything = listing("--all")
        self.assertNotIn("ws documents add", everything)

    def test_help_and_describe_meet_the_content_rules(self):
        # contracts/cli.md, Help and describe content rules. The check is the
        # enforcement; this test keeps the enforcement itself honest.
        from ws_lib import registry

        self.assertEqual(registry.cli_findings(self.parser), [])

    def test_describe_answers_what_not_how(self):
        from ws_lib import registry

        record = registry.command_record(self.parser, ["relate"])
        # What and why: purpose, contract, effects. Never the flag list.
        self.assertTrue(record["purpose"])
        self.assertEqual(record["contract"], "contracts/relations.md")
        self.assertTrue(record["effects"]["writes"])
        self.assertNotIn("options", record)
        # A leaf answers for itself rather than borrowing the domain's purpose.
        leaf = registry.command_record(self.parser, ["documents", "taxonomy"])
        domain = registry.command_record(self.parser, ["documents"])
        self.assertTrue(leaf["purpose"])
        self.assertNotEqual(leaf["purpose"], domain["purpose"])

    def test_overview_is_one_text_everywhere(self):
        from ws_lib import registry

        def rendered(function, *args):
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                function(*args)
            return buffer.getvalue()

        bare_ws = rendered(ws_cli.command_help, argparse.Namespace())
        bare_help = rendered(
            registry.command_help, argparse.Namespace(path=[], root_parser=self.parser)
        )
        self.assertEqual(bare_ws, bare_help)
        # The overview is a map: four sections, no tutorial prose.
        for fragment in (
            "What you can do",
            "What the workspace holds",
            "Grammar",
            "Finding your way",
        ):
            self.assertIn(fragment, bare_ws)

    def test_capabilities_scopes_to_a_kind(self):
        def listing(*extra):
            args = self.parse("capabilities", *extra)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                args.func(args)
            return buffer.getvalue().splitlines()

        documents = listing("documents")
        self.assertIn("ws add document", documents)
        self.assertIn("ws show document:<key>", documents)
        self.assertIn("ws documents taxonomy", documents)
        self.assertNotIn("ws create document", " ".join(documents))
        # The hand-curated kinds keep their limits.
        projects = listing("projects")
        self.assertIn("ws create project", projects)
        self.assertIn("ws projects install", projects)
        self.assertNotIn("ws edit project:<key>", projects)
        self.assertNotIn("ws delete project:<key>", projects)
        self.assertNotIn("ws delete literature:<key>", listing("literature"))
        # Kind words scope regardless of grammatical number, singular or plural.
        self.assertEqual(listing("person"), listing("people"))
        # A kind's home specialists ride along.
        self.assertIn("ws logistics people merge", listing("person"))
        self.assertIn("ws tasks ensure", listing("tasks"))
        self.assertIn("ws add resource:<key> <path>", listing("resource"))
        # JSON returns records with contracts, like the global listing.
        args = self.parse("capabilities", "tasks", "--json")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        records = json.loads(buffer.getvalue())
        self.assertEqual(records[0]["command"], "ws create task")
        self.assertTrue(all(record["contract"] for record in records))

    def test_misplaced_flags_are_told_the_house_rule(self):
        # argparse reports these as `unrecognized arguments` / `invalid
        # choice`; neither names the real mistake.
        for argv in (
            ["list", "--type", "abstract", "documents"],
            ["search", "documents", "--type", "abstract", "siqew"],
            ["edit", "--name", "X", "document:foo"],
        ):
            with self.subTest(argv=argv):
                self.assertTrue(registry._flag_precedes_a_bare_word(argv))
        # Correct orderings, and a plain typo, must not trip the detector.
        for argv in (
            ["search", "documents", "siqew", "--type", "abstract"],
            ["list", "documents", "--type", "abstract"],
            ["show", "document:a", "document:b", "--json"],
            ["list", "documentz"],
        ):
            with self.subTest(argv=argv):
                self.assertFalse(registry._flag_precedes_a_bare_word(argv))

    def test_flags_last_is_enforced_without_exception(self):
        def check(argv):
            buffer = io.StringIO()
            with contextlib.redirect_stderr(buffer):
                registry.enforce_flags_last(
                    self.parser, catalog.expand_add_target(list(argv))
                )
            return buffer.getvalue()

        # House style parses; every one of these must survive untouched.
        for argv in (
            ["search", "documents", "siqew", "--type", "abstract"],
            ["search", "documents", "siqew", "--type=abstract"],
            ["list", "documents", "--type", "abstract", "--limit", "5"],
            ["show", "document:a", "document:b", "--json"],
            ["add", "document", "/tmp/x.pdf", "--name", "R", "--ensure"],
            ["create", "task", "Write", "the", "paper", "--due", "2026-09-01"],
            ["relate", "person:a", "to", "organisation:b", "as", "works-at"],
            ["edit", "document:foo", "--name", "Report"],
            ["add", "resource:exampleco", "receipt.pdf", "--mode", "copy"],
        ):
            with self.subTest(argv=argv):
                self.assertEqual(check(argv), "")

        # A flag before an operand is refused even where argparse would
        # have accepted it -- one rule, no exceptions.
        for argv, offender in (
            (["add", "document", "--name", "R", "/tmp/x.pdf"], "/tmp/x.pdf"),
            (["show", "--json", "document:a"], "document:a"),
            (["list", "--type", "abstract", "documents"], "documents"),
            (["create", "task", "--due", "2026-09-01", "Write"], "Write"),
        ):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                message = check(argv)
                self.assertIn("flags come last", message)
                self.assertIn(offender, message)
                # The refusal hands over a runnable command.
                self.assertIn("try: ws", message)

    def test_every_global_command_has_exactly_one_category(self):
        # contracts/cli.md: an uncategorised command is a defect in the
        # model, so the whole canonical surface must classify.
        paths = registry._canonical_capability_paths(self.parser)
        for words in paths:
            category = registry.command_category(words)
            self.assertTrue(category, f"uncategorised: ws {' '.join(words)}")
            self.assertIn(category, {*registry.CATEGORIES, *registry.DOMAINS})
        # The five categories are each non-empty, and the verbs land where
        # the contract says: CRUD under objects, collection queries under
        # search.
        by_category = {}
        for words in paths:
            by_category.setdefault(registry.command_category(words), []).append(words)
        for name in registry.CATEGORIES:
            self.assertTrue(by_category.get(name), f"empty category: {name}")
        self.assertEqual(registry.command_category(["show"]), "objects")
        self.assertEqual(registry.command_category(["delete"]), "objects")
        self.assertEqual(registry.command_category(["relate"]), "objects")
        self.assertEqual(registry.command_category(["list", "tasks"]), "search")
        self.assertEqual(registry.command_category(["search"]), "search")
        self.assertEqual(registry.command_category(["id", "resolve"]), "search")
        self.assertEqual(registry.command_category(["index", "rebuild"]), "maintenance")
        self.assertEqual(registry.command_category(["check"]), "maintenance")
        self.assertEqual(registry.command_category(["describe"]), "discovery")
        self.assertEqual(registry.command_category(["literature", "enrich"]), "literature")

    def test_capabilities_groups_by_category_and_scopes_to_one(self):
        def listing(*extra):
            args = self.parse("capabilities", *extra)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                args.func(args)
            return buffer.getvalue()

        grouped = listing()
        # Every category is a heading, in the model's order, and the domains
        # follow.
        headings = [
            line[2:].split(" — ")[0]
            for line in grouped.splitlines()
            if line.startswith("# ")
        ]
        self.assertEqual(headings[:len(registry.CATEGORIES)], list(registry.CATEGORIES))
        self.assertNotIn("uncategorised", " ".join(headings))
        for domain in registry.DOMAINS:
            self.assertIn(domain, headings)
        # A category word scopes the listing to exactly its own rows.
        maintenance = [
            line for line in listing("maintenance").splitlines() if line.strip()
        ]
        self.assertEqual(
            set(maintenance),
            {"ws init", "ws check", "ws index rebuild", "ws index stat", "ws wiki build"},
        )
        # Kind scoping still works and is not confused by category words.
        self.assertIn("ws documents taxonomy", listing("documents"))
        # Records carry the category, so the JSON surface classifies too.
        args = self.parse("capabilities", "--json")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        records = json.loads(buffer.getvalue())
        self.assertTrue(all(record["category"] for record in records))

    def test_vocabulary_listings_name_what_the_workspace_holds(self):
        def listing(command):
            args = self.parse(command)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                args.func(args)
            return buffer.getvalue()

        # Domains keep their own listing; the retired tools/services
        # listings are gone rather than renamed onto colliding words.
        self.assertTrue(listing("domains").strip())
        self.assertNotIn("tools", self.top)
        self.assertNotIn("services", self.top)
        # Each line is one line.
        domains = listing("domains")
        self.assertTrue(all(len(line.splitlines()) == 1 for line in domains.splitlines()))
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            registry.print_overview()
        overview = buffer.getvalue()
        # The overview teaches both axes: the categories, then what is held.
        for category in registry.CATEGORIES:
            self.assertIn(category, overview)
        for command in ("ws domains", "ws relations"):
            self.assertIn(command, overview)

    def test_relations_is_its_own_layer_not_a_derived_one(self):
        # A maintenance target holds only what can be rebuilt; a
        # hand-asserted edge exists nowhere else, so relations keeps its own
        # layer even though its commands file under the objects category.
        self.assertNotIn("relations", registry.GLOBAL_NAMESPACES)
        self.assertNotIn("relations", registry.DOMAINS)
        self.assertIn("relations", registry.GRAPH)
        self.assertEqual(registry.GRAPH["relations"].kind, "graph")
        self.assertEqual(registry.command_category(["relations"]), "objects")
        # It still resolves to its contract through describe.
        record = registry.command_record(self.parser, ["relations"])
        self.assertEqual(record["contract"], "contracts/relations.md")
        # Bare `ws relations` runs, and its subcommands survive.
        self.assertIsNotNone(self.top["relations"].get_default("func"))
        self.assertEqual(set(subcommands(self.top["relations"])), {"edit"})

    def test_capabilities_lists_runnable_parent_commands(self):
        args = self.parse("capabilities")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        rows = buffer.getvalue().splitlines()
        # `ws list` and `ws relations` do something on their own, so they are
        # commands rather than mere headings.
        self.assertIn("ws list", rows)
        self.assertIn("ws relations", rows)
        self.assertIn("ws list tasks", rows)

    def test_completion_drift_is_reported_by_check(self):
        import tempfile
        generated = {"zsh": "#compdef ws\ncurrent\n", "bash": "current\n"}
        with tempfile.TemporaryDirectory() as tmp:
            installed = Path(tmp) / "_ws"
            with mock.patch.dict(
                registry.INSTALLED_COMPLETIONS, {"zsh": installed, "bash": Path(tmp) / "absent"}
            ):
                # Nothing installed is not a finding: completions are optional.
                self.assertEqual(registry.completion_findings(generated), [])
                installed.write_text(generated["zsh"], encoding="utf-8")
                self.assertEqual(registry.completion_findings(generated), [])
                # A file left behind by an older grammar is.
                installed.write_text("#compdef ws\nstale\n", encoding="utf-8")
                rows = registry.completion_findings(generated)
                self.assertEqual(len(rows), 1)
                self.assertIn("stale", rows[0]["message"])
                self.assertIn("ws completions zsh", rows[0]["message"])

    def test_dead_migrations_are_gone(self):
        # Both had migrated everything they were written for.
        self.assertNotIn("refs", self.top)
        self.assertNotIn("migrate", subcommands(self.top["relations"]))
        self.assertFalse(hasattr(catalog, "migrate_refs"))
        # Building the wiki has one spelling.
        self.assertEqual(set(subcommands(self.top["wiki"])), {"build"})

    def test_overview_teaches_the_flag_rule(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            registry.print_overview()
        self.assertIn("Flags come last", buffer.getvalue())

    def test_overview_maps_every_category_and_listing(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            ws_cli.command_help(argparse.Namespace())
        text = buffer.getvalue()
        # Every category is named, and every command the map claims for one
        # is a real top-level command.
        for category, commands in registry.OVERVIEW_CATEGORY_COMMANDS.items():
            self.assertIn(category, text)
            for command in commands:
                self.assertIn(command, self.top)
                self.assertEqual(registry.command_category([command]), category)
        # Both listings are named and pointed at.
        for domain in registry.DOMAINS:
            self.assertIn(domain, text)
        for pointer in ("ws domains", "ws relations"):
            self.assertIn(pointer, text)
        # The discovery surfaces are the way onward.
        for command, _ in registry.OVERVIEW_DISCOVERY:
            self.assertIn(command, text)

    def test_overview_examples_are_runnable_commands(self):
        # The map's examples are the only hand-written spellings left in it,
        # so they are the one place that can drift from the parser.
        for _, _, example in registry.OVERVIEW_GRAMMAR:
            words = example.split()
            self.assertEqual(words[0], "ws")
            resolved = 0
            for length in range(1, len(words)):
                if registry.resolve_parser(self.parser, tuple(words[1 : length + 1])):
                    resolved = length
                else:
                    break
            self.assertTrue(resolved, f"unrunnable example: {example}")

    def test_overview_reads_no_workspace_state(self):
        # A map must print identically in a broken or absent workspace, so
        # the live edge count stays with `ws relations`.
        from ws_lib import relations

        def explode(*_args, **_kwargs):
            raise AssertionError("print_overview must not read the workspace")

        buffer = io.StringIO()
        with mock.patch.object(relations, "load_all", explode):
            with contextlib.redirect_stdout(buffer):
                registry.print_overview()
        self.assertIn("ws relations", buffer.getvalue())

    def test_completion_scripts_include_canonical_roots(self):
        scripts = ws_cli.bash_completion_script() + ws_cli.zsh_completion_script()
        self.assertIn("__complete-path", scripts)
        args = self.parse("__complete-path", "literature")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        values = set(buffer.getvalue().splitlines())
        self.assertTrue({"enrich"}.issubset(values))

    def test_completion_reads_flags_from_the_parser(self):
        def flags(*path):
            args = self.parse("__complete-flags", *path)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                args.func(args)
            return set(buffer.getvalue().splitlines())

        # No hand-kept flag lists in the shell scripts: a removed flag is gone
        # from completion the moment it leaves the parser.
        scripts = ws_cli.bash_completion_script() + ws_cli.zsh_completion_script()
        self.assertIn("__complete-flags", scripts)
        for removed in ("--no-link", "--depends-on", "--relations"):
            self.assertNotIn(removed, scripts)
        self.assertIn("--mode", flags("add", "document"))
        self.assertNotIn("--no-link", flags("add", "literature"))
        # Flags already typed do not break the lookup.
        self.assertEqual(flags("list", "tasks"), flags("list", "tasks", "--limit", "5"))
        # `ws edit REF` flags follow the kind named by the REF.
        self.assertIn("--add-field", flags("edit", "literature:Some2020Key"))
        self.assertIn("--add-tag", flags("edit", "document:some-key"))

    def test_document_delete_has_a_dry_run(self):
        args = self.parse(
            "delete",
            "document:some-receipt",
            "--dry-run",
        )
        self.assertTrue(args.dry_run)

    def test_top_level_delete_takes_bare_refs(self):
        args = self.parse("delete", "document:some-receipt", "task:call-x", "--dry-run")
        self.assertEqual(args.objects, ["document:some-receipt", "task:call-x"])
        self.assertTrue(args.dry_run)

    def test_top_level_show_takes_bare_refs(self):
        args = self.parse("show", "document:some-receipt", "person:maria")
        self.assertEqual(args.objects, ["document:some-receipt", "person:maria"])
        self.assertIs(args.func, catalog.command_show_any)

    def test_top_level_show_accepts_the_relations_sentence(self):
        args = self.parse("show", "relations", "of", "document:some-receipt", "--as", "party-to")
        self.assertEqual(args.objects, ["relations", "of", "document:some-receipt"])
        self.assertEqual(args.relation, "party-to")
        self.assertIs(args.func, catalog.command_show_any)

    def test_top_level_edit_defers_kind_flags_to_the_ref_kind(self):
        args = self.parse("edit", "document:some-receipt", "--type", "contract")
        self.assertEqual(args.object, "document:some-receipt")
        self.assertEqual(args.flags, ["--type", "contract"])
        self.assertIs(args.func, catalog.command_edit_any)

    def test_top_level_create_and_add_take_the_kind_first(self):
        task = self.parse("create", "task", "Submit", "May", "claim")
        self.assertIs(task.func, catalog.command_create)
        self.assertEqual(task.object_type, "task")
        resource = self.parse("create", "resource", "ExampleCo", "Reimbursements")
        self.assertEqual(resource.object_type, "resource")
        profile = self.parse("create", "profile", "PhD", "--type", "education")
        self.assertEqual(profile.func.__name__, "command_profile_create")
        person = self.parse("add", "person", "Maria", "Schwarz", "--ensure")
        self.assertIs(person.func, catalog.command_create)
        self.assertEqual(person.object_type, "person")
        self.assertTrue(person.ensure)
        document = self.parse("add", "document", "/tmp/example.pdf")
        self.assertIs(document.func, catalog.command_document_register)
        self.assertEqual(document.mode, "move")
        self.assertTrue(document.interactive_add)
        literature_add = self.parse("add", "literature", "2406.01234")
        self.assertEqual(literature_add.func.__name__, "command_literature_add")

    def test_describe_resolves_hoisted_spellings(self):
        args = self.parse("describe", "add", "document", "--json")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        record = json.loads(buffer.getvalue())
        self.assertEqual(record["command"], "ws add document")
        self.assertEqual(record["contract"], "contracts/documents.md")
        self.assertTrue(record["effects"]["writes"])

        args = self.parse("describe", "delete", "--json")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            args.func(args)
        record = json.loads(buffer.getvalue())
        self.assertEqual(record["contract"], "contracts/objects.md")
        self.assertTrue(record["effects"]["destructive"])

    def test_choice_values_render_once_in_help(self):
        from ws_lib import document_taxonomy, profile_taxonomy
        from ws_lib import project as project_lib

        def squeezed(parser):
            # argparse wraps help lines (even at hyphens); drop all whitespace
            # so a vocabulary is one substring regardless of wrapping.
            return "".join(parser.format_help().split())

        project_help = squeezed(subcommands(self.top["create"])["project"])
        self.assertEqual(project_help.count(",".join(project_lib.load_taxonomy()["type"])), 1)
        document_help = squeezed(subcommands(self.top["add"])["document"])
        self.assertEqual(document_help.count(",".join(document_taxonomy.type_ids())), 1)
        self.assertNotIn("{reference,copy,move}", document_help)
        profile_help = squeezed(subcommands(self.top["create"])["profile"])
        self.assertEqual(profile_help.count(",".join(profile_taxonomy.type_ids())), 1)

    def test_bare_creation_fails_cleanly_without_a_terminal(self):
        # On a terminal these open wizards; headless they must error, not hang.
        document = self.parse("add", "document")
        self.assertIsNone(document.file)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            document.func(document)
        profile = self.parse("create", "profile")
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            profile.func(profile)

    def test_top_level_list_takes_the_kind_as_first_word(self):
        bare = self.parse("list")
        self.assertIs(bare.func, catalog.command_list_overview)
        documents = self.parse("list", "documents", "--type", "contract")
        self.assertIs(documents.func, catalog.command_list)
        self.assertEqual(documents.object_type, "document")
        self.assertEqual(documents.document_type, "contract")
        events = self.parse("list", "events", "--upcoming")
        self.assertEqual(events.object_type, "event")
        self.assertTrue(events.upcoming)
        projects = self.parse("list", "projects", "--field", "physics")
        self.assertEqual(projects.func.__name__, "command_project_list")
        self.assertEqual(projects.field, ["physics"])
        literature = self.parse("list", "literature")
        self.assertIs(literature.func, catalog.command_list)
        self.assertEqual(literature.object_type, "literature")


if __name__ == "__main__":
    unittest.main()
