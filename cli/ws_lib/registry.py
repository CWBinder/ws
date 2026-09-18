from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class NamespaceSpec:
    name: str
    kind: str
    purpose: str
    contract: str


@dataclass(frozen=True)
class EffectSpec:
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    relations: tuple[str, ...] = ()
    external: tuple[str, ...] = ()
    destructive: bool = False


DOMAINS = {
    item.name: item
    for item in (
        NamespaceSpec("projects", "domain", "Structured project workspaces.", "contracts/projects.md"),
        NamespaceSpec("tasks", "domain", "Structured actionable work.", "contracts/tasks.md"),
        NamespaceSpec("literature", "domain", "Canonical scholarly literature database.", "contracts/literature.md"),
        NamespaceSpec("documents", "domain", "Canonical document catalogue.", "contracts/documents.md"),
        NamespaceSpec("resources", "domain", "Folder-backed bundles of supporting files.", "contracts/resources.md"),
        NamespaceSpec("logistics", "domain", "People, organisations, events, and communication assets.", "contracts/logistics.md"),
        NamespaceSpec("profile", "domain", "Personal profile and generated career material.", "contracts/profile.md"),
    )
}

# The four categories of global commands (contracts/cli.md): every command
# that is not a domain specialist belongs to exactly one. An uncategorised
# command is a defect in the model, not a harmless omission.
CATEGORIES = {
    "objects": "Work on single objects and their edges: the CRUD verbs.",
    "search": "Find things: collection queries and reference lookup.",
    "maintenance": "Keep the derived layers coherent: index, wiki, validation.",
    "discovery": "Learn the command surface from the CLI itself.",
}

# Verb-first commands take their category here; namespace commands carry
# theirs on their NamespaceSpec (the `kind` field names the category).
VERB_CATEGORIES = {
    "create": "objects",
    "add": "objects",
    "show": "objects",
    "edit": "objects",
    "delete": "objects",
    "relate": "objects",
    "unrelate": "objects",
    "list": "search",
    "search": "search",
}

GLOBAL_NAMESPACES = {
    item.name: item
    for item in (
        NamespaceSpec("init", "maintenance", "Initialise an empty workspace and remember its location.", "contracts/workspace.md"),
        NamespaceSpec("index", "maintenance", "Maintain the derived search index.", "contracts/search.md"),
        NamespaceSpec("wiki", "maintenance", "Build the derived Obsidian/wiki view.", "contracts/wiki.md"),
        NamespaceSpec("check", "maintenance", "Validate workspace state and contracts.", "contracts/check.md"),
        NamespaceSpec("id", "search", "Resolve and inspect canonical references.", "contracts/objects.md"),
        NamespaceSpec("help", "discovery", "How to type one command.", "contracts/cli.md"),
        NamespaceSpec("capabilities", "discovery", "Which commands exist.", "contracts/cli.md"),
        NamespaceSpec("describe", "discovery", "What one command does and touches.", "contracts/cli.md"),
        NamespaceSpec("completions", "discovery", "Generate shell completions.", "contracts/cli.md"),
        NamespaceSpec("domains", "discovery", "List the domains that own objects.", "contracts/cli.md"),
    )
}


# The graph layer: not a domain (edges are not objects and belong to no
# kind), and not recoverable either — a hand-asserted edge exists nowhere
# else and cannot be regenerated. Its commands (`ws relations`, `ws
# relations edit`) do object-and-edge work, so they file under the objects
# category while the store keeps its own layer and contract.
GRAPH = {
    item.name: item
    for item in (
        NamespaceSpec("relations", "graph", "Canonical edges between objects.", "contracts/relations.md"),
    )
}


