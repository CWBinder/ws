import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import anatomy, catalog, paths, records, relations


class AnatomySpecTests(unittest.TestCase):
    """Loading and validating the folder anatomy file."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.file = self.root / "folder-anatomy.yaml"
        self.patcher = mock.patch.object(paths, "FOLDER_ANATOMY", self.file)
        self.patcher.start()

    def tearDown(self) -> None:
        self.patcher.stop()
        self.tempdir.cleanup()

    def test_absent_file_yields_builtin_defaults(self) -> None:
        spec = anatomy.load_spec()
        anatomy.validate_spec(spec)
        self.assertEqual(spec, anatomy.DEFAULTS)

    def test_listed_domain_is_complete_and_others_default(self) -> None:
        self.file.write_text(
            "schema_version: 1\nprojects:\n  rings: [type]\n", encoding="utf-8"
        )
        spec = anatomy.load_spec()
        self.assertEqual(spec["projects"], {"rings": ["type"]})
        self.assertEqual(spec["documents"], anatomy.DEFAULTS["documents"])

    def test_schema_version_is_required(self) -> None:
        self.file.write_text("projects:\n  rings: [type]\n", encoding="utf-8")
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.load_spec()

    def test_legacy_tree_grammar_is_refused(self) -> None:
        self.file.write_text(
            "schema_version: 1\ndocuments:\n  by-type: {}\n", encoding="utf-8"
        )
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.validate_spec(anatomy.load_spec())

    def test_unknown_facet_is_refused(self) -> None:
        self.file.write_text(
            "schema_version: 1\nprojects:\n  rings: [flavour]\n",
            encoding="utf-8",
        )
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.validate_spec(anatomy.load_spec())

    def test_repeated_facet_is_refused(self) -> None:
        self.file.write_text(
            "schema_version: 1\nprojects:\n  rings: [type, type]\n",
            encoding="utf-8",
        )
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.validate_spec(anatomy.load_spec())

    def test_dependent_cannot_head_a_ring(self) -> None:
        self.file.write_text(
            "schema_version: 1\ndocuments:\n  rings: [month]\n",
            encoding="utf-8",
        )
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.validate_spec(anatomy.load_spec())

    def test_dependent_requires_its_parent(self) -> None:
        self.file.write_text(
            "schema_version: 1\ndocuments:\n  rings: [type > month]\n",
            encoding="utf-8",
        )
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.validate_spec(anatomy.load_spec())

    def test_only_dependents_may_follow_the_arrow(self) -> None:
        self.file.write_text(
            "schema_version: 1\ndocuments:\n  rings: [year > type]\n",
            encoding="utf-8",
        )
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.validate_spec(anatomy.load_spec())

    def test_depth_bounds(self) -> None:
        for depth in ("0", "4"):
            self.file.write_text(
                "schema_version: 1\ndocuments:\n"
                f"  rings: [type]\n  depth: {depth}\n",
                encoding="utf-8",
            )
            with self.assertRaises(anatomy.AnatomyError):
                anatomy.validate_spec(anatomy.load_spec())

    def test_explicit_prefixes_resolve(self) -> None:
        self.assertEqual(
            anatomy.resolve_grouping("projects", "classifier:type").source,
            "classifier",
        )
        self.assertEqual(
            anatomy.resolve_grouping("projects", "kind:event").source, "kind"
        )

    def test_resource_is_a_kind_facet_everywhere(self) -> None:
        self.assertEqual(
            anatomy.resolve_grouping("documents", "resource").source, "kind"
        )


class AnatomyBuildTests(unittest.TestCase):
    """Building trees from a ring set: nesting, dependents, kinds, pruning."""

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.file = self.root / "folder-anatomy.yaml"
        self.domain = self.root / "documents"
        self.store = self.domain / "files"
        self.store.mkdir(parents=True)
        self.events = self.root / "events"
        self.relations = self.root / "relations"
        self.patchers = [
            mock.patch.object(paths, "FOLDER_ANATOMY", self.file),
            mock.patch.dict(catalog.SPECS["event"], {"dir": self.events}),
            mock.patch.object(relations, "RELATIONS", self.relations),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def _item(self, name: str, data: dict) -> anatomy.Item:
        target = self.store / name
        target.write_bytes(b"x")
        return anatomy.Item(id=f"doc_{name}", link_name=name, target=target, data=data)

    def test_rings_nest_and_dependents_ride_free(self) -> None:
        self.file.write_text(
            "schema_version: 1\n"
            "documents:\n"
            "  rings: [type, year > month]\n"
            "  depth: 2\n",
            encoding="utf-8",
        )
        items = [
            self._item(
                "r.pdf",
                {"classification": {"type": "receipt", "date": "2026-07-30"}},
            ),
            self._item(
                "p.pdf",
                {"classification": {"type": "presentation"}},
            ),
            self._item("undated.pdf", {"classification": {"type": "receipt"}}),
        ]
        counts = anatomy.rebuild_domain("documents", self.domain, items, collision="id")
        self.assertEqual(counts, {"by-type": 5, "by-year": 5})
        # Items link flat at every value they reach, plus nested rings.
        self.assertTrue((self.domain / "by-type" / "receipt" / "r.pdf").is_symlink())
        self.assertTrue(
            (self.domain / "by-type" / "receipt" / "by-year" / "2026" / "r.pdf").is_symlink()
        )
        # The dependent month refines the year value in place.
        self.assertTrue(
            (
                self.domain / "by-type" / "receipt" / "by-year" / "2026"
                / "by-month" / "07-July" / "r.pdf"
            ).is_symlink()
        )
        # The transposed ordering exists as well.
        self.assertTrue(
            (self.domain / "by-year" / "2026" / "by-type" / "receipt" / "r.pdf").is_symlink()
        )
        # unclassified/ exists only at the first layer...
        self.assertTrue(
            (self.domain / "by-year" / "unclassified" / "undated.pdf").is_symlink()
        )
        self.assertFalse(
            (self.domain / "by-type" / "receipt" / "by-year" / "unclassified").exists()
        )
        # ...and a ring nobody descends into is never created.
        self.assertFalse(
            (self.domain / "by-type" / "presentation" / "by-year").exists()
        )

    def test_kind_ring_uses_related_object_names(self) -> None:
        self.events.mkdir(parents=True)
        self.relations.mkdir()
        records.atomic_write(
            self.events / "event_x.yaml",
            {"schema_version": 1, "id": "event_x", "kind": "event", "name": "ExampleCo Away Day"},
        )
        records.atomic_write(
            self.relations / "rel_x.yaml",
            {"schema_version": 1, "id": "rel_x", "subject": "doc_a.pdf", "object": "event_x", "relation": "presented-at"},
        )
        self.file.write_text(
            "schema_version: 1\n"
            "documents:\n"
            "  rings: [type, event]\n"
            "  depth: 2\n",
            encoding="utf-8",
        )
        items = [
            self._item("a.pdf", {"classification": {"type": "presentation"}}),
            self._item("b.pdf", {"classification": {"type": "presentation"}}),
        ]
        anatomy.rebuild_domain("documents", self.domain, items, collision="id")
        self.assertTrue(
            (
                self.domain / "by-type" / "presentation" / "by-event"
                / "ExampleCo Away Day" / "a.pdf"
            ).is_symlink()
        )
        self.assertTrue(
            (self.domain / "by-event" / "ExampleCo Away Day" / "by-type" / "presentation" / "a.pdf").is_symlink()
        )
        # The edge-less document stays flat at the value and in the root
        # fallback; it never enters the nested event ring.
        self.assertTrue(
            (self.domain / "by-type" / "presentation" / "b.pdf").is_symlink()
        )
        self.assertTrue(
            (self.domain / "by-event" / "unclassified" / "b.pdf").is_symlink()
        )
        self.assertFalse(
            (self.domain / "by-type" / "presentation" / "by-event" / "unclassified").exists()
        )

    def test_removed_tree_is_wiped_and_broken_spec_wipes_nothing(self) -> None:
        stale = self.domain / "by-stale" / "old"
        stale.mkdir(parents=True)
        self.file.write_text(
            "schema_version: 1\ndocuments:\n  rings: [type]\n", encoding="utf-8"
        )
        items = [self._item("note.pdf", {"classification": {"type": "letter"}})]
        counts = anatomy.rebuild_domain("documents", self.domain, items, collision="id")
        self.assertEqual(counts, {"by-type": 1})
        self.assertFalse((self.domain / "by-stale").exists())
        # Now break the spec: validation must refuse before wiping anything.
        self.file.write_text(
            "schema_version: 1\ndocuments:\n  rings: [flavour]\n",
            encoding="utf-8",
        )
        with self.assertRaises(anatomy.AnatomyError):
            anatomy.rebuild_domain("documents", self.domain, items, collision="id")
        self.assertTrue(
            (self.domain / "by-type" / "letter" / "note.pdf").is_symlink()
        )

    def test_subfields_are_filtered_by_their_current_parent_field(self) -> None:
        self.file.write_text(
            "schema_version: 1\nprojects:\n  rings: [field > subfield]\n",
            encoding="utf-8",
        )
        domain = self.root / "projects"
        target = self.store / "multi-field"
        target.mkdir()
        item = anatomy.Item(
            id="project:multi-field",
            link_name="multi-field",
            target=target,
            data={
                "fields": ["physics", "mathematics"],
                "subfields": ["spin-qubits", "tooling"],
            },
        )
        with mock.patch(
            "ws_lib.project.subfield_map",
            return_value={"physics": ["spin-qubits"], "mathematics": ["tooling"]},
        ):
            anatomy.rebuild_domain("projects", domain, [item])
        self.assertTrue(
            (domain / "by-field" / "physics" / "multi-field").is_symlink()
        )
        self.assertTrue(
            (
                domain / "by-field" / "physics" / "by-subfield"
                / "spin-qubits" / "multi-field"
            ).is_symlink()
        )
        self.assertTrue(
            (
                domain / "by-field" / "mathematics" / "by-subfield"
                / "tooling" / "multi-field"
            ).is_symlink()
        )
        self.assertFalse(
            (domain / "by-field" / "physics" / "by-subfield" / "tooling").exists()
        )


class ResourceAnatomyTests(unittest.TestCase):
    def test_resources_shelve_by_related_organisation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resources_root = root / "resources"
            items = resources_root / "items"
            organisations = root / "organisations"
            relations_dir = root / "relations"
            for folder, record in (
                ("exampleco-travel", {"id": "resource_01BUNDLE", "key": "exampleco-travel", "name": "ExampleCo Travel"}),
                ("loose-notes", {"id": "resource_01LOOSE", "key": "loose-notes", "name": "Loose Notes"}),
            ):
                (items / folder).mkdir(parents=True)
                records.atomic_write(
                    items / folder / "resource.yaml",
                    {"schema_version": 1, "kind": "resource", **record},
                )
            organisations.mkdir(parents=True)
            records.atomic_write(
                organisations / "org_q.yaml",
                {"schema_version": 1, "id": "org_q", "kind": "organisation", "name": "ExampleCo"},
            )
            relations_dir.mkdir()
            records.atomic_write(
                relations_dir / "rel_r.yaml",
                {"schema_version": 1, "id": "rel_r", "subject": "resource_01BUNDLE", "object": "org_q", "relation": "for"},
            )
            with (
                mock.patch.object(paths, "RESOURCES", resources_root),
                mock.patch.object(paths, "RESOURCE_ITEMS", items),
                mock.patch.object(paths, "FOLDER_ANATOMY", root / "missing.yaml"),
                mock.patch.object(relations, "RELATIONS", relations_dir),
                mock.patch.dict(catalog.SPECS["organisation"], {"dir": organisations}),
            ):
                counts = anatomy.rebuild_resources()
            link = resources_root / "by-organisation" / "ExampleCo" / "exampleco-travel"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), (items / "exampleco-travel").resolve())
            self.assertTrue(
                (resources_root / "by-organisation" / "unclassified" / "loose-notes").is_symlink()
            )
            # Kind rings with no edges at all fall back at the root only.
            self.assertEqual(
                counts,
                {"by-organisation": 2, "by-project": 2, "by-event": 2},
            )


class ProfileAnatomyTests(unittest.TestCase):
    def test_profile_objects_get_a_readable_by_type_view(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "profile"
            items = root / "items"
            items.mkdir(parents=True)
            object_id = "profile_01TEST"
            record = items / f"{object_id}.yaml"
            records.atomic_write(record, {
                "schema_version": 1,
                "id": object_id,
                "kind": "profile",
                "name": "DPhil Physics",
                "type": "education",
                "aliases": [],
            })
            with (
                mock.patch.object(paths, "CAREER", root),
                mock.patch.object(paths, "FOLDER_ANATOMY", Path(tmp) / "missing.yaml"),
                mock.patch.object(relations, "RELATIONS", Path(tmp) / "relations"),
                mock.patch.dict(catalog.SPECS["profile"], {"dir": items}),
            ):
                counts = anatomy.rebuild_profile()
            link = root / "by-type" / "education" / "DPhil Physics.yaml"
            self.assertEqual(counts, {"by-type": 1, "by-organisation": 1})
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), record.resolve())
            # No organisation edges: the item sits in the root fallback only.
            self.assertTrue(
                (root / "by-organisation" / "unclassified" / "DPhil Physics.yaml").is_symlink()
            )


if __name__ == "__main__":
    unittest.main()
