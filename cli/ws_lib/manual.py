"""The manual behind `ws help`: hand-written pages, generated surroundings.

Pages are Markdown files under SYSTEM/help, laid out like the command
grammar (contracts/cli.md, Discovery):

    help/ws.md                    the overview, printed by bare `ws help`
    help/<kind plural>.md         one kind: what it is, where it lives
    help/relations.md             the graph layer, read like a kind
    help/<command>.md             one command, e.g. help/create.md
    help/<command>/<word>.md      a deeper command, e.g. help/create/project.md
    help/<topic>.md               anything else, e.g. help/configuration.md

A page carries only what the parser and registry cannot know: what a thing
is, how to work with it, and why. Everything listable is generated around
it when `ws help` prints the page -- the flags, the commands one kind
supports, the deeper pages under a command -- so those lists never drift
from the CLI. Pages refer to each other by `ws help ...` commands, never by
file links, because a terminal cannot follow a link.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from . import paths, registry

# Kind words after these verbs name the kind the command works on. create
# and add take the singular (`ws create project`), list and search the plural.
SINGULAR_AFTER = {"create", "add"}
PLURAL_AFTER = {"list", "search"}

# The order kinds appear in the overview's list of manuals.
KIND_ORDER = (
    "project", "task", "document", "resource", "literature",
    "person", "organisation", "event", "profile",
)

HELP_REFERENCE = re.compile(r"`ws help((?: [a-z][a-z0-9-]*)+)`")
MARKDOWN_LINK = re.compile(r"\]\([^)]*\)")


def help_dir() -> Path:
    return paths.SYSTEM / "help"


def kind_page_word(word: str) -> str | None:
    """The page name for a kind word in either number, or for the graph."""
    if word in ("relation", "relations"):
        return "relations"
    kind = registry.KIND_OF_WORD.get(word)
    return registry.KIND_PLURALS[kind] if kind else None


def page_words(words: tuple[str, ...]) -> tuple[str, ...]:
    """The page path for a typed command path: kind words are spelled the
    way the page tree spells them, so `ws help create projects` and
    `ws help create project` read the same page."""
    if len(words) == 1:
        return (kind_page_word(words[0]) or words[0],)
    if len(words) >= 2 and words[0] in SINGULAR_AFTER | PLURAL_AFTER:
        kind = registry.KIND_OF_WORD.get(words[1])
        if kind:
            word = kind if words[0] in SINGULAR_AFTER else registry.KIND_PLURALS[kind]
            return (words[0], word, *words[2:])
    return words


def page_file(words: tuple[str, ...]) -> Path:
    if not words:
        return help_dir() / "ws.md"
    return help_dir().joinpath(*words[:-1]) / f"{words[-1]}.md"


def read_page(words: tuple[str, ...]) -> str | None:
    path = page_file(words)
    return path.read_text(encoding="utf-8").strip() if path.is_file() else None


def _kind_of_path(words: tuple[str, ...]) -> str | None:
    """The kind a command path is about, as its page name, if any."""
    for word in words:
        page = kind_page_word(word)
        if page:
            return page
    return None


def _command_rows(records: list[dict]) -> list[tuple[str, str]]:
    return [
        (record["command"], registry._first_sentence(record.get("purpose") or ""))
        for record in records
    ]


def _rows_block(title: str, rows: list[tuple[str, str]]) -> str:
    width = min(max((len(left) for left, _ in rows), default=0) + 2, 46)
    lines = [f"## {title}", ""]
    for left, right in rows:
        if right and len(left) < width:
            lines.append(f"  {left:<{width}}{right}")
        elif right:
            lines.append(f"  {left}\n  {'':<{width}}{right}")
        else:
            lines.append(f"  {left}")
    return "\n".join(lines)


def _child_rows(parser: argparse.ArgumentParser, words: tuple[str, ...]) -> list[tuple[str, str]]:
    """One row per deeper command under a parser, with its one-line help."""
    rows = []
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        seen: set[int] = set()
        helps = {choice.dest: choice.help or "" for choice in action._choices_actions}
        for name, child in action.choices.items():
            if name.startswith("__") or id(child) in seen:
                continue
            if registry.is_compatibility_path((*words, name)):
                continue
            seen.add(id(child))
            rows.append((f"ws help {' '.join((*words, name))}", helps.get(name, "")))
    return rows


def kind_page(root: argparse.ArgumentParser, word: str) -> str:
    """A kind's page: the hand-written body, then every command for it."""
    body = read_page((word,))
    if word == "relations":
        records = registry.relation_capability_records(root)
    else:
        records = registry.kind_capability_records(root, word) or []
    sections = [body] if body else []
    sections.append(_rows_block("Commands", _command_rows(records)))
    sections.append(
        "Each command has its own page: `ws help` followed by the command, "
        "e.g. `ws help " + _example_command(records) + "`."
    )
    return "\n\n".join(sections)