EFFECTS: dict[str, EffectSpec] = {
    "init": EffectSpec(
        reads=("existing workspace files and local configuration", "shipped defaults"),
        writes=("missing workspace directories, taxonomies, browse settings and orientation files", "local ws configuration workspace_root", "initial search index when absent"),
    ),
    "projects create": EffectSpec(
        reads=("project taxonomy", "project templates"),
        writes=("projects/items/<slug>/",),
        relations=("creates depends-on/related/references edges for declared links; install dependencies are recorded as project_dependencies facts",),
    ),
    "projects create-subproject": EffectSpec(
        reads=("parent project metadata",),
        writes=("projects/items/<parent>/<slug>/",),
    ),
    "projects install": EffectSpec(
        reads=("projects/items/<slug>/project.yaml", "dependency projects' package_install recipes", "packages/slide_factory in the ws checkout", "slides.themes in the ws configuration"),
        writes=(
            "projects/items/<slug>/project.yaml (capability flags, runtime, project_dependencies)",
            "capability folders, pyproject.toml, and .venv/ inside the project",
        ),
        relations=("creates depends-on edges for newly recorded --use-project dependencies",),
        external=("pip install -e for package dependencies, the slide generator and configured slide theme packages",),
    ),
    "tasks create": EffectSpec(writes=("tasks/<key>.yaml",)),
    "documents add": EffectSpec(
        reads=("source file", "documents/document-taxonomy.yaml"),
        writes=(
            "documents/items/<id>.yaml",
            "documents/files/<filename> with --mode copy|move",
            "documents/by-*/ derived symlinks",
            "documents/document-taxonomy.yaml when a new type is confirmed",
        ),
        destructive=True,
    ),
    "documents types add": EffectSpec(
        reads=("documents/document-taxonomy.yaml",),
        writes=("documents/document-taxonomy.yaml",),
    ),
    "documents types rename": EffectSpec(
        reads=(
            "documents/document-taxonomy.yaml",
            "documents/items/*.yaml",
        ),
        writes=(
            "documents/document-taxonomy.yaml",
            "matching documents/items/*.yaml",
        ),
        destructive=True,
    ),
    "documents types remove": EffectSpec(
        reads=(
            "documents/document-taxonomy.yaml",
            "documents/items/*.yaml",
        ),
        writes=("documents/document-taxonomy.yaml",),
        destructive=True,
    ),
    "projects views rebuild": EffectSpec(
        reads=(
            "folder-anatomy.yaml",
            "projects/items/*/project.yaml",
            "relations/*.yaml",
        ),
        writes=("projects/by-*/",),
        destructive=True,
    ),
    "documents views rebuild": EffectSpec(
        reads=("folder-anatomy.yaml", "documents/items/*.yaml", "relations/*.yaml"),
        writes=("documents/by-*/",),
        destructive=True,
    ),
    "resources create": EffectSpec(writes=("resources/items/<key>/resource.yaml",)),
    "resources add": EffectSpec(
        reads=("supplied file or folder",),
        writes=("resources/items/<key>/<name>",),
    ),
    "documents delete": EffectSpec(
        reads=("documents/items/<key>.yaml", "relations/*.yaml"),
        writes=(
            "removes the record and every relation touching it",
            "moves the managed file to ~/.Trash",
            "documents/by-*/ derived symlinks",
        ),
        destructive=True,
    ),
    "resources delete": EffectSpec(
        reads=("resources/items/<key>/", "relations/*.yaml"),
        writes=(
            "removes every relation touching the resource",
            "moves the whole folder, record included, to ~/.Trash",
        ),
        destructive=True,
    ),
    "tasks delete": EffectSpec(
        reads=("tasks/<key>.yaml", "relations/*.yaml"),
        writes=("removes the record and every relation touching it",),
        destructive=True,
    ),
    "resources views rebuild": EffectSpec(
        reads=("folder-anatomy.yaml", "resources/items/*/resource.yaml", "relations/*.yaml"),
        writes=("resources/by-*/",),
        destructive=True,
    ),
    "literature add": EffectSpec(
        reads=("provider metadata or local BibTeX",),
        writes=(
            "literature/items/<ItemKey>/",
            "literature/items/<ItemKey>/info.yaml field/subfield classifiers",
        ),
        external=("Crossref/arXiv/Open Library when the identifier requires lookup",),
    ),
    "literature edit": EffectSpec(
        reads=("literature/items/<ItemKey>/info.yaml", "shared field/subfield taxonomy"),
        writes=("literature/items/<ItemKey>/info.yaml",),
    ),
    "projects add-subfield": EffectSpec(
        reads=("projects/project-taxonomy.yaml",),
        writes=("projects/project-taxonomy.yaml",),
    ),
    "literature add-subfield": EffectSpec(
        reads=("projects/project-taxonomy.yaml",),
        writes=("projects/project-taxonomy.yaml",),
    ),
    "literature download-source": EffectSpec(
        reads=("literature/items/<ItemKey>/citation.bib",),
        writes=(
            "literature/items/<ItemKey>/source/arxiv/citation.bib",
            "literature/items/<ItemKey>/source/arxiv/source.tar",
            "literature/items/<ItemKey>/source/arxiv/files/",
        ),
        external=("arXiv API and e-print download",),
    ),
    "literature views rebuild": EffectSpec(
        reads=(
            "folder-anatomy.yaml",
            "literature/items/*/citation.bib",
            "literature/items/*/info.yaml",
        ),
        writes=("literature/by-*/",),
        destructive=True,
    ),
    "profile init": EffectSpec(
        writes=(
            "profile/items/",
            "profile/applications/",
            "profile/profile-taxonomy.yaml",
            "profile/README.md",
        ),
    ),
    "profile create": EffectSpec(
        reads=("profile/profile-taxonomy.yaml",),
        writes=("profile/items/<id>.yaml", "profile/by-type/"),
    ),
    "profile edit": EffectSpec(
        reads=("profile/items/<id>.yaml",),
        writes=("profile/items/<id>.yaml", "profile/by-type/"),
    ),
    "profile add-type": EffectSpec(
        reads=("profile/profile-taxonomy.yaml",),
        writes=("profile/profile-taxonomy.yaml",),
    ),
    "profile views rebuild": EffectSpec(
        reads=("folder-anatomy.yaml", "profile/items/*.yaml"),
        writes=("profile/by-type/",),
        destructive=True,
    ),
    "profile make-cv": EffectSpec(
        reads=(
            "profile/items/*.yaml",
            "related literature citation.bib files",
            "the requested --spec YAML file, when supplied",
        ),
        writes=(
            "<requested-output>/<name>.tex",
            "<requested-output>/<name>.pdf unless --no-build",
            "<requested-output>/out/ LaTeX artifacts unless --no-build",
        ),
    ),
    "logistics people add": EffectSpec(writes=("logistics/people/<id>.yaml",)),
    "logistics organisations add": EffectSpec(writes=("logistics/organisations/<id>.yaml",)),
    "logistics events add": EffectSpec(writes=("logistics/events/<id>.yaml",)),
    "show": EffectSpec(
        reads=("the referenced records", "relations/*.yaml for `show relations of`"),
    ),
    "list": EffectSpec(
        reads=("the named kind's records; every kind when bare",),
    ),
    "create": EffectSpec(
        writes=("a new record of the named kind",),
    ),
    "add": EffectSpec(
        writes=("a new record of the named kind; document files move into the workspace",),
    ),
    "edit": EffectSpec(
        reads=("the referenced record",),
        writes=("the referenced record",),
    ),
    "delete": EffectSpec(
        reads=("the referenced records", "relations/*.yaml"),
        writes=(
            "removes records and every relation touching them",
            "moves document files and resource folders to ~/.Trash",
        ),
        destructive=True,
    ),
    "relate": EffectSpec(writes=("relations/<id>.yaml",)),
    "unrelate": EffectSpec(
        writes=("relations/<id>.yaml",), destructive=True
    ),
    "relations edit": EffectSpec(writes=("relations/<id>.yaml",)),
    "search": EffectSpec(reads=("derived index/index.sqlite",)),
    "wiki build": EffectSpec(
        reads=("all canonical domain data", "relations"),
        writes=("wiki/generated/",),
    ),
}

