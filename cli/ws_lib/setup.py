"""`ws setup`: a wizard an agent can run.

A program cannot hold a conversation with an agent, so this one prints instead
of asking: what to explain, what to ask, and which command to run with the
answers. The agent talks to the person, runs that command and runs `ws setup`
again. Progress is read from the workspace itself, so there is no state to
keep and a new session picks up where the last one stopped. The texts ship
under `context/setup/`. Nothing here writes (contracts/workspace.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json

from ws_lib import catalog, context, owner, paths


TEXTS = paths.SYSTEM / "context" / "setup"

# In order: the name of each step's text, and how its heading calls it.
STEPS = (
    ("workspace", "the workspace folder"),
    ("identity", "their public identity"),
    ("person", "their private details"),
)


def _text(name: str) -> str:
    return context._read(TEXTS / f"{name}.md").replace("{today}", dt.date.today().isoformat())


def next_step() -> str:
    """The first step the workspace has not done yet, or '' when it has them all."""
    if not paths.FOLDER_ANATOMY.is_file():
        return "workspace"
    found = owner.find([*catalog.stored_objects("person"), *catalog.stored_objects("profile")])
    if not found or not found["identity"]:
        return "identity"
    return "person" if not found["person"] else ""


def render(step: str) -> str:
    if not step:
        return "\n\n".join(["WS SETUP: complete", _text("done")])
    number, title = next(
        (index, title) for index, (name, title) in enumerate(STEPS, start=1) if name == step
    )
    return "\n\n".join([f"WS SETUP: step {number} of {len(STEPS)}, {title}", _text("guide"), _text(step)])


def command_setup(args: argparse.Namespace) -> None:
    step = next_step()
    if args.json:
        print(json.dumps(
            {"step": step, "complete": not step, "text": render(step)},
            ensure_ascii=False, indent=2, sort_keys=True,
        ))
    else:
        print(render(step))


def add_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="the next step of setting up ws, written for an agent guiding a person",
        description="Print the next unfinished step of setting up ws: what to explain, what to ask, "
        "and which command to run with the answers. Run it again after each step. It changes nothing "
        "itself, and it reads its progress from the workspace, so it can stop and resume at any point.",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.set_defaults(func=command_setup)
