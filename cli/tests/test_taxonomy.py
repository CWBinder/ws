import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import taxonomy


DEFAULTS = {"type": ["research", "other"], "fields": ["physics"]}
HEADER = ["Test header line."]


class TaxonomyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "taxonomy.yaml"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_load_missing_file_returns_defaults_copy(self) -> None:
        data = taxonomy.load(self.path, DEFAULTS)
        self.assertEqual(data, DEFAULTS)
        data["type"].append("mutated")
        self.assertNotIn("mutated", DEFAULTS["type"])

    def test_write_then_load_round_trips(self) -> None:
        taxonomy.write(self.path, {"type": ["a", "b"], "fields": []}, HEADER)
        content = self.path.read_text(encoding="utf-8")
        self.assertIn("# Test header line.", content)
        self.assertIn("type:\n  - a\n  - b", content)
        data = taxonomy.load(self.path, DEFAULTS)
        self.assertEqual(data["type"], ["a", "b"])
        self.assertEqual(data["fields"], ["physics"])

    def test_add_slugs_dedupes_and_appends(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            taxonomy.add(self.path, DEFAULTS, HEADER, "type", "Review Article")
        self.assertIn("added: review-article", out.getvalue())
        self.assertEqual(
            taxonomy.load(self.path, DEFAULTS)["type"],
            ["research", "other", "review-article"],
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            taxonomy.add(self.path, DEFAULTS, HEADER, "type", "review article")
        self.assertIn("exists: review-article", out.getvalue())

    def test_add_rejects_empty_values(self) -> None:
        with self.assertRaises(ValueError):
            taxonomy.add(self.path, DEFAULTS, HEADER, "type", "!!!")

    def test_nested_taxonomy_round_trips_and_adds_children(self) -> None:
        defaults = {
            **DEFAULTS,
            "subfields": {"physics": ["quantum-information"]},
        }
        taxonomy.write(self.path, defaults, HEADER)
        self.assertEqual(taxonomy.load(self.path, defaults), defaults)
        with contextlib.redirect_stdout(io.StringIO()):
            taxonomy.add_nested(
                self.path, defaults, HEADER, "subfields", "Physics", "Spin Qubits"
            )
        self.assertEqual(
            taxonomy.load(self.path, defaults)["subfields"]["physics"],
            ["quantum-information", "spin-qubits"],
        )

    def test_slug_normalizes(self) -> None:
        self.assertEqual(taxonomy.slug("Computer Science"), "computer-science")
        self.assertEqual(taxonomy.slug("  Spin/Qubits  "), "spin-qubits")


if __name__ == "__main__":
    unittest.main()