# `ws create subproject` is the only registered spelling; it shares the
# home-keyed entry the same way the other hoisted spellings do.
EFFECTS["create subproject"] = EFFECTS["projects create-subproject"]

COMPATIBILITY_PATHS = {
    "create agent",
    "create subagent",
}


HOISTED_KIND_HOMES = {
    "document": ("documents",),
    "documents": ("documents",),
    "person": ("logistics", "people"),
    "people": ("logistics", "people"),
    "organisation": ("logistics", "organisations"),
    "organisations": ("logistics", "organisations"),
    "organizations": ("logistics", "organisations"),
    "event": ("logistics", "events"),
    "events": ("logistics", "events"),
    "literature": ("literature",),
    "task": ("tasks",),
    "tasks": ("tasks",),
    "resource": ("resources",),
    "resources": ("resources",),
    "profile": ("profile",),
    "project": ("projects",),
    "projects": ("projects",),
}

# The kind behind each accepted kind word, and each kind's listing word.
KIND_OF_WORD = {
    "document": "document", "documents": "document",
    "person": "person", "people": "person",
    "organisation": "organisation", "organisations": "organisation",
    "organizations": "organisation",
    "event": "event", "events": "event",
    "literature": "literature",
    "task": "task", "tasks": "task",
    "resource": "resource", "resources": "resource",
    "profile": "profile",
    "project": "project", "projects": "project",
}
KIND_PLURALS = {
    "document": "documents",
    "person": "people",
    "organisation": "organisations",
    "event": "events",
    "literature": "literature",
    "task": "tasks",
    "resource": "resources",
    "profile": "profile",
    "project": "projects",
}

# The hand-curated kinds keep their limits (objects.md, Acting on objects):
# show renders every REF, projects have no edit, and neither projects nor
# literature can be deleted.
REF_TOOL_EXCEPTIONS = {
    "edit": {"project"},
    "delete": {"project", "literature"},
}

VERB_CONTRACTS = {
    "show": "contracts/objects.md",
    "edit": "contracts/objects.md",
    "delete": "contracts/objects.md",
    "list": "contracts/objects.md",
    "create": "contracts/objects.md",
    "add": "contracts/objects.md",
    "search": "contracts/search.md",
    "relate": "contracts/relations.md",
    "unrelate": "contracts/relations.md",
    # The CLI's own discovery surface is specified in the CLI contract.
    "help": "contracts/cli.md",
    "capabilities": "contracts/cli.md",
    "describe": "contracts/cli.md",
    "domains": "contracts/cli.md",
}


def canonical_command_path(path: list[str]) -> list[str]:
    """Map a hoisted spelling (`add document`, `list tasks`, `create project`)
    onto the domain spelling that carries the contract and effects."""
    if len(path) >= 2 and path[0] in {"add", "create", "list", "search"}:
        home = HOISTED_KIND_HOMES.get(path[1])
        if home:
            return [*home, path[0], *path[2:]]
    return path


UNIVERSAL_VERBS = (
    "create",
    "add",
    "show",
    "edit",
    "delete",
    "list",
    "search",
    "relate",
    "unrelate",
)

# A flag with the same name means the same thing on every command
# (contracts/cli.md, Templates and placeholders). Defined once here;
# finalize_help() fills these in wherever a registration left the help empty.
STANDARD_OPTION_HELP = {
    "--json": "print JSON instead of lines",
    "--dry-run": "preview without changing anything",
    "--force": "replace what is already there",
    "--ensure": "reuse the matching existing object instead of creating a duplicate",
    "--alias": "alternative name; repeatable",
    "--description": "one-line description",
    "--status": "lifecycle status word",
    "--source": "provenance: who or what asserted this",
    "--observed-at": "provenance: when this was observed (ISO date)",
    "--limit": "show at most this many rows",
    "--max": "maximum number of results",
    "--as": "the edge's relation words (e.g. works-at)",
    "--from": "edge validity start (ISO date)",
    "--until": "edge validity end (ISO date)",
    "--start": "start date (ISO)",
    "--end": "end date (ISO)",
    "--timezone": "IANA timezone (e.g. Europe/London)",
    "--location": "place name",
    "--website": "website URL",
    "--email": "email address",
    "--phone": "phone number",
    "--preferred-name": "preferred form of address",
    "--due": "due date (YYYY-MM-DD); empty means none",
    "--priority": "task priority word",
    "--tag": "free-form tag; repeatable",
    "--keyword": "keyword; repeatable",
    "--type": "classifier type; the kind's `taxonomy` command lists the allowed values",
    "--field": "broad classifier field; see the kind's `taxonomy`",
    "--subfield": "narrower classifier within the chosen field",
    "--title": "title",
    "--author": "author list as written in the citation",
    "--year": "publication year",
    "--doi": "DOI",
    "--isbn": "ISBN",
    "--publisher": "publisher",
    "--volume": "journal volume",
    "--url": "URL",
    "--arxiv": "arXiv identifier",
    "--venue": "publication or event venue",
    "--orcid": "ORCID identifier",
}

