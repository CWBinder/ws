"""`ws rebuild [TARGET]`: regenerate the derived layers from canonical data.

Four layers are derived, and deleting any of them loses nothing: each
domain's `by-*` browse views, the search index, the generated wiki, and the
dashboard page. Bare `ws rebuild` regenerates all four in that order,
`ws rebuild TARGET` one of them, and `ws rebuild views DOMAIN` one domain's
trees (contracts/workspace.md, Derived layers).

Each layer once had its own spelling (`ws documents views rebuild`,
`ws index rebuild`, `ws wiki build`, `ws dashboard build`). Those still run
as aliases of the same handler; they are registered here so the whole
command lives in one place.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

from ws_lib import anatomy, dashboard, indexing, literature, paths, project, registry, wiki


TARGETS = tuple(registry.REBUILD_TARGETS)
VIEW_DOMAINS = registry.VIEW_DOMAINS


def _view_root(domain: str) -> Path:
    return {
        "projects": anatomy.PROJECTS_DOMAIN,
        "documents": paths.DOCUMENTS,
        "literature": literature.LITERATURE,
        "profile": paths.CAREER,
        "resources": paths.RESOURCES,
    }[domain]


def rebuild_views(domains: Iterable[str] = VIEW_DOMAINS) -> dict[str, dict]:
    """Rebuild each domain's by-* trees. Every domain validates the same
    folder-anatomy.yaml before its wipe, so a broken file raises AnatomyError
    at the first domain and leaves every tree as it was."""
    results: dict[str, dict] = {}
    for domain in domains:
        counts = getattr(anatomy, f"rebuild_{domain}")()
        record: dict = {"root": str(_view_root(domain))}
        if domain == "documents":
            # Documents report totals, plus the records whose file is gone.
            record.update(counts)
        else:
            record.update(links=sum(counts.values()), trees=counts)
        results[domain] = record
    return results


def _rebuild(target: str, domains: tuple[str, ...]) -> dict:
    if target == "views":
        return rebuild_views(domains)
    if target == "index":
        return indexing.rebuild(quiet=True)
    if target == "wiki":
        return wiki.build()
    return dashboard.build()


def _lines(target: str, result: dict) -> list[str]:
    if target == "views":
        lines = []
        for record in result.values():
            missing = record.get("missing")
            skipped = f"  skipped, file missing: {missing}" if missing else ""
            lines.append(
                f"rebuilt views: {project.rel_home(Path(record['root']))}/by-*  "
                f"links: {record['links']}{skipped}"
            )
        return lines
    if target == "index":
        summary = f"objects: {result['objects']}  relations: {result['relationships']}"
    elif target == "wiki":
        summary = (
            f"projects: {result['projects']}  literature: {result['literature']}  "
            f"other objects: {result['registered']}  relations: {result['relations']}"
        )
    else:
        summary = (
            f"objects: {result['objects']}  relations: {result['relations']}  "
            f"open tasks: {result['open_tasks']}"
        )
    return [f"rebuilt {target}: {project.rel_home(Path(result['path']))}  {summary}"]


def command_rebuild(args: argparse.Namespace) -> None:
    current = getattr(args, "current_spelling", "")
    if current:
        print(f"note: the current spelling is `ws {current}`", file=sys.stderr)
    # `--in DIR` exists only on the older `ws projects views rebuild`.
    project.use_projects_dir(args)
    domain = getattr(args, "domain", None)
    domains = (domain,) if domain else VIEW_DOMAINS
    results: dict[str, dict] = {}
    failed = False
    for target in args.targets:
        try:
            results[target] = _rebuild(target, domains)
        except anatomy.AnatomyError as exc:
            # Validation precedes any wipe, so the previous trees stand, and
            # no other layer reads the browse settings: carry on with them.
            results[target] = {"error": str(exc)}
            failed = True
            print(f"error: {target}: {exc}", file=sys.stderr)
            continue
        if not args.json:
            for line in _lines(target, results[target]):
                print(line)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


def command_heading_help(args: argparse.Namespace) -> None:
    args.heading.print_help()


def add_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "rebuild",
        help="regenerate the derived layers from canonical data",
        description="Regenerate the derived layers from canonical data: each "
        "domain's by-* browse views, the search index, the generated wiki and "
        "the dashboard, in that order. Name a target to rebuild only that "
        "layer. Records and relations are only read.",
    )
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=command_rebuild, targets=TARGETS)
    targets = parser.add_subparsers(dest="rebuild_target", metavar="TARGET")

    views = targets.add_parser(
        "views",
        help="rebuild the by-* browse folders of every domain, or of one",
        description="Rebuild the by-* browse folders from folder-anatomy.yaml "
        "and the current records: every domain, or only the one named.",
    )
    views.add_argument(
        "domain",
        nargs="?",
        choices=VIEW_DOMAINS,
        metavar="DOMAIN",
        help=f"one domain ({', '.join(VIEW_DOMAINS)}); bare `ws rebuild views` "
        "rebuilds all of them",
    )
    views.add_argument("--json", action="store_true")
    views.set_defaults(func=command_rebuild, targets=("views",))

    for target, text in (
        ("index", "rebuild the search index"),
        ("wiki", "rebuild the generated Obsidian wiki under wiki/generated/"),
        ("dashboard", "rebuild dashboard.html, the workspace at a glance with its graph"),
    ):
        child = targets.add_parser(target, help=text)
        child.add_argument("--json", action="store_true")
        child.set_defaults(func=command_rebuild, targets=(target,))


def _subparsers(parser: argparse.ArgumentParser, dest: str) -> argparse._SubParsersAction:
    """The parser's subcommand table; a missing one makes it a heading."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    parser.set_defaults(func=command_heading_help, heading=parser)
    return parser.add_subparsers(dest=dest)


def add_older_spellings(sub: argparse._SubParsersAction) -> None:
    """Attach each layer's older spelling beneath its old home, as an alias
    that runs `ws rebuild` (contracts/cli.md: aliases execute the same
    function). Call once the domain parsers exist."""
    for older, current in registry.OLDER_REBUILD_SPELLINGS.items():
        *homes, leaf = older.split()
        _, target, *domain = current.split()
        actions = sub
        for depth, name in enumerate(homes):
            parent = actions.choices.get(name) or actions.add_parser(
                name, help=f"older home of `ws rebuild {target}`"
            )
            actions = _subparsers(parent, "_".join(homes[: depth + 1]) + "_command")
        alias = actions.add_parser(
            leaf,
            help=f"older spelling of `ws {current}`",
            description=f"Older spelling of `ws {current}`; runs the same command.",
        )
        alias.add_argument("--json", action="store_true")
        if homes == ["projects", "views"]:
            project.add_projects_dir_arg(alias)
        alias.set_defaults(
            func=command_rebuild,
            targets=(target,),
            domain=domain[0] if domain else None,
            current_spelling=current,
        )
