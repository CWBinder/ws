import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ws_lib import records, yamlish


# A record is only useful if something other than ws can read it. yamlish is
# lenient enough to load what dump_yaml writes even when the output is not
# valid YAML, so these tests parse with PyYAML when it is available — that is
# the reader that catches a scalar which silently terminates its own key.
try:
    import yaml as pyyaml
except ImportError:  # pragma: no cover - PyYAML is not a hard dependency
    pyyaml = None


PLAIN = [
    "https://arxiv.org/abs/2508.00139",
    "project:virtuallab",
    "literature:Doe2025ExampleStudy",
    "10:30 standup",
    "doc_01KZ8YPJ5DKWWQNK783G70QTY5",
    "plain name",
]

NEEDS_QUOTING = [
    "The Virtual Lab: Modelling Electron Shuttling",
    "Poisson Solver Performance: From Jacobi to Multigrid",
    "Overview: Electron Shuttling and 2Q-Gate Fidelity",
    "Trailing colon:",
]


class YamlScalarTests(unittest.TestCase):
    def test_colon_not_followed_by_space_stays_plain(self) -> None:
        # Natural keys and URLs are relation endpoints; quoting them would be
        # its own regression.
        for text in PLAIN:
            with self.subTest(text=text):
                self.assertEqual(records.yaml_scalar(text), text)

    def test_colon_space_is_quoted(self) -> None:
        for text in NEEDS_QUOTING:
            with self.subTest(text=text):
                self.assertTrue(records.yaml_scalar(text).startswith('"'))

    def test_titles_with_subtitles_round_trip(self) -> None:
        for text in PLAIN + NEEDS_QUOTING:
            with self.subTest(text=text):
                document = records.dump_yaml({"name": text})
                self.assertEqual(yamlish.load_mapping(document)["name"], text)
                if pyyaml is not None:
                    self.assertEqual(pyyaml.safe_load(document)["name"], text)

    @unittest.skipIf(pyyaml is None, "PyYAML not installed")
    def test_whole_record_is_valid_yaml(self) -> None:
        record = {
            "schema_version": 1,
            "id": "doc_01KZ8YPJ5DKWWQNK783G70QTY5",
            "kind": "document",
            "name": "The Virtual Lab: Modelling Electron Shuttling",
            "aliases": ["VLab: short form"],
            "path_root": "external",
            "classification": {"type": "presentation"},
        }

        loaded = pyyaml.safe_load(records.dump_yaml(record))

        self.assertEqual(loaded, record)


if __name__ == "__main__":
    unittest.main()
