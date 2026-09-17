"""slide_factory — a reusable python-pptx slide factory with switchable themes.

    from slide_factory import Deck, list_themes

    deck = Deck()                       # neutral "plain" theme
    deck.title_slide("My talk", authors=["A. Author"])
    deck.save("talk.pptx")
"""
from .animate import appear_on_click
from .factory import Deck, card_item
from .themes import THEMES, Theme, register_theme


def list_themes() -> list[str]:
    """Built-in themes plus those of installed theme packages."""
    from .themes import load_theme_plugins
    load_theme_plugins()
    return sorted(THEMES)


__all__ = ["Deck", "card_item", "Theme", "THEMES", "register_theme", "list_themes",
           "appear_on_click"]
