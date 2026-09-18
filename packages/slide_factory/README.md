# slide_factory

A reusable python-pptx slide factory: hand content to a few functions, get a
consistently laid-out deck. Themes are switchable; the layout never drifts.

## Quick start

In a ws project, `ws create project my-talk --has-slides` (or
`ws projects install project:my-talk slides`) installs this package into the
project's `.venv`, together with any theme packages named in your ws
configuration. Standalone:

```bash
pip install -e .
python3 demo.py          # builds out/demo/<theme>_demo.pptx for every installed theme
```

```python
from slide_factory import Deck

deck = Deck()                                  # neutral "plain" theme
# deck = Deck(org="My Lab")                    # plain, with a text logotype
# deck = Deck(theme="my_lab")                  # a theme from an installed theme package

deck.title_slide(
    "Modelling Electron Shuttling in Si/SiO2 devices",
    authors=["A. Author", "B. Writer"],
)

deck.outline(["Electrostatics", "Pulse design", "Dynamics"])   # agenda, all bright
deck.next_section()   # before each section: same slide, next section lit,
                      # everything else dimmed (call once per section, in order)

deck.picture_slide(                            # one dominant picture
    "Electrostatics of the shuttling device", "figs/device.png",
    caption="Gate stack cross-section",
    takeaway="Green's functions make electrostatics cheap",
)

deck.two_picture_slide(                        # two pictures side by side
    "Why we want to shuttle?",
    pictures=[("figs/a.png", "Looped pipeline"), ("figs/b.png", "Snakes-on-a-plane")],
    takeaway="Low adiabatic error rates",
    references=["A. Author et al., Journal of Examples 5, 040328 (2023)"],
)

deck.picture_bullets_slide(                    # bullets + picture
    "Modelling framework", "figs/wells.png",
    bullets=[
        "Solve the Poisson equation",
        ("position-dependent permittivity", 1),   # (text, level) = sub-bullet
        "Spectral method with Lanczos",
    ],
    bullets_heading="Electrostatics", picture_side="right",
)

deck.save("talk.pptx")
```

## Slide functions

| Function | Purpose | Key arguments |
|---|---|---|
| `title_slide` | branded opener | `title, subtitle, authors, logo, notes` |
| `outline` | talk outline (numbered section list), remembers the sections | `sections, title, notes` |
| `next_section` | outline reprise: next section lit, the rest dimmed | `notes` |
| `picture_slide` | one dominant picture | `title, picture, caption, takeaway, references, notes` |
| `two_picture_slide` | two pictures side by side | `title, pictures=[(path, caption), ...], takeaway, references, notes` |
| `picture_bullets_slide` | bullets next to a picture | `title, picture, bullets, bullets_heading, caption, picture_side, takeaway, references, notes` |
| `picture_stack_slide` | build-up: pictures appear in the same spot, one per click | `title, pictures=[(path, caption), ...], reveal_first, takeaway, references, notes` |
| `group_stack_slide` | build-up of picture GROUPS: several laid-out pictures + a label appear per click, covering the previous step | `title, steps=[(label, [(path, (fx, fy, fw, fh)), ...]), ...], reveal_first, takeaway, references, notes` |
| `bullets_slide` | full-width text list (no picture) | `title, bullets=[str or (lead, rest), ...], headline, sub, references, notes` |
| `columns_slide` | side-by-side cards of bulleted entries with sub-points and colored tags | `title, columns=[(heading, subheading, [str or card_item(...), ...]), ...], size, card_h, weights, legend, references, notes` |
| `timeline_slide` | month axis: deadline milestones above, work bars below | `title, months, milestones=[(pos, date, text), ...], spans=[(start, end, text, hot), ...], subtitle, aside, footnote, notes` |
| `chain_slide` | horizontal flow chain (or plain row with `arrows=False`) | `title, nodes, hot, headline, sub, footnote, arrows, notes` |
| `vchain_slide` | vertical flow chain | `title, nodes, hot, headline, notes` |
| `labeled_chains_slide` | labeled comparison rows of chains (old way vs new way) | `title, rows=[(label, nodes, {"hot": (...), "dim": True}), ...], headline, notes` |
| `triangle_slide` | three nodes joined into a triangle + bottom statement | `title, corners, bottom, bottom_sub, notes` |
| `two_cards_slide` | two big numbered cards | `title, cards=[(heading, [lines]), ...], notes` |
| `team_slide` | row of circular headshots (initials medallion when no photo) | `title, people=[(photo_or_None, name, affiliation), ...], closing, notes` |

