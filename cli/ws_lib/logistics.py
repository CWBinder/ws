from __future__ import annotations

import argparse
from pathlib import Path

from ws_lib import catalog, paths


def command_communications_list(_args: argparse.Namespace) -> None:
    if not paths.COMMUNICATIONS.exists():
        print("none")
        return
    files = sorted(path for path in paths.COMMUNICATIONS.rglob("*") if path.is_file())
    print("\n".join(str(path.relative_to(paths.COMMUNICATIONS)) for path in files) if files else "none")


def command_communications_path(_args: argparse.Namespace) -> None:
    print(paths.COMMUNICATIONS)


def command_communications_show(args: argparse.Namespace) -> None:
    requested = Path(args.path)
    if requested.is_absolute() or ".." in requested.parts:
        catalog.fail("communication asset must be relative to the communications folder")
    target = paths.COMMUNICATIONS / requested
    if not target.is_file():
        catalog.fail(f"communication asset does not exist: {target}")
    print(target.read_text(encoding="utf-8"), end="")


def add_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = sub.add_parser(
        "logistics",
        help="manage people, organisations, events, and communication assets",
    )
    actions = parser.add_subparsers(dest="logistics_command", required=True)
    catalog.add_object_parser(
        actions, "people", "person", help_text="people specialists (ensure, merge)"
    )
    catalog.add_object_parser(
        actions,
        "organisations",
        "organisation",
        help_text="organisation specialists (ensure, merge)",
    )
    catalog.add_object_parser(
        actions, "events", "event", help_text="event specialists (ensure, merge)"
    )

    communications = actions.add_parser(
        "communications", help="inspect templates, styles, and reference material"
    )
    communication_actions = communications.add_subparsers(
        dest="communications_command", required=True
    )
    communication_actions.add_parser(
        "list", help="list the available templates, styles, and reference material"
    ).set_defaults(
        func=command_communications_list
    )
    communication_actions.add_parser(
        "path", help="print the communications folder path"
    ).set_defaults(
        func=command_communications_path
    )
    show = communication_actions.add_parser(
        "show", help="print one communications file"
    )
    show.add_argument("path")
    show.set_defaults(func=command_communications_show)

    return parser
