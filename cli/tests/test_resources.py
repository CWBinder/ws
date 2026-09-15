import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import catalog, indexing, paths, relations, resources


class ResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        specs = {
            kind: {**spec, "dir": self.root / spec["plural"]}
            for kind, spec in catalog.SPECS.items()
        }
        self.documents = self.root / "document-domain"
        specs["document"]["dir"] = self.documents / "items"
        specs["resource"]["dir"] = self.root / "resources" / "items"
        self.patchers = [
            mock.patch.object(catalog, "SPECS", specs),
            mock.patch.object(paths, "DOCUMENTS", self.documents),
            mock.patch.object(paths, "RESOURCES", self.root / "resources"),
            mock.patch.object(paths, "RESOURCE_ITEMS", self.root / "resources" / "items"),
            mock.patch.object(relations, "RELATIONS", self.root / "relations"),
            mock.patch.object(indexing, "INDEX", self.root / "search" / "index.sqlite"),
            mock.patch.object(catalog.project, "existing_project_names", return_value=[]),
            mock.patch.object(catalog.literature, "list_item_bibtex_files", return_value=[]),
            mock.patch.object(resources.anatomy, "rebuild_documents"),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def test_resource_is_a_folder_backed_object(self) -> None:
        resource, created = catalog.create_object(
            "resource",
            "ExampleCo Travel Reimbursements",
            {"aliases": ["ExampleCo expenses"], "description": "Travel files."},
        )
        self.assertTrue(created)
        self.assertEqual(resource.ref, "resource:exampleco-travel-reimbursements")
        self.assertEqual(resource.path.name, "resource.yaml")
        self.assertEqual(resource.path.parent.name, "exampleco-travel-reimbursements")
        self.assertEqual(catalog.resolve(resource.ref).id, resource.id)
        public = catalog.public_object_data(resource)
        self.assertEqual(public["folder"], str(resource.path.parent))
        self.assertNotIn("id", public)

    def test_add_moves_an_ordinary_file_without_creating_an_object(self) -> None:
        resource = catalog.create_object("resource", "Interview Material", {})[0]
        original_updated = catalog.records.load_record(resource.path)["updated_at"]
        source = self.root / "interviewer-cv.pdf"
        source.write_bytes(b"pdf")
        output = io.StringIO()
        with mock.patch.object(resources.records, "now", return_value="2026-08-16T12:00:00+01:00"), \
                contextlib.redirect_stdout(output):
            resources.command_add(argparse.Namespace(
                resource=resource.ref,
                path=str(source),
                name=None,
                mode="move",
                json=False,
            ))
        self.assertFalse(source.exists())
        self.assertEqual((resource.path.parent / "interviewer-cv.pdf").read_bytes(), b"pdf")
        self.assertEqual([obj.ref for obj in catalog.all_objects()], [resource.ref])
        self.assertNotEqual(original_updated, catalog.records.load_record(resource.path)["updated_at"])
        self.assertEqual(
            catalog.records.load_record(resource.path)["updated_at"],
            "2026-08-16T12:00:00+01:00",
        )

    def test_child_filename_finds_the_containing_resource_once(self) -> None:
        resource = catalog.create_object("resource", "Interview Material", {})[0]
        (resource.path.parent / "Interviewer CV.pdf").write_bytes(b"pdf")
        indexing.rebuild(quiet=True)
        args = argparse.Namespace(query=["Interviewer", "CV"], type=None, limit=50, json=True)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            indexing.command_search(args)
        self.assertEqual(json.loads(output.getvalue()), [
            {"ref": resource.ref, "kind": "resource", "name": "Interview Material"}
        ])

    def test_retire_flow_moves_file_then_delete_cascades_relations(self) -> None:
        resource = catalog.create_object("resource", "ExampleCo Travel Reimbursements", {})[0]
        organisation = catalog.create_object("organisation", "Example Company", {})[0]
        source = self.documents / "files" / "ExampleCo Expenses.xlsx"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"sheet")
        document = catalog.create_object("document", "ExampleCo Expenses Form", {
            "path": "files/ExampleCo Expenses.xlsx",
            "path_root": "documents",
            "classification": {"type": "form"},
        })[0]
        relations.create(document.id, organisation.id, "for")
        relations.create(resource.id, organisation.id, "expense-for")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            resources.command_add(argparse.Namespace(
                resource=resource.ref,
                path=str(source),
                name="2026/May/ExampleCo Expenses.xlsx",
                mode="move",
                json=False,
            ))
            catalog.command_delete(argparse.Namespace(
                object_type="document",
                objects=[document.ref],
                dry_run=False,
            ))

        self.assertFalse(source.exists())
        self.assertEqual(
            (resource.path.parent / "2026" / "May" / "ExampleCo Expenses.xlsx").read_bytes(),
            b"sheet",
        )
        self.assertFalse(document.path.exists())
        self.assertEqual(catalog.public_stored_objects("document"), [])
        rows = relations.load_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["subject"], resource.id)
        self.assertEqual(rows[0]["object"], organisation.id)
        self.assertEqual(rows[0]["relation"], "expense-for")

    def test_delete_moves_managed_file_to_trash(self) -> None:
        trash = self.root / "trash"
        trash.mkdir()
        source = self.documents / "files" / "receipt.pdf"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"receipt")
        document = catalog.create_object("document", "May Receipt", {
            "path": "files/receipt.pdf",
            "path_root": "documents",
            "classification": {"type": "receipt"},
        })[0]

        output = io.StringIO()
        with mock.patch.object(catalog, "TRASH", trash), contextlib.redirect_stdout(output):
            catalog.command_delete(argparse.Namespace(
                object_type="document", objects=[document.ref], dry_run=False,
            ))
        self.assertFalse(source.exists())
        self.assertFalse(document.path.exists())
        self.assertEqual((trash / "receipt.pdf").read_bytes(), b"receipt")
        self.assertIn("Trash", output.getvalue())

    def test_delete_dry_run_changes_nothing(self) -> None:
        organisation = catalog.create_object("organisation", "Example Company", {})[0]
        document = catalog.create_object("document", "Loose Note", {})[0]
        relations.create(document.id, organisation.id, "related")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_delete(argparse.Namespace(
                object_type="document", objects=[document.ref], dry_run=True,
            ))
        self.assertIn("would delete", output.getvalue())
        self.assertTrue(document.path.exists())
        self.assertEqual(len(relations.load_all()), 1)

    def test_generic_delete_cascades_for_pure_record_kinds(self) -> None:
        organisation = catalog.create_object("organisation", "Example Company", {})[0]
        task = catalog.create_object("task", "Submit May claim", {})[0]
        relations.create(task.id, organisation.id, "for")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_delete(argparse.Namespace(
                object_type="task", objects=[task.ref], dry_run=False,
            ))

        self.assertFalse(task.path.exists())
        self.assertEqual(relations.load_all(), [])
        self.assertTrue(organisation.path.exists())

    def test_top_level_delete_dispatches_on_ref_kind(self) -> None:
        task = catalog.create_object("task", "Submit May claim", {})[0]
        event = catalog.create_object("event", "Group Meeting", {})[0]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_delete_any(argparse.Namespace(
                objects=[task.ref, event.ref], dry_run=False,
            ))

        self.assertFalse(task.path.exists())
        self.assertFalse(event.path.exists())

    def test_top_level_delete_rejects_undeletable_kinds(self) -> None:
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            catalog.command_delete_any(argparse.Namespace(
                objects=["project:virtuallab"], dry_run=False,
            ))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            catalog.command_delete_any(argparse.Namespace(
                objects=["not-a-ref"], dry_run=False,
            ))

    def test_top_level_show_renders_mixed_kinds(self) -> None:
        task = catalog.create_object("task", "Submit May claim", {})[0]
        organisation = catalog.create_object("organisation", "Example Company", {})[0]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_show_any(argparse.Namespace(
                objects=[task.ref, organisation.ref], relation=None, json=True,
            ))
        rows = json.loads(output.getvalue())
        self.assertEqual([row["ref"] for row in rows], [task.ref, organisation.ref])

    def test_relations_query_uses_the_index_when_present(self) -> None:
        task = catalog.create_object("task", "Submit May claim", {})[0]
        organisation = catalog.create_object("organisation", "Example Company", {})[0]
        relations.create(task.id, organisation.id, "for")

        scanned = relations.for_object(task.id)
        self.assertFalse(indexing.INDEX.exists())
        indexing.rebuild(quiet=True)
        indexed = relations.for_object(task.id)

        self.assertTrue(indexing.INDEX.exists())
        self.assertEqual(
            [(row["subject"], row["object"], row["relation"]) for row in indexed],
            [(row["subject"], row["object"], row["relation"]) for row in scanned],
        )

    def test_show_relations_sentence_renders_edges(self) -> None:
        task = catalog.create_object("task", "Submit May claim", {})[0]
        organisation = catalog.create_object("organisation", "Example Company", {})[0]
        relations.create(task.id, organisation.id, "for")

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_show_any(argparse.Namespace(
                objects=["relations", "of", task.ref], relation=None, json=False,
            ))
        self.assertIn("--for-->", output.getvalue())
        self.assertIn(organisation.ref, output.getvalue())

    def test_top_level_edit_applies_kind_specific_flags(self) -> None:
        person = catalog.create_object("person", "Maria Schwarz", {})[0]

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_edit_any(argparse.Namespace(
                object=person.ref, flags=["--add-email", "maria@example.org"],
            ))
        data = catalog.records.load_record(person.path)
        self.assertIn("maria@example.org", data.get("emails", []))

    def test_task_wizard_asks_description_due_priority_aliases(self) -> None:
        answers = iter(["Send the May receipts", "2026-09-15", "high", "may claim"])
        with mock.patch("builtins.input", side_effect=lambda *_: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()):
            catalog.command_create(argparse.Namespace(
                object_type="task", title=["Submit", "claim"], ensure=False, json=False,
                interactive=True,
            ))
        data = catalog.resolve("task:submit-claim").data or {}
        self.assertEqual(data.get("description"), "Send the May receipts")
        self.assertEqual(data.get("due"), "2026-09-15")
        self.assertEqual(data.get("priority"), "high")
        self.assertEqual(data.get("aliases"), ["may claim"])
        self.assertEqual(relations.for_object(data["id"]), [])

    def test_task_wizard_reasks_a_bad_due_date_and_skips_on_enter(self) -> None:
        answers = iter(["", "next week", "2026-13-01", "2026-09-15", "", ""])
        with mock.patch("builtins.input", side_effect=lambda *_: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            catalog.command_create(argparse.Namespace(
                object_type="task", title=["Submit", "claim"], ensure=False, json=False,
                interactive=True,
            ))
        data = catalog.resolve("task:submit-claim").data or {}
        self.assertEqual(data.get("due"), "2026-09-15")
        self.assertNotIn("description", data)
        self.assertNotIn("priority", data)
        self.assertEqual(data.get("aliases"), [])

    def test_task_wizard_skips_facts_given_as_flags(self) -> None:
        answers = iter(["", ""])  # only description and aliases remain to ask
        with mock.patch("builtins.input", side_effect=lambda *_: next(answers)), \
                contextlib.redirect_stdout(io.StringIO()):
            catalog.command_create(argparse.Namespace(
                object_type="task", title=["Submit", "claim"], ensure=False, json=False,
                interactive=True, due="2026-09-15", priority="low",
            ))
        data = catalog.resolve("task:submit-claim").data or {}
        self.assertEqual(data.get("due"), "2026-09-15")
        self.assertEqual(data.get("priority"), "low")

    def test_task_create_never_prompts_off_tty(self) -> None:
        with mock.patch.object(sys.stdin, "isatty", return_value=False), \
                mock.patch("builtins.input", side_effect=AssertionError("prompted")), \
                contextlib.redirect_stdout(io.StringIO()):
            catalog.command_create(argparse.Namespace(
                object_type="task", title=["Quiet", "task"], ensure=False, json=False,
            ))
        self.assertTrue(catalog.resolve("task:quiet-task"))

    def test_bare_list_counts_every_kind(self) -> None:
        catalog.create_object("task", "Submit May claim", {})
        catalog.create_object("organisation", "Example Company", {})

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_list_overview(argparse.Namespace(json=True))
        rows = json.loads(output.getvalue())
        self.assertEqual(
            {row["kind"]: row["count"] for row in rows},
            {"organisation": 1, "task": 1},
        )

    def test_top_level_edit_rejects_curated_kinds(self) -> None:
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            catalog.command_edit_any(argparse.Namespace(
                object="project:virtuallab", flags=[],
            ))
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            catalog.command_edit_any(argparse.Namespace(
                object="not-a-ref", flags=[],
            ))

    def test_resource_delete_moves_whole_folder_to_trash(self) -> None:
        trash = self.root / "trash"
        trash.mkdir()
        organisation = catalog.create_object("organisation", "Example Company", {})[0]
        resource = catalog.create_object("resource", "Old Bundle", {})[0]
        relations.create(resource.id, organisation.id, "expense-for")
        (resource.path.parent / "receipt.pdf").write_bytes(b"receipt")
        folder_name = resource.path.parent.name

        output = io.StringIO()
        with mock.patch.object(catalog, "TRASH", trash), contextlib.redirect_stdout(output):
            catalog.command_delete(argparse.Namespace(
                object_type="resource", objects=[resource.ref], dry_run=False,
            ))
        self.assertFalse(resource.path.parent.exists())
        self.assertEqual(relations.load_all(), [])
        self.assertEqual((trash / folder_name / "receipt.pdf").read_bytes(), b"receipt")
        self.assertTrue((trash / folder_name / "resource.yaml").exists())


if __name__ == "__main__":
    unittest.main()
