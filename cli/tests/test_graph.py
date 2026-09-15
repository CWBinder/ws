import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import anatomy, catalog, indexing, literature, relations, wiki


class GraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        # Mirror the production layout: a domain root holding the flat
        # items/ store, with the derived by-* trees as siblings of items/.
        self.domain = self.root / "projects"
        self.projects = self.domain / "items"
        self.projects.mkdir(parents=True)
        self.project = self.projects / "shuttling"
        self.project.mkdir()
        (self.project / "project.yaml").write_text(
            "schema_version: 1\ntitle: Shuttling\nstatus: active\nfields: []\n",
            encoding="utf-8",
        )
        (self.project / "README.md").write_text("# Shuttling\n", encoding="utf-8")
        (self.project / "AGENTS.md").write_text("# Agents\n", encoding="utf-8")

        specs = {}
        for type_name, spec in catalog.SPECS.items():
            specs[type_name] = {
                **spec,
                "dir": self.root / "data" / spec["plural"],
            }
        self.patchers = [
            mock.patch.object(catalog, "SPECS", specs),
            mock.patch.object(catalog.project, "PROJECTS", self.projects),
            mock.patch.object(anatomy, "PROJECTS_DOMAIN", self.domain),
            # No anatomy file: the engine's built-in defaults apply.
            mock.patch.object(
                catalog.paths, "FOLDER_ANATOMY", self.root / "no-anatomy.yaml"
            ),
            mock.patch.object(catalog.project, "existing_project_names", return_value=["shuttling"]),
            mock.patch.object(catalog.literature, "list_item_bibtex_files", return_value=[]),
            mock.patch.object(relations, "RELATIONS", self.root / "data" / "relations"),
            mock.patch.object(relations.paths, "LEGACY_RELATIONS", self.root / "legacy-relations"),
            mock.patch.object(indexing, "INDEX", self.root / "index.sqlite"),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def create_person(self, name: str = "Maria Schwarz"):
        return catalog.create_object(
            "person",
            name,
            {
                "emails": ["maria@example.org"],
                "email": "maria@example.org",
                "source": "address book",
                "observed_at": "2026-07-30",
            },
        )[0]

    def test_ensure_is_idempotent_and_provenance_is_preserved(self) -> None:
        person = self.create_person()
        ensured, created = catalog.create_object(
            "person",
            "Maria Schwarz",
            {"email": "maria@example.org", "emails": ["maria@example.org"]},
            ensure=True,
        )
        self.assertFalse(created)
        self.assertEqual(ensured.id, person.id)
        data = catalog.records.load_record(person.path)
        self.assertEqual(data["emails"], ["maria@example.org"])
        self.assertNotIn("email", data)
        self.assertEqual(data["provenance"][0]["source"], "address book")

        bare = catalog.create_object("person", "Tom Harty", {})[0]
        updated, created = catalog.create_object(
            "person",
            "Tom Harty",
            {
                "email": "tom@example.org",
                "emails": ["tom@example.org"],
                "source": "email",
            },
            ensure=True,
        )
        self.assertFalse(created)
        self.assertEqual(updated.id, bare.id)
        self.assertEqual(catalog.records.load_record(bare.path)["emails"], ["tom@example.org"])

    def test_ref_is_stable_when_display_name_changes(self) -> None:
        person = self.create_person()
        original_path = person.path
        edited = catalog.edit_object(person, {"name": "Maria Black"})
        self.assertEqual(edited.ref, "person:maria-schwarz")
        self.assertEqual(edited.path, original_path)
        self.assertEqual(edited.title, "Maria Black")

    def test_names_aliases_and_internal_ids_are_not_action_operands(self) -> None:
        person = catalog.create_object(
            "person", "Maria Schwarz", {"aliases": ["MS"]}
        )[0]
        self.assertEqual(catalog.resolve(person.ref).id, person.id)
        for value in (person.title, "MS", person.id):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                catalog.resolve(value)

    def test_repeated_kind_prefix_is_named_as_a_typo(self) -> None:
        person = catalog.create_object("person", "Maria Schwarz", {})[0]
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer), self.assertRaises(SystemExit):
            catalog.resolve(f"person:{person.ref}")
        message = buffer.getvalue()
        # Naming the typo beats sending the user to search for a key that
        # still carries a prefix.
        self.assertIn("kind prefix is repeated", message)
        self.assertIn(person.ref, message)
        self.assertNotIn("does not exist", message)

    def test_a_keyless_legacy_record_is_still_readable(self) -> None:
        # `ws refs migrate` is gone (it had nothing left to migrate), but a
        # record written before keys existed must still resolve: the key is
        # derived from the name on read.
        store = Path(catalog.SPECS["person"]["dir"])
        store.mkdir(parents=True, exist_ok=True)
        legacy = store / "person_legacy.yaml"
        catalog.records.atomic_write(legacy, {
            "schema_version": 1,
            "id": "person_legacy",
            "kind": "person",
            "name": "Ada Lovelace",
            "aliases": [],
        })
        resolved = catalog.resolve("person:ada-lovelace")
        self.assertEqual(resolved.id, "person_legacy")
        self.assertEqual(resolved.path, legacy)

    def test_add_ensure_flag_is_get_or_create_at_the_command_level(self) -> None:
        person = self.create_person()
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            catalog.command_create(argparse.Namespace(
                object_type="person", title="Maria Schwarz", json=True, ensure=True
            ))
        payload = json.loads(buffer.getvalue())
        self.assertFalse(payload["created"])
        self.assertEqual(payload["ref"], person.ref)

    def test_relate_natural_grammar_with_to_and_as(self) -> None:
        person = self.create_person()
        org = catalog.create_object("organisation", "ExampleCo", {"aliases": []})[0]
        args = argparse.Namespace(
            references=[person.ref, "to", org.ref, "as", "vice", "president"],
            relation="", valid_from=None, valid_until=None, source=None,
            observed_at=None, json=False,
        )
        with mock.patch("ws_lib.anatomy.rebuild_documents"), \
                contextlib.redirect_stdout(io.StringIO()):
            relations.command_relate(args)
        row = relations.load_all()[-1]
        self.assertEqual(row["subject"], person.id)
        self.assertEqual(row["relation"], "vice-president")

    def test_relate_rejects_names_instead_of_refs(self) -> None:
        person = self.create_person()
        org = catalog.create_object("organisation", "ExampleCo", {"aliases": []})[0]
        args = argparse.Namespace(
            references=["Maria Schwarz", org.ref],
            relation="", valid_from=None, valid_until=None, source=None,
            observed_at=None, json=False,
        )
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            relations.command_relate(args)
        self.assertEqual(relations.load_all(), [])

    def test_unrelate_accepts_the_same_phrasing(self) -> None:
        person = self.create_person()
        org = catalog.create_object("organisation", "ExampleCo", {"aliases": []})[0]
        relations.create(person.id, org.id, "member-of")
        args = argparse.Namespace(
            references=[person.ref, "to", org.ref],
            relation=None, dry_run=False,
        )
        buffer = io.StringIO()
        with mock.patch("ws_lib.anatomy.rebuild_documents"), \
                contextlib.redirect_stdout(buffer):
            relations.command_unrelate(args)
        # Stateless relations: unrelate deletes the record outright and
        # prints the exact command that would restore it.
        self.assertEqual(relations.load_all(), [])
        self.assertIn("restore with: ws relate", buffer.getvalue())
        self.assertIn(person.ref, buffer.getvalue())
        self.assertIn(org.ref, buffer.getvalue())

    def test_subprojects_have_project_identity_and_relate(self) -> None:
        sub = self.project / "paper-x"
        sub.mkdir()
        (sub / "subproject.yaml").write_text(
            "schema_version: 1\nname: paper-x\ntype: subproject\nparent: shuttling\nvenv: ../.venv\n",
            encoding="utf-8",
        )
        ref = catalog.resolve("project:shuttling/paper-x")
        self.assertEqual(ref.type, "project")
        self.assertEqual((ref.data or {}).get("parent"), "shuttling")
        org = catalog.create_object("organisation", "ExampleCo", {"aliases": []})[0]
        row, created = relations.create("project:shuttling/paper-x", org.id, "for")
        self.assertTrue(created)
        self.assertEqual(row["subject"], "project:shuttling/paper-x")

    def test_project_views_rebuild_creates_org_shelves(self) -> None:
        org = catalog.create_object("organisation", "ExampleCo", {"aliases": []})[0]
        relations.create("project:shuttling", org.id, "with")
        counts = anatomy.rebuild_projects()
        # Container-less views: the by-* trees sit at the domain root,
        # beside the items/ store.
        link = self.domain / "by-organisation" / "ExampleCo" / "shuttling"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.projects / "shuttling").resolve())
        self.assertTrue((self.domain / "by-status" / "active" / "shuttling").is_symlink())
        # The nested status ring beneath the organisation value.
        self.assertTrue(
            (self.domain / "by-organisation" / "ExampleCo" / "by-status" / "active" / "shuttling").is_symlink()
        )
        self.assertEqual(counts["by-organisation"], 2)

    def test_project_list_filters_by_classifier(self) -> None:
        with mock.patch.object(catalog.project, "use_projects_dir"):
            for status, expected in (("active", "shuttling"), ("archived", "no projects")):
                ns = argparse.Namespace(type=None, status=status, field=None, keyword=None)
                buffer = io.StringIO()
                with contextlib.redirect_stdout(buffer):
                    catalog.project.command_project_list(ns)
                self.assertIn(expected, buffer.getvalue())

    def test_findings_ignore_merged_tombstones(self) -> None:
        canonical = self.create_person()
        duplicate = catalog.create_object("person", "Maria Schwarz", {"aliases": []})[0]
        with contextlib.redirect_stdout(io.StringIO()):
            catalog.merge_objects(duplicate, canonical, dry_run=False)
        rows = catalog.findings({"person"})
        self.assertEqual([row for row in rows if "duplicate" in row["message"]], [])
        self.assertNotIn(duplicate.id, {obj.id for obj in catalog.all_objects()})
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            catalog.resolve(duplicate.ref)

    def test_add_wizard_fills_missing_facts_but_never_relates(self) -> None:
        answers = iter(["AE", "", "Alex", "c@example.org", ""])
        args = argparse.Namespace(
            object_type="person", title="Maria Schwarz", json=False,
            interactive=True, ensure=False,
        )
        with mock.patch("builtins.input", side_effect=lambda *_: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()):
            catalog.command_create(args)
        person = catalog.resolve("person:maria-schwarz", "person")
        data = person.data or {}
        self.assertEqual(data["aliases"], ["AE"])
        self.assertEqual(data["preferred_name"], "Alex")
        self.assertEqual(data["emails"], ["c@example.org"])
        self.assertNotIn("phones", data)
        self.assertEqual(relations.for_object(person.id), [])

    def test_bare_add_asks_for_the_name_first(self) -> None:
        answers = iter(["Maria Neu", "", "", "", "", "", ""])
        args = argparse.Namespace(
            object_type="person", title=[], json=False,
            interactive=True, ensure=False,
        )
        with mock.patch("builtins.input", side_effect=lambda *_: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()):
            catalog.command_create(args)
        self.assertTrue(catalog.resolve("person:maria-neu", "person"))

    def test_add_never_prompts_off_tty(self) -> None:
        args = argparse.Namespace(
            object_type="person", title="Quiet Person", json=False, ensure=False,
        )
        with mock.patch.object(sys.stdin, "isatty", return_value=False), \
                mock.patch("builtins.input", side_effect=AssertionError("prompted")), \
                contextlib.redirect_stdout(io.StringIO()):
            catalog.command_create(args)
        self.assertTrue(catalog.resolve("person:quiet-person", "person"))

    def test_document_ensure_matches_by_stored_path(self) -> None:
        existing = catalog.create_object(
            "document",
            "Final report",
            {"path": "files/final.pdf", "path_root": "documents"},
        )[0]
        ensured, created = catalog.create_object(
            "document",
            "Final report",
            {"path": "files/final.pdf", "path_root": "documents"},
            ensure=True,
        )
        self.assertFalse(created)
        self.assertEqual(ensured.id, existing.id)

    def test_document_can_relate_to_project_idempotently(self) -> None:
        document = catalog.create_object(
            "document",
            "Final report",
            {"path": "Reports/final.pdf", "path_root": "documents"},
        )[0]
        first, created = relations.create(document.id, "project:shuttling", "deliverable")
        second, created_again = relations.create(document.id, "project:shuttling", "deliverable")

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["subject"], document.id)
        self.assertEqual(first["object"], "project:shuttling")
        self.assertEqual(relations.findings(), [])

    def test_merge_redirects_relationships_and_keeps_redirect_record(self) -> None:
        duplicate = self.create_person("Maria S.")
        canonical = catalog.create_object("person", "Maria Schwarz", {})[0]
        row, _ = relations.create(duplicate.id, "project:shuttling", "speaker")

        with contextlib.redirect_stdout(io.StringIO()):
            catalog.merge_objects(duplicate, canonical)

        redirected = relations.get(row["id"])
        self.assertEqual(redirected["subject"], canonical.id)
        duplicate_data = catalog.records.load_record(duplicate.path)
        self.assertEqual(duplicate_data["status"], "merged")
        self.assertEqual(duplicate_data["redirect_to"], canonical.id)

    def test_index_is_rebuildable_and_invalidated_by_mutation(self) -> None:
        person = self.create_person()
        result = indexing.rebuild(quiet=True)
        self.assertTrue(indexing.INDEX.exists())
        self.assertGreaterEqual(result["objects"], 2)  # person and project
        catalog.edit_object(person, {"title": "Maria Black"})
        self.assertFalse(indexing.INDEX.exists())
        indexing.rebuild(quiet=True)
        self.assertEqual(indexing.findings(), [])

    def test_wiki_renders_relationship_as_direct_wikilink(self) -> None:
        document = catalog.create_object(
            "document",
            "Final report",
            {"path": str(self.root / "final.pdf"), "path_root": "external"},
        )[0]
        (self.root / "final.pdf").write_bytes(b"pdf")
        relations.create(document.id, "project:shuttling", "deliverable")

        knowledgebase = self.root / "knowledgebase"
        generated = knowledgebase / "generated"
        wiki_patchers = [
            mock.patch.object(wiki, "WORKSPACE", self.root),
            mock.patch.object(wiki, "KNOWLEDGEBASE", knowledgebase),
            mock.patch.object(wiki, "GENERATED", generated),
            mock.patch.object(wiki.project, "PROJECTS", self.projects),
            mock.patch.object(wiki.project, "existing_project_names", return_value=["shuttling"]),
            mock.patch.object(wiki.project, "load_taxonomy", return_value={"fields": []}),
            mock.patch.object(wiki.literature, "list_item_bibtex_files", return_value=[]),
            mock.patch.object(wiki.career, "load_profile", return_value={}),
            mock.patch.object(wiki.career, "CAREER", self.root / "career"),
            mock.patch.object(wiki.career, "ITEMS", self.root / "career" / "items"),
            mock.patch.object(wiki.career, "TAXONOMY", self.root / "career" / "profile-taxonomy.yaml"),
        ]
        for patcher in wiki_patchers:
            patcher.start()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                wiki.command_wiki(argparse.Namespace())
        finally:
            for patcher in reversed(wiki_patchers):
                patcher.stop()

        project_note = (generated / "projects" / "shuttling.md").read_text(encoding="utf-8")
        document_note = (generated / "documents" / "document-final-report.md").read_text(encoding="utf-8")
        connections = (generated / "Connections.md").read_text(encoding="utf-8")
        self.assertIn("[[document-final-report|Final report]]", project_note)
        self.assertIn("[[shuttling|Shuttling]]", document_note)
        self.assertIn('aliases:\n  - "Final report"', document_note)
        self.assertIn("`deliverable`", connections)

    def test_legacy_relationships_migrate_to_dedicated_store(self) -> None:
        legacy = relations.paths.LEGACY_RELATIONS
        legacy.mkdir(parents=True)
        source = legacy / "rel_example.yaml"
        source.write_text(
            "schema_version: 1\nid: rel_example\nsubject: project:a\n"
            "object: project:b\nrelation: related\nstatus: active\n",
            encoding="utf-8",
        )

        moved, identical = relations.migrate_legacy()

        self.assertEqual((moved, identical), (1, 0))
        self.assertFalse(source.exists())
        self.assertTrue((relations.RELATIONS / "rel_example.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
