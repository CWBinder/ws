import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import anatomy, catalog, literature


class LiteratureClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.items = self.root / "items"
        self.items.mkdir()
        self.patchers = [
            mock.patch.object(literature, "LITERATURE", self.root),
            mock.patch.object(literature, "LITERATURE_ITEMS", self.items),
            # No anatomy file: the engine's built-in defaults apply.
            mock.patch.object(
                literature.paths, "FOLDER_ANATOMY", self.root / "no-anatomy.yaml"
            ),
            mock.patch.object(
                literature,
                "load_taxonomy",
                return_value={
                    "fields": ["physics", "ai"],
                    "subfields": {"physics": ["spin-qubits", "shuttling"], "ai": []},
                },
            ),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self) -> None:
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.tempdir.cleanup()

    def make_item(
        self, key: str, doi: str, *, author: str = "", year: str = ""
    ) -> Path:
        root = self.items / key
        root.mkdir()
        extra = ""
        if author:
            extra += f"  author = {{{author}}},\n"
        if year:
            extra += f"  year = {{{year}}},\n"
        (root / "citation.bib").write_text(
            f"@article{{{key},\n  doi = {{{doi}}},\n{extra}}}\n", encoding="utf-8"
        )
        return root

    def test_default_info_yaml_has_fields_and_no_nature_or_reading_status(self) -> None:
        info = literature.default_info_yaml("@article{x,\n}\n")
        self.assertIn("fields: []", info)
        self.assertIn("subfields: []", info)
        self.assertNotIn("nature", info)
        self.assertNotIn("reading_status", info)

    def test_bibtex_authors_normalizes_names_and_keeps_every_author(self) -> None:
        bibtex = (
            "@article{x,\n"
            "  author = {Doe, Alice M. and Bob Smith and {ATLAS Collaboration}},\n"
            "}\n"
        )
        self.assertEqual(
            literature.bibtex_authors(bibtex),
            ["Alice Doe", "Bob Smith", "ATLAS Collaboration"],
        )
        self.assertTrue(literature.author_matches("Alice M. Doe", "Alice Doe"))
        self.assertFalse(literature.author_matches("Alice Doe", "Andrew Doe"))

    def test_listing_does_not_require_optional_item_files(self) -> None:
        # Items with only a citation.bib must still surface; `ws search`
        # covers them through the shared index.
        self.make_item("Turner2025Device", "10.1000/turner")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            catalog.command_list(
                argparse.Namespace(object_type="literature", limit=100, json=False)
            )
        self.assertIn("literature:Turner2025Device", output.getvalue())

    def test_update_info_classifiers_preserves_other_content(self) -> None:
        root = self.make_item("smith2020", "10.1000/smith")
        (root / "info.yaml").write_text(
            'schema_version: 1\nkeywords:\n  - "qudits"\n'
            'fields: []\nsummary: "Hand-written summary."\nnotes: "Keep me."\n',
            encoding="utf-8",
        )
        literature.update_info_classifiers(root, ["physics"], ["spin-qubits"])
        content = (root / "info.yaml").read_text(encoding="utf-8")
        self.assertIn("  - physics", content)
        self.assertIn("subfields:\n  - spin-qubits", content)
        self.assertIn('summary: "Hand-written summary."', content)
        self.assertIn('notes: "Keep me."', content)
        self.assertIn('  - "qudits"', content)
        self.assertEqual(sum(line.startswith("fields:") for line in content.splitlines()), 1)
        self.assertEqual(sum(line.startswith("subfields:") for line in content.splitlines()), 1)

    def test_classify_flags_apply_without_prompts(self) -> None:
        root = self.make_item("smith2021", "10.1000/smith21")
        literature.write_info_if_missing(root, "@article{x,\n}\n")
        args = argparse.Namespace(field=["physics"], subfield=["spin-qubits"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            literature.classify_new_item(root, args)
        content = (root / "info.yaml").read_text(encoding="utf-8")
        self.assertIn("  - spin-qubits", content)
        self.assertIn("classified: fields=physics", out.getvalue())
        self.assertIn("classified: subfields=spin-qubits", out.getvalue())

    def test_classify_rejects_unknown_fields_non_interactively(self) -> None:
        root = self.make_item("smith2022", "10.1000/smith22")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            literature.classify_new_item(root, argparse.Namespace(field=["biology"]))
        self.assertIn("unknown field", err.getvalue())

    def test_classify_rejects_subfield_under_wrong_field(self) -> None:
        root = self.make_item("smith-wrong", "10.1000/wrong")
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            literature.classify_new_item(
                root,
                argparse.Namespace(field=["ai"], subfield=["spin-qubits"]),
            )
        self.assertIn("do not belong", err.getvalue())

    def test_classify_without_flags_non_interactive_is_a_no_op(self) -> None:
        root = self.make_item("smith2023", "10.1000/smith23")
        literature.write_info_if_missing(root, "@article{x,\n}\n")
        before = (root / "info.yaml").read_text(encoding="utf-8")
        literature.classify_new_item(root, argparse.Namespace(field=[]))
        self.assertEqual((root / "info.yaml").read_text(encoding="utf-8"), before)

    def test_add_taxonomy_value_accepts_only_fields(self) -> None:
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            literature.add_taxonomy_value("type", "review")
        self.assertIn("use fields", err.getvalue())

    def test_views_rebuild_builds_author_field_and_year_trees(self) -> None:
        classified = self.make_item(
            "classified2024",
            "10.1000/classified",
            author="Doe, Alice and Bob Smith",
            year="2024",
        )
        literature.write_info_if_missing(classified, "@article{x,\n}\n")
        literature.update_info_classifiers(classified, ["physics"], ["spin-qubits"])
        bare = self.make_item("bare2024", "10.1000/bare")
        counts = anatomy.rebuild_literature()
        # Container-less views: by-* trees sit at the literature domain root.
        views = self.root
        self.assertTrue((views / "by-field" / "physics" / "by-subfield" / "spin-qubits" / "classified2024").is_symlink())
        self.assertTrue((views / "by-field" / "unclassified" / "bare2024").is_symlink())
        self.assertTrue((views / "by-author" / "Alice Doe" / "classified2024").is_symlink())
        self.assertTrue((views / "by-author" / "Bob Smith" / "classified2024").is_symlink())
        self.assertTrue((views / "by-author" / "unclassified" / "bare2024").is_symlink())
        self.assertTrue((views / "by-year" / "2024" / "classified2024").is_symlink())
        self.assertTrue((views / "by-year" / "unclassified" / "bare2024").is_symlink())
        # The set nests into itself below each value.
        self.assertTrue((views / "by-author" / "Alice Doe" / "by-year" / "2024" / "classified2024").is_symlink())
        self.assertTrue((views / "by-year" / "2024" / "by-field" / "physics" / "classified2024").is_symlink())
        resolved = (views / "by-field" / "physics" / "by-subfield" / "spin-qubits" / "classified2024").resolve()
        self.assertEqual(resolved, classified.resolve())
        # Flat value link + nested rings, per item: see the anatomy contract.
        self.assertEqual(counts["by-field"], 6)
        self.assertEqual(counts["by-author"], 9)
        self.assertEqual(counts["by-year"], 6)

    def test_edit_adds_and_removes_fields(self) -> None:
        root = self.make_item("editable2025", "10.1000/editable")
        literature.write_info_if_missing(root, "@article{x,\n}\n")
        literature.update_info_classifiers(root, ["physics"])
        with contextlib.redirect_stdout(io.StringIO()):
            literature.command_literature_edit(
                argparse.Namespace(
                    key="editable2025",
                    add_field=[],
                    remove_field=[],
                    add_subfield=["spin-qubits"],
                    remove_subfield=[],
                )
            )
        self.assertEqual(literature.info_fields(root), ["physics"])
        self.assertEqual(literature.info_subfields(root), ["spin-qubits"])

    def test_add_flow_classifies_new_manual_item(self) -> None:
        args = argparse.Namespace(
            source_value="",
            kind="manual",
            key=None,
            project=None,
            no_link=True,
            title="Spin qubit control",
            author="Example, Alex",
            year="2026",
            doi="",
            isbn="",
            arxiv="",
            publisher="",
            url="",
            keyword=["control"],
            entry_type="article",
            field=["physics"],
            subfield=["spin-qubits"],
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            literature.command_literature_add(args)
        created = [path.parent for path in literature.list_item_bibtex_files()]
        self.assertEqual(len(created), 1)
        content = (created[0] / "info.yaml").read_text(encoding="utf-8")
        self.assertIn("fields:\n  - physics", content)
        self.assertIn("subfields:\n  - spin-qubits", content)

    def test_classifier_findings_reports_incompatible_subfield(self) -> None:
        root = self.make_item("invalid2026", "10.1000/invalid")
        literature.write_info_if_missing(root, "@article{x,\n}\n")
        literature.update_info_classifiers(root, ["ai"], ["spin-qubits"])
        self.assertEqual(literature.classifier_findings(), [{
            "severity": "error",
            "id": "invalid2026",
            "message": "subfield(s) do not belong to a selected field: spin-qubits",
        }])


if __name__ == "__main__":
    unittest.main()