# The placeholder lexicon (contracts/cli.md): one metavar and one meaning per
# operand name. Commands whose operand is genuinely their own set it at the
# registration site instead.
STANDARD_POSITIONAL = {
    "title": ("TITLE", "human title; words are joined, quotes optional"),
    "name": ("NAME", "human name; words are joined, quotes optional"),
    "value": ("VALUE", "the value to add to the taxonomy"),
    "field": ("FIELD", "the broad field this value belongs under"),
    "type": ("TYPE", "type id from the taxonomy"),
    "skill": ("SKILL", "skill name; `ws agents list` shows them"),
    "query": ("QUERY", "query words; quotes optional"),
    "question": ("QUESTION", "the question to research; quotes optional"),
    "shell": ("SHELL", "shell to generate completions for"),
    "file": ("FILE", "file to ingest into the workspace"),
    "path": ("PATH", "filesystem path"),
    "source_value": (
        "IDENTIFIER",
        "DOI, arXiv id, or ISBN; omit with --manual to enter metadata by hand",
    ),
    "relation_id": ("RELATION_ID", "relation id from `ws show relations of REF`"),
    "resource": ("REF", "canonical resource:<key> reference"),
    "roots": ("ROOT", "folders to sync into; defaults to the configured roots"),
}


def finalize_help(root: argparse.ArgumentParser) -> None:
    """Apply the content rules of contracts/cli.md at build time: a command
    whose registration gave only a parent `help=` line inherits it as its
    description, and shared flags get their one registry-defined meaning."""
    seen: set[int] = set()

    def walk(parser: argparse.ArgumentParser) -> None:
        if id(parser) in seen:
            return
        seen.add(id(parser))
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                helps = {
                    pseudo.dest: pseudo.help
                    for pseudo in action._choices_actions
                    if pseudo.help and pseudo.help != argparse.SUPPRESS
                }
                for name, child in action.choices.items():
                    text = helps.get(name, "")
                    if text and not (child.description or "").strip():
                        text = text.strip().rstrip(".")
                        child.description = text[0].upper() + text[1:] + "."
                    walk(child)
            elif action.option_strings:
                if not (action.help or "").strip():
                    for option in action.option_strings:
                        if option in STANDARD_OPTION_HELP:
                            action.help = STANDARD_OPTION_HELP[option]
                            break
            else:
                standard = STANDARD_POSITIONAL.get(action.dest)
                if standard:
                    metavar, text = standard
                    if not action.metavar:
                        action.metavar = metavar
                    if not (action.help or "").strip():
                        action.help = text

    walk(root)


def _retired_spellings(text: str) -> list[str]:
    """Spellings that no longer parse. Help that teaches one is a wrong
    instruction, not a cosmetic slip, so `ws check cli` fails on it."""
    generic = "create|add|list|search|show|edit|delete"
    patterns = (
        rf"\bws (?:documents|tasks|resources|profile|projects|literature)"
        rf" (?:{generic})\b(?![-\w])",
        rf"\bws (?:people|organisations|organizations|events|person|organisation"
        rf"|event|task|document|career) (?:{generic}|ensure|merge)\b",
        r"\bws logistics (?:people|organisations|events) "
        rf"(?:{generic})\b",
        r"\bws relations show\b",
    )
    return [m.group(0) for pattern in patterns for m in re.finditer(pattern, text)]


FLAG_POSITION_HINT = (
    "flags come after the command and its operands: "
    "`ws <verb> <kind> <operands> --flag value`"
)


def _flag_precedes_a_bare_word(argv: list[str]) -> bool:
    """True when a --flag (with its value) is followed by a further bare word
    -- `ws list --type abstract documents`, the shape argparse mis-parses."""
    seen_flag = False
    for index, token in enumerate(argv):
        if token.startswith("-") and token != "-":
            seen_flag = True
            continue
        previous = argv[index - 1] if index else ""
        if seen_flag and not (previous.startswith("-") and previous != "-"):
            return True
    return False


def _option_arity(parser: argparse.ArgumentParser) -> dict[str, int | None]:
    """How many values each option of this parser consumes. None means
    variable (`*`, `+`, REMAINDER), where counting cannot be trusted."""
    arity: dict[str, int | None] = {}
    for action in parser._actions:
        if not action.option_strings:
            continue
        if action.nargs is None:
            count: int | None = 1
        elif action.nargs in (0, argparse.REMAINDER, "*", "+", "?"):
            count = 0 if action.nargs == 0 else None
        elif isinstance(action.nargs, int):
            count = action.nargs
        else:
            count = None
        if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction,
                               argparse._CountAction, argparse._HelpAction)):
            count = 0
        for option in action.option_strings:
            arity[option] = count
    return arity


def _is_flag(token: str) -> bool:
    return token.startswith("-") and token not in ("-", "--")


