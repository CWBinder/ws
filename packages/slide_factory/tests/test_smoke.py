"""Smoke test for the shipped slide engine. Needs python-pptx and Pillow, which
live in slides projects rather than in the ws environment, so it skips there:

    <project>/.venv/bin/python -m unittest discover -s packages/slide_factory/tests
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import pptx  # noqa: F401
    from slide_factory import Deck, card_item
    from slide_factory.themes import THEMES
except ImportError:  # pragma: no cover
    Deck = None


@unittest.skipIf(Deck is None, "python-pptx is not installed in this environment")
class SlideFactorySmokeTests(unittest.TestCase):
    def test_default_theme_is_the_neutral_one_and_ships_no_brand(self) -> None:
        deck = Deck()
        self.assertEqual(deck.theme.name, "plain")
        self.assertIsNone(deck.theme.default_logo)
        self.assertEqual(deck.theme.org_lines, ())
        self.assertIn("plain", THEMES)

    def test_text_layouts_build_and_save(self) -> None:
        deck = Deck(org="Example Lab")
        deck.title_slide("Title", authors=["A. Author"])
        deck.bullets_slide("Bullets", [("Lead", "rest"), "plain"])
        deck.columns_slide("Cards", [("A", "sub", [card_item("x", tag="TAG"), "y"]),
                                     ("B", None, ["z"])], weights=[3, 2], legend="key")
        deck.timeline_slide("Plan", ["Sep", "Oct"], [(1.0, "End Sep", "Done")],
                            [(1.0, 2.0, "Next", True)])
        with tempfile.TemporaryDirectory() as tmp:
            path = deck.save(Path(tmp) / "deck.pptx")
            self.assertGreater(path.stat().st_size, 10_000)
        self.assertEqual(len(deck.prs.slides), 4)

    def test_unknown_theme_error_points_to_theme_packages(self) -> None:
        with self.assertRaisesRegex(ValueError, "theme packages"):
            Deck(theme="no-such-theme")


if __name__ == "__main__":
    unittest.main()