Shared conventions: `references` (list auto-numbered `[1]…`, or a single
string) go in a white pill in the footer, one per line rather than run
together — a single stacked column for one or two, two columns for more (the
footer grows a row past four). The pill is anchored to the right edge and
sized to the text, so short lists get a small box.
A lone citation renders unnumbered in a snugger pill at slightly larger size;
`takeaway="..."` adds the bold `→ …` line;
`notes` fills speaker notes.
Every function returns the python-pptx slide object for post-tweaking.

Column cards: build entries with `card_item(text, sub=..., tag=...,
tag_color=..., tag_italic=..., muted=...)` (exported from `slide_factory`);
plain strings work too. `weights=[5, 2]` makes unequal cards, `card_h` a
shorter, vertically centered row, and `legend` takes a muted line of text or
a list of `(label, color)` for a colored key. Timeline positions are in
months from the axis start (`3.0` = end of the third month); put
milestones on month boundaries so their stems clear the month labels.

Pictures: every `picture` argument takes a file path (`str` or
`pathlib.Path`) or an open binary file / `io.BytesIO`. Formats: PNG, JPEG,
GIF, BMP, TIFF. Images are fitted into their slot preserving aspect ratio.
Animated GIFs are embedded byte-for-byte and animate in slideshow mode
(static viewers show the first frame).

## Themes

This package is brand-free. It ships one theme:

- `plain` — deep slate-blue, no logo, no organisation name. `Deck(org="My
  Lab")` adds a text logotype, `Deck(logo="logo.png")` an image.

Branded themes (an institute's colors, logos and title-slide motif) live in
separate theme packages, outside this repository. A theme package declares
itself under the `slide_factory.themes` entry-point group; once it is
installed next to slide_factory, `Deck(theme="<its name>")` finds it and
`list_themes()` lists it. See "Adding a theme" below.

Conceptual layouts (chains, cards, triangle, headlines) color their nodes
and headings with the theme's `accent` token, falling back to
`takeaway_color`; the flow arrows and highlighted "hot" nodes use
`primary`. Chain nodes take three styles: plain (accent outline), hot
(primary fill) and dim (for the rejected alternative in comparisons).

`draw.py` also gained `flow_arrow` (chain connector arrows), `line`
(straight connector), `circle_crop` (round headshots) and `formula`
(mathtext lines → transparent PNG via matplotlib, imported lazily).

Logos: a theme may set `default_logo` to an image shipped in its own
package; it is then used on every slide. Dark brand surfaces get an
automatically derived white, transparent version (works even for a logo
saved as JPEG on white). Themes whose logo artwork already contains the
org name set `logo_has_wordmark = True`, which suppresses the drawn
wordmark text next to it; otherwise the logo is paired with the org
wordmark. `Deck(theme=..., logo="other.png")` overrides. A theme with
neither logo nor `org_lines` draws no mark at all.

Title slides are left-anchored: the title/subtitle/authors block flows down
from the upper third, the brand lockup sits bottom-left, and each theme adds
its own motif by overriding `_title_canvas`. Bullet lists use "•" for main points and
"–" for sub-points (`(text, 1)` items).

Animations: `picture_stack_slide` reveals its pictures with click-triggered
"Appear" effects (visible in PowerPoint slideshow mode; static viewers show
the full stack). For custom builds, `appear_on_click(slide, shapes)` from
`slide_factory` animates any shapes on a slide, one click per shape (pass
lists of shapes to reveal several per click).

### Adding a theme

Themes belong in their own small package, not in this one, so that logos and
organisation names never enter the ws repository. A theme package is a
module plus a line of metadata:

```python
# my_themes/__init__.py
from pathlib import Path
from pptx.dml.color import RGBColor
from slide_factory import Theme, register_theme

@register_theme
class MyLab(Theme):
    name = "my_lab"
    primary = RGBColor(0x12, 0x34, 0x56)
    org_lines = ("MY", "LAB")
    default_logo = Path(__file__).parent / "assets" / "my_lab.png"
```

```toml
# pyproject.toml of the theme package
[project.entry-points."slide_factory.themes"]
my_lab = "my_themes"
```

Override color/font tokens, and `_title_canvas`/`org_mark` for a different
composition. `slide_factory.themes` exports the helpers themes need: `mix`
(blend two colors), `logo_white` (white version of a logo for dark
surfaces), `W`/`H`. To have ws install the theme package with every
`--has-slides` project, list it under `slides.themes` in your ws
configuration (see the ws configuration reference).

## Files

- `slide_factory/` — the module (`factory.py` Deck, `themes.py` base theme and `plain`, `draw.py` plumbing)
- `demo.py`, `demo_assets.py` — example decks with generated placeholder figures
- `out/demo/` — output of `demo.py` (ignored by git)

New slide layouts go into `factory.py` and must stay theme-agnostic: take
colors and fonts from `self.theme`, never hard-code a brand.

For agents: `demo.py` is the canonical usage example — mimic it to summarise
a project into slides.