def reorder_flags_last(argv: list[str], arity: dict[str, int | None]) -> list[str]:
    """The same command written in house style, for the error message."""
    head, tail, index = [], [], 0
    while index < len(argv):
        token = argv[index]
        if _is_flag(token):
            tail.append(token)
            if "=" not in token:
                take = arity.get(token, 1) or 0
                tail.extend(argv[index + 1: index + 1 + take])
                index += take
        else:
            head.append(token)
        index += 1
    return head + tail


def enforce_flags_last(root: argparse.ArgumentParser, argv: list[str]) -> None:
    """Flags come last, without exception (contracts/cli.md, Where flags go).

    Deliberately conservative: anything the parser cannot account for -- an
    unknown option, a variable-arity one -- ends the check rather than
    risking a false rejection of a working command."""
    parser, index = root, 0
    while index < len(argv) and not _is_flag(argv[index]):
        child = _subcommands(parser).get(argv[index])
        if child is None:
            break
        parser, index = child, index + 1
    if any(
        isinstance(action, argparse._SubParsersAction) is False
        and action.nargs == argparse.REMAINDER
        for action in parser._actions
    ):
        # `ws edit REF --flags` hands everything after the REF to another
        # parser; that parser enforces its own shape.
        return
    arity = _option_arity(parser)
    rest = argv[index:]
    position, seen_flag = 0, False
    while position < len(rest):
        token = rest[position]
        if _is_flag(token):
            if token not in arity:
                # Unknown here, but a later word naming a subcommand means the
                # flag was typed before the command it belongs to.
                children = _subcommands(parser)
                later = next(
                    (word for word in rest[position + 1:]
                     if not _is_flag(word) and word in children),
                    "",
                )
                if later:
                    parser.error(
                        f"flags come last, so '{later}' cannot follow a flag; "
                        f"'{later}' names the command that owns {token}\n"
                        f"hint: {FLAG_POSITION_HINT}\n"
                        f"try: ws {' '.join(argv[:index])} {later} "
                        f"{' '.join(w for w in rest if w != later)}".replace("  ", " ")
                    )
                return
            take = arity[token]
            if take is None:
                return
            seen_flag = True
            if "=" not in token:
                position += take
        elif seen_flag:
            fixed = " ".join(["ws", *argv[:index], *reorder_flags_last(rest, arity)])
            catalog_fail = getattr(parser, "error")
            catalog_fail(
                f"flags come last, so '{token}' cannot follow a flag\n"
                f"hint: {FLAG_POSITION_HINT}\n"
                f"try: {fixed}"
            )
        position += 1


def install_flag_position_hints(root: argparse.ArgumentParser) -> None:
    """argparse reports a misplaced flag as `unrecognized arguments` or an
    `invalid choice`, neither of which names the real mistake. Add the house
    rule to those two messages, and only when the argv actually has that
    shape (contracts/cli.md, Where flags go)."""
    seen: set[int] = set()

    def wrap(parser: argparse.ArgumentParser) -> None:
        if id(parser) in seen:
            return
        seen.add(id(parser))
        original = parser.error

        def error(message: str, _original=original) -> None:
            misplaced = message.startswith("unrecognized arguments") or (
                "invalid choice" in message
            )
            if misplaced and _flag_precedes_a_bare_word(sys.argv[1:]):
                message = f"{message}\nhint: {FLAG_POSITION_HINT}"
            _original(message)

        parser.error = error  # type: ignore[method-assign]
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    wrap(child)

    wrap(root)


# Where each shell keeps the completion script `ws completions` generates.
INSTALLED_COMPLETIONS = {
    "zsh": Path.home() / ".zfunc" / "_ws",
    "bash": Path.home() / ".local" / "share" / "bash-completion" / "completions" / "ws",
}


def completion_findings(generated: dict[str, str]) -> list[dict]:
    """An installed completion script is a copy, and a copy drifts. The
    grammar changed under this file for a month before anyone noticed, so
    compare it the way `ws agents sync` compares installed roles."""
    rows: list[dict] = []
    for shell, path in INSTALLED_COMPLETIONS.items():
        if not path.exists():
            continue
        try:
            installed = path.read_text(encoding="utf-8")
        except OSError as exc:
            rows.append({"severity": "warning", "message": f"cannot read {path}: {exc}"})
            continue
        if installed != generated.get(shell, ""):
            rows.append({
                "severity": "error",
                "message": (
                    f"{shell} completion is stale: {path}; "
                    f"refresh with `ws completions {shell} > {path}`"
                ),
            })
    return rows


def cli_findings(root: argparse.ArgumentParser) -> list[dict]:
    """Enforce the help/describe content rules (contracts/cli.md): every
    command described, every visible argument helped, every positional a
    placeholder, every command under a contract, every writer with its own
    effects entry."""
    findings: list[dict] = []

    def problem(path: str, message: str) -> None:
        findings.append({"severity": "error", "message": f"ws {path}: {message}"})

    seen: set[int] = set()
    for path, parser in leaf_commands(root):
        if id(parser) in seen:
            continue
        seen.add(id(parser))
        words = path.split()
        if not (parser.description or "").strip():
            problem(path, "no description (say what the command does)")
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                continue
            if action.help == argparse.SUPPRESS:
                continue
            if action.option_strings:
                if {"-h", "--help"} & set(action.option_strings):
                    continue
                if not (action.help or "").strip():
                    problem(path, f"flag {action.option_strings[-1]} has no help text")
            else:
                if not (action.help or "").strip():
                    problem(path, f"positional '{action.dest}' has no help text")
                metavar = str(action.metavar or "")
                if not metavar or not metavar.isupper():
                    problem(
                        path,
                        f"positional '{action.dest}' needs an UPPERCASE placeholder metavar",
                    )
        for spelling in sorted(set(_retired_spellings(parser.format_help()))):
            problem(path, f"help teaches a retired spelling: `{spelling}`")
        record = command_record(root, words)
        if not record["contract"]:
            problem(path, "resolves to no contract")
        canonical = " ".join(canonical_command_path(words))
        fallback = EFFECTS.get(words[0])
        if (
            len(words) > 1
            and canonical not in EFFECTS
            and fallback is not None
            and fallback.writes
        ):
            problem(path, f"writing command relies on the generic '{words[0]}' effects entry")
    return findings