def _example_command(records: list[dict]) -> str:
    for record in records:
        words = record["command"].split()[1:]
        if words and all(re.fullmatch(r"[a-z][a-z0-9-]*", word) for word in words):
            return " ".join(words)
    return "show"


def command_page(root: argparse.ArgumentParser, words: tuple[str, ...]) -> str | None:
    """A command's page: the body, the parser's own help, the deeper pages
    under it, and a pointer to the page of the kind it works on."""
    parser = registry.resolve_parser(root, words)
    body = read_page(page_words(words))
    if parser is None:
        return body
    sections = [body] if body else []
    sections.append("## Usage\n\n" + parser.format_help().rstrip())
    children = _child_rows(parser, words)
    if children:
        sections.append(_rows_block("More help", children))
    kind = _kind_of_path(words)
    if kind:
        sections.append(f"About {kind}: `ws help {kind}`")
    return "\n\n".join(sections)


def topic_rows(root: argparse.ArgumentParser) -> list[tuple[str, str]]:
    """Top-level pages that are neither a kind nor a command: topics."""
    rows = []
    commands = registry._subcommands(root)
    for path in sorted(help_dir().glob("*.md")):
        word = path.stem
        if word == "ws" or kind_page_word(word) or word in commands:
            continue
        rows.append((f"ws help {word}", _title_of(path)))
    return rows


def first_words(root: argparse.ArgumentParser) -> list[str]:
    """What may follow `ws help`: kinds, the graph, topics and commands."""
    words = {registry.KIND_PLURALS[kind] for kind in KIND_ORDER} | {"relations"}
    words |= {row[0].split()[-1] for row in topic_rows(root)}
    words |= {
        name for name in registry._subcommands(root)
        if not name.startswith("__") and not registry.is_compatibility_path((name,))
    }
    return sorted(words)


def _title_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def overview(root: argparse.ArgumentParser) -> str:
    """Bare `ws help`: the overview text, the map, then every manual."""
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        registry.print_overview(manual_pointer=False)
    sections = []
    body = read_page(())
    if body:
        sections.append(body)
    sections.append("## Map\n\n" + buffer.getvalue().rstrip())
    kinds = " ".join(registry.KIND_PLURALS[kind] for kind in KIND_ORDER)
    rows = [("ws help <kind>", "one kind: what it is, where it lives, its commands")]
    rows.append(("", kinds))
    rows.append(("ws help relations", "the edges between objects"))
    rows.extend(topic_rows(root))
    rows.append(("ws help <command>", "one command in full, e.g. ws help create project"))
    sections.append(_rows_block("Manuals", rows))
    return "\n\n".join(sections)


def render(root: argparse.ArgumentParser, words: tuple[str, ...]) -> str | None:
    """The full text `ws help WORDS` prints, or None for an unknown path."""
    if not words:
        return overview(root)
    if len(words) == 1:
        kind = kind_page_word(words[0])
        if kind:
            return kind_page(root, kind)
    return command_page(root, words)


def guide_for(words: list[str]) -> str:
    """The page that documents a command, relative to SYSTEM: the most
    specific page on its path, else its kind's page, else the overview."""
    typed = page_words(tuple(words))
    for length in range(len(typed), 0, -1):
        if page_file(typed[:length]).is_file():
            return page_file(typed[:length]).relative_to(paths.SYSTEM).as_posix()
    kind = _kind_of_path(tuple(words))
    if kind and page_file((kind,)).is_file():
        return page_file((kind,)).relative_to(paths.SYSTEM).as_posix()
    return page_file(()).relative_to(paths.SYSTEM).as_posix()


def findings(root: argparse.ArgumentParser) -> list[dict]:
    """The page rules (contracts/cli.md): every page belongs to a kind, a
    command or a topic; every page names its subject in a title; pages refer
    to each other by `ws help ...`, never by file link, and every such
    reference resolves."""
    rows: list[dict] = []

    def problem(path: Path, message: str) -> None:
        rel = path.relative_to(paths.SYSTEM).as_posix()
        rows.append({"severity": "error", "message": f"{rel}: {message}"})

    base = help_dir()
    if not base.is_dir():
        return [{"severity": "error", "message": "help/: the manual is missing"}]
    for path in sorted(base.rglob("*.md")):
        words = path.relative_to(base).with_suffix("").parts
        text = path.read_text(encoding="utf-8")
        if len(words) > 1 and registry.resolve_parser(root, words) is None:
            problem(path, f"no command `ws {' '.join(words)}` for this page to document")
        if not any(line.startswith("# ") for line in text.splitlines()):
            problem(path, "no `# ` title line")
        if MARKDOWN_LINK.search(text):
            problem(path, "file link; refer to other pages as `ws help ...`")
        for match in HELP_REFERENCE.finditer(text):
            target = tuple(match.group(1).split())
            if render(root, target) is None:
                problem(path, f"`ws help{match.group(1)}` resolves to nothing")
    return rows