def is_compatibility_path(path: tuple[str, ...]) -> bool:
    text = " ".join(path)
    return any(text == item or text.startswith(item + " ") for item in COMPATIBILITY_PATHS)


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def resolve_parser(
    parser: argparse.ArgumentParser, path: Iterable[str]
) -> argparse.ArgumentParser | None:
    current = parser
    for part in path:
        current = _subcommands(current).get(part)
        if current is None:
            return None
    return current


def _runs_without_a_subcommand(parser: argparse.ArgumentParser) -> bool:
    """True when the parent itself does work: its subcommand is optional and
    its handler is not merely that parser's own help.

    `ws list` counts every kind and `ws relations` lists the vocabulary, so
    both are commands; `ws create` and `ws projects` only print their help,
    which makes them headings (their handlers are named `*_help`, the
    convention this relies on)."""
    handler = parser.get_default("func")
    if handler is None or getattr(handler, "__name__", "").endswith("_help"):
        return False
    return any(
        isinstance(action, argparse._SubParsersAction) and not action.required
        for action in parser._actions
    )


def leaf_commands(
    parser: argparse.ArgumentParser,
    prefix: tuple[str, ...] = (),
    *,
    include_compatibility: bool = False,
) -> list[tuple[str, argparse.ArgumentParser]]:
    rows: list[tuple[str, argparse.ArgumentParser]] = []
    for name, child in _subcommands(parser).items():
        if name.startswith("__"):
            continue
        path = prefix + (name,)
        if not include_compatibility and is_compatibility_path(path):
            continue
        children = _subcommands(child)
        if children and _runs_without_a_subcommand(child):
            # A parent that does something on its own (`ws list` counts every
            # kind, `ws relations` lists the vocabulary) is a command in its
            # own right, not merely a heading.
            rows.append((" ".join(path), child))
        if children:
            rows.extend(
                leaf_commands(
                    child,
                    path,
                    include_compatibility=include_compatibility,
                )
            )
        else:
            rows.append((" ".join(path), child))
    return rows


def bind_command_paths(
    parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()
) -> None:
    for name, child in _subcommands(parser).items():
        path = prefix + (name,)
        child.set_defaults(_ws_command_path=" ".join(path))
        bind_command_paths(child, path)


def print_receipt(command_path: str) -> None:
    canonical = " ".join(canonical_command_path(command_path.split()))
    effect = asdict(EFFECTS.get(canonical, EffectSpec()))
    print(
        json.dumps(
            {
                "schema_version": 1,
                "command": f"ws {command_path}",
                "status": "succeeded",
                "completed_at": dt.datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "declared_effects": effect,
            },
            indent=2,
        )
    )


def command_record(root: argparse.ArgumentParser, path: list[str]) -> dict:
    parser = resolve_parser(root, path)
    if parser is None:
        raise KeyError(" ".join(path))
    canonical = canonical_command_path(list(path))
    effect = EFFECTS.get(" ".join(canonical), EFFECTS.get(path[0], EffectSpec()))
    children = sorted(_subcommands(parser))
    namespace = (
        DOMAINS.get(canonical[0])
        or GLOBAL_NAMESPACES.get(canonical[0])
        or GRAPH.get(canonical[0])
    )
    contract = namespace.contract if namespace else VERB_CONTRACTS.get(path[0], "")
    # A leaf answers for itself; only a namespace root may borrow the
    # namespace's purpose. Flags are help's job, not describe's.
    purpose = parser.description or ""
    if not purpose and namespace and len(path) == 1:
        purpose = namespace.purpose
    try:
        category = command_category(list(path))
    except KeyError:
        category = ""
    return {
        "command": f"ws {' '.join(path)}",
        "kind": namespace.kind if namespace else "command",
        "category": category,
        "purpose": purpose,
        "subcommands": children,
        "effects": asdict(effect),
        "contract": contract,
        "guide": command_guide(canonical),
    }


def command_guide(canonical: list[str]) -> str:
    """Route command discovery to shared usage docs, relative to SYSTEM."""
    if canonical[:2] == ["projects", "install"]:
        return "docs/project-install.md"
    if "views" in canonical:
        return "docs/browsing.md"
    return {
        "init": "GETTING-STARTED.md",
        "projects": "docs/project-setup.md",
        "literature": "docs/literature.md",
        "profile": "docs/profile.md",
        "documents": "docs/documents.md",
        "resources": "docs/resources.md",
        "relations": "docs/relationships.md",
        "relate": "docs/relationships.md",
        "unrelate": "docs/relationships.md",
        "show": "docs/relationships.md",
        "search": "docs/relationships.md",
        "wiki": "docs/visualization.md",
        "completions": "docs/ws-completions.md",
    }.get(canonical[0], "docs/reference/commands.md")


def _first_sentence(text: str) -> str:
    """One line for a listing, from a description that may say more."""
    stripped = (text or "").strip()
    cut = stripped.find(". ")
    return stripped[: cut + 1] if cut != -1 else stripped


def command_category(words: list[str]) -> str:
    """The category a command spelling files under, from its first word:
    verb-first commands carry it in VERB_CATEGORIES, namespace commands on
    their NamespaceSpec, domain specialists file under their domain."""
    head = words[0]
    if head in VERB_CATEGORIES:
        return VERB_CATEGORIES[head]
    if head in DOMAINS:
        return head
    if head in GRAPH:
        return "objects"
    spec = GLOBAL_NAMESPACES.get(head)
    if spec:
        return spec.kind
    raise KeyError(f"uncategorised command: ws {' '.join(words)}")


def command_domains(_args: argparse.Namespace) -> None:
    for spec in DOMAINS.values():
        print(f"{spec.name:<14} {spec.purpose}")


def command_describe(args: argparse.Namespace) -> None:
    try:
        record = command_record(args.root_parser, args.path)
    except KeyError:
        args.root_parser.error(f"unknown command path: {' '.join(args.path)}")
    if args.json:
        print(json.dumps(record, indent=2))
        return
    print(record["command"])
    if record["purpose"]:
        print(record["purpose"])
    from .paths import SYSTEM

    print(f"guide: {SYSTEM / record['guide']}")
    if record["contract"]:
        print(f"contract: {record['contract']}")
    if record["subcommands"]:
        print(f"subcommands: {', '.join(record['subcommands'])}")
    effects = record["effects"]
    for label in ("reads", "writes", "relations", "external"):
        if effects[label]:
            print(f"{label}:")
            for item in effects[label]:
                print(f"  - {item}")
    if effects["destructive"]:
        print("destructive: yes")


def kind_capability_records(
    root: argparse.ArgumentParser, word: str
) -> list[dict] | None:
    """Everything one can do with one kind: the universal tools instantiated
    for it, then the kind's home specialists. None if the word names no kind."""
    kind = KIND_OF_WORD.get(word)
    if kind is None:
        return None
    plural = KIND_PLURALS[kind]
    home = HOISTED_KIND_HOMES[kind]
    ref = f"{kind}:<key>"
    records: list[dict] = []

    def tool(path: list[str], spelling: str) -> None:
        record = command_record(root, path)
        record["command"] = spelling
        records.append(record)

    for name in (kind, plural):
        if resolve_parser(root, ("create", name)):
            tool(["create", name], f"ws create {name}")
            break
    if kind == "project":
        tool(["create", "subproject"], "ws create subproject")
    for name in (kind, plural):
        if resolve_parser(root, ("add", name)):
            spelling = f"ws add {ref} <path>" if kind == "resource" else f"ws add {name}"
            tool(["add", name], spelling)
            break
    tool(["show"], f"ws show {ref}")
    if kind not in REF_TOOL_EXCEPTIONS["edit"]:
        tool(["edit"], f"ws edit {ref}")
    if kind not in REF_TOOL_EXCEPTIONS["delete"]:
        tool(["delete"], f"ws delete {ref}")
    if resolve_parser(root, ("list", plural)):
        tool(["list", plural], f"ws list {plural}")
    tool(["search"], f"ws search {plural} <query>")
    tool(["show"], f"ws show relations of {ref}")
    tool(["relate"], f"ws relate {ref} to <ref> as <words>")
    tool(["unrelate"], f"ws unrelate {ref} to <ref> as <words>")

    home_parser = resolve_parser(root, home)
    if home_parser is not None:
        for path, _ in leaf_commands(home_parser, home):
            records.append(command_record(root, path.split()))
    return records


def _canonical_capability_paths(root: argparse.ArgumentParser) -> list[list[str]]:
    """One row per command: alias rows collapse onto their parser, and the
    universal grammar leads the listing."""
    paths, seen = [], set()
    for path, parser in leaf_commands(root):
        if id(parser) in seen:
            continue
        seen.add(id(parser))
        paths.append(path.split())
    rank = {name: position for position, name in enumerate(UNIVERSAL_VERBS)}
    paths.sort(key=lambda words: (0, rank[words[0]]) if words[0] in rank else (1, 0))
    return paths


def command_capabilities(args: argparse.Namespace) -> None:
    if args.path:
        if len(args.path) == 1:
            word = args.path[0]
            if word in CATEGORIES:
                paths = [
                    words
                    for words in _canonical_capability_paths(args.root_parser)
                    if command_category(words) == word
                ]
                records = [command_record(args.root_parser, words) for words in paths]
                if args.json:
                    print(json.dumps(records, indent=2))
                    return
                for record in records:
                    print(record["command"])
                return
            records = kind_capability_records(args.root_parser, word)
            if records is not None:
                if args.json:
                    print(json.dumps(records, indent=2))
                    return
                for record in records:
                    print(record["command"])
                return
        command_describe(args)
        return
    if getattr(args, "all", False):
        # Every registered spelling, flat: a debugging surface, not the canon.
        paths = [
            path.split()
            for path, _ in leaf_commands(args.root_parser, include_compatibility=True)
        ]
        records = [command_record(args.root_parser, words) for words in paths]
        if args.json:
            print(json.dumps(records, indent=2))
            return
        for record in records:
            print(record["command"])
        return
    paths = _canonical_capability_paths(args.root_parser)
    records = [command_record(args.root_parser, words) for words in paths]
    if args.json:
        print(json.dumps(records, indent=2))
        return
    # Grouped: the five categories of global commands, then each domain's
    # specialists. Rows stay flush-left so the output pipes cleanly.
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record["category"] or "uncategorised", []).append(record)
    first = True
    for name in (*CATEGORIES, *DOMAINS):
        rows = grouped.pop(name, [])
        if not rows:
            continue
        if not first:
            print()
        first = False
        purpose = CATEGORIES.get(name) or DOMAINS[name].purpose
        print(f"# {name} — {purpose}")
        for record in rows:
            print(record["command"])
    for name, rows in grouped.items():  # a defect in the model, kept visible
        print(f"\n# uncategorised: {name}")
        for record in rows:
            print(record["command"])


# The overview's category rows: the commands a person reaches for, not the
# exhaustive listing. `relations` and `domains` are commands too, but they
# read as places rather than actions, so the map points at them from "what
# the workspace holds" instead. `ws capabilities` remains the total view.
OVERVIEW_CATEGORY_COMMANDS = {
    "objects": ("create", "add", "show", "edit", "delete", "relate", "unrelate"),
    "search": ("list", "search", "id"),
    "maintenance": ("init", "index", "wiki", "check"),
    "discovery": ("help", "capabilities", "describe", "completions"),
}

# Grammar shape, what it is for, and one command that really runs.
OVERVIEW_GRAMMAR = (
    ("ws <verb> <kind:key>", "act on one object", "ws show document:some-receipt"),
    ("ws <verb> <kind> ...", "enter or list a kind", "ws add person Maria Schwarz"),
    ("ws <domain> <specialist>", "specific to one kind", "ws logistics people merge"),
)

OVERVIEW_DISCOVERY = (
    ("ws capabilities [KIND|CATEGORY]", "which commands exist"),
    ("ws help COMMAND", "how to type it"),
    ("ws describe COMMAND", "what it does and touches"),
    ("ws check [AREA]", "validate the workspace"),
)


def _wrapped_names(names: Iterable[str], width: int) -> list[str]:
    """Pack names into lines no wider than `width`, for the domains row."""
    lines: list[str] = []
    current = ""
    for name in names:
        candidate = f"{current} {name}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = name
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def print_overview() -> None:
    """The one overview text, shared by bare `ws`, `ws --help`, and bare
    `ws help` (contracts/cli.md, Discovery).

    A map, not a tutorial: it names every category, points at the two
    listings, and shows the three grammars. It reads no workspace state, so
    it prints identically in a broken or absent workspace -- the live edge
    count belongs to `ws relations`, which is one keystroke away."""
    label, gutter = 13, 42
    print("ws - workspace administration\n")
    print("What you can do")
    for name, commands in OVERVIEW_CATEGORY_COMMANDS.items():
        print(f"  {name:<{label}}{' · '.join(commands)}")
    print("\nWhat the workspace holds")
    rows = _wrapped_names(DOMAINS, gutter)
    for position, row in enumerate(rows):
        name = "domains" if position == 0 else ""
        pointer = "  -> ws domains" if position == len(rows) - 1 else ""
        print(f"  {name:<{label}}{row:<{gutter}}{pointer}".rstrip())
    edges = "the edge layer between objects"
    print(f"  {'relations':<{label}}{edges:<{gutter}}  -> ws relations")
    print("\nGrammar")
    for shape, purpose, example in OVERVIEW_GRAMMAR:
        print(f"  {shape:<26}{purpose:<22}{example}")
    print("  Flags come last: ws <verb> <kind> <operands> --flag value")
    print("\nFinding your way")
    for command, answer in OVERVIEW_DISCOVERY:
        print(f"  {command:<34}{answer}")
    from .paths import SYSTEM

    print(f"\nGetting started: {SYSTEM / 'GETTING-STARTED.md'}")
    print(f"Usage guides: {SYSTEM / 'docs/README.md'}")


def command_help(args: argparse.Namespace) -> None:
    if not args.path:
        print_overview()
        return
    parser = resolve_parser(args.root_parser, args.path)
    if parser is None:
        args.root_parser.error(f"unknown command path: {' '.join(args.path)}")
    parser.print_help()


def add_parsers(sub: argparse._SubParsersAction, root: argparse.ArgumentParser) -> None:
    domains = sub.add_parser(
        "domains",
        help="list the domains that own objects",
        description="List the domains: the homes that own objects, each "
        "hosting its kind's own specialists.",
    )
    domains.set_defaults(func=command_domains)

    help_parser = sub.add_parser("help", help="show help for a command path")
    help_parser.add_argument("path", nargs="*")
    help_parser.set_defaults(func=command_help, root_parser=root)

    capabilities = sub.add_parser(
        "capabilities",
        help="list executable capabilities; a kind or category word scopes",
        description="List every command, one spelling each, grouped by "
        "category (objects, search, maintenance, discovery) and "
        "domain. `ws capabilities documents` shows everything one can do "
        "with that kind, `ws capabilities maintenance` one category; a "
        "longer command path describes that one command.",
    )
    capabilities.add_argument("path", nargs="*")
    capabilities.add_argument("--json", action="store_true")
    capabilities.add_argument(
        "--all",
        action="store_true",
        help="every registered spelling: domain synonyms, aliases, compatibility paths",
    )
    capabilities.set_defaults(func=command_capabilities, root_parser=root)

    describe = sub.add_parser("describe", help="show usage guide, contract and side effects for a command")
    describe.add_argument("path", nargs="+")
    describe.add_argument("--json", action="store_true")
    describe.set_defaults(func=command_describe, root_parser=root)
