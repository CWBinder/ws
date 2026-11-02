"""`ws setup`: getting started, for an agent, at a terminal or in a browser.

One list of steps drives all three. An agent has no terminal to be asked on, so
for it this prints: what to explain, what to ask, and which command to run with
the answers. At a terminal it asks the questions itself, and `--web` asks them
as a form in the browser (setup_web.py). Whatever asks, the answers end up in
the same `ws` commands, run as separate processes because `ws init` changes
where the next command finds the workspace. Which required step comes next is
read from the workspace, so there is no state to keep and any session can pick
up where the last one stopped.

`--test` runs the whole thing against a temporary workspace that is deleted at
the end (contracts/workspace.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ws_lib import catalog, context, owner, paths, project


TEXTS = paths.SYSTEM / "context" / "setup"
TEST_ENV = "WS_SETUP_TEST"
# Settings that say where ws itself lives, which a test run still needs.
KEPT_IN_TEST = {"WS_SYSTEM_ROOT", "WS_CLI_ROOT"}


class SetupError(Exception):
    """A step that could not be applied, in words the person can act on."""


@dataclass(frozen=True)
class Question:
    key: str
    ask: str
    flag: str = ""  # empty: the value goes into the command itself
    many: bool = False  # several values, comma-separated
    required: bool = False
    default: str = ""  # {root} and {name} come from the workspace's state


@dataclass(frozen=True)
class Step:
    name: str
    title: str
    questions: tuple[Question, ...]
    command: tuple[str, ...] = ()
    howto: str = ""  # how to apply it, where one command does not say it


PROVENANCE = ("--source", "ws setup", "--observed-at", "{today}")

REQUIRED = (
    Step(
        "workspace", "the workspace folder",
        (Question("root", "Where the workspace should live", "--root", default="{root}"),),
        ("init",),
    ),
    Step(
        "identity", "your public identity",
        (
            Question("name", "Full name, as a CV should show it", required=True),
            Question("headline", "One-line professional headline", "--headline"),
            Question("email", "Email address a CV should show", "--email"),
            Question("phone", "Phone number a CV should show", "--phone"),
            Question("address", "Postal address a CV should show", "--address"),
            Question("link", "Public links, such as a website", "--link", many=True),
            Question("orcid", "ORCID, if you have one", "--orcid"),
        ),
        ("create", "profile", "{name}", "--type", "identity", "--ensure", *PROVENANCE),
    ),
    Step(
        "person", "your private details",
        (
            Question("name", "Your name", required=True, default="{name}"),
            Question("preferred", "What agents should call you", "--preferred-name"),
            Question("email", "Every email address worth knowing", "--email", many=True),
            Question("phone", "Every phone number worth knowing", "--phone", many=True),
            Question("description", "A sentence or two on who you are and what you do", "--description"),
        ),
        ("add", "person", "{name}", "--owner", "--ensure", "--non-interactive", *PROVENANCE),
    ),
)

# Offered once the required steps are done. Nothing tells whether these are
# done, and they can be repeated, so each session offers them again.
OPTIONAL = (
    Step(
        "fields", "your fields",
        (
            Question("fields", "Broad fields you work in", many=True),
            Question("subfields", "Subfields, as field/subfield", many=True),
        ),
        howto="ws projects add-field FIELD\nws projects add-subfield FIELD SUBFIELD",
    ),
    Step(
        "note", "a note for every briefing",
        (Question("note", "What every agent should always know"),),
        howto="Add it to {root}/.context/whereami.md, keeping what is there.",
    ),
)

STEPS = {step.name: step for step in (*REQUIRED, *OPTIONAL)}


def _text(name: str) -> str:
    launcher = shutil.which("ws") or sys.argv[0]
    return (
        context._read(TEXTS / f"{name}.md")
        .replace("{today}", dt.date.today().isoformat())
        .replace("{ws}", launcher)
    )


def _next_step(initialised: bool, found: dict | None) -> str:
    """The first required step not done yet, or '' when all are."""
    if not initialised:
        return "workspace"
    if not found or not found["identity"]:
        return "identity"
    return "person" if not found["person"] else ""


def state() -> dict:
    """What this workspace has, for this process."""
    initialised = paths.FOLDER_ANATOMY.is_file()
    found = owner.find([*catalog.stored_objects("person"), *catalog.stored_objects("profile")])
    step = _next_step(initialised, found)
    return {
        "step": step,
        "complete": not step,
        "root": context._home_path(paths.WORKSPACE),
        "name": found["name"] if found else "",
        "owner": found,
        "fields": list(project.load_taxonomy().get("fields", [])) if initialised else [],
        "test": TEST_ENV in os.environ,
    }


def explain(step: Step, known: dict) -> str:
    return _text(step.name).replace("{fields}", ", ".join(known["fields"]))


def default_of(question: Question, known: dict) -> str:
    # A test run shows what a real one would, not its temporary folder.
    root = "~/workspace" if known["test"] else known["root"]
    return question.default.replace("{root}", root).replace("{name}", known["name"])


def _argv(step: Step, answers: dict) -> list[str]:
    """The ws command a required step's answers become."""
    today = dt.date.today().isoformat()
    argv = [
        answers.get("name", "") if word == "{name}" else today if word == "{today}" else word
        for word in step.command
    ]
    for question in step.questions:
        value = answers.get(question.key)
        if question.flag and value:
            for item in value if isinstance(value, list) else [value]:
                argv += [question.flag, item]
    return argv


def template(step: Step) -> str:
    """The same command with placeholders, for an agent to fill in."""
    if step.howto:
        return step.howto
    names = {
        question.key: [question.key.upper()] if question.many else question.key.upper()
        for question in step.questions
    }
    words = _argv(step, names)
    quoted = [f'"{word}"' if " " in word else word for word in words]
    return "ws " + " ".join(quoted)


def _ws(*args: str) -> str:
    """Run ws in a process of its own and return what it printed."""
    result = subprocess.run(
        [sys.executable, sys.argv[0], *args],
        stdin=subprocess.DEVNULL, capture_output=True, text=True,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise SetupError(message.removeprefix("error: ") or f"ws {args[0]} failed")
    return result.stdout


def current_state() -> dict:
    """The workspace's state as a fresh process sees it, since `ws init` may
    have moved it since this one started."""
    return json.loads(_ws("setup", "--json"))


def _add_fields(answers: dict) -> None:
    subfields = []
    for pair in answers.get("subfields") or []:
        field, slash, subfield = pair.partition("/")
        if not slash or not field.strip() or not subfield.strip():
            raise SetupError(f"Write a subfield as field/subfield, not '{pair}'")
        subfields.append((field.strip(), subfield.strip()))
    for field in [*(answers.get("fields") or []), *(field for field, _ in subfields)]:
        _ws("projects", "add-field", field)
    for field, subfield in subfields:
        _ws("projects", "add-subfield", field, subfield)


def _add_note(root: str, note: str) -> None:
    path = Path(root).expanduser() / context.CONTEXT / "whereami.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    kept = path.read_text(encoding="utf-8").rstrip() if path.is_file() else ""
    path.write_text(f"{kept}\n\n{note}\n" if kept else f"{note}\n", encoding="utf-8")


def clean(step: Step, raw: dict) -> dict:
    """Typed answers as commands want them: trimmed, lists split at commas."""
    answers: dict = {}
    for question in step.questions:
        text = str(raw.get(question.key) or "").strip()
        if question.required and not text:
            raise SetupError(f"{question.ask} is needed")
        if text:
            answers[question.key] = (
                [item.strip() for item in text.split(",") if item.strip()] if question.many else text
            )
    return answers


def apply(step: Step, raw: dict, known: dict) -> None:
    """Carry out one answered step."""
    answers = clean(step, raw)
    if step.name == "fields":
        _add_fields(answers)
    elif step.name == "note":
        if answers:
            _add_note(known["root"], answers["note"])
    elif step.name == "workspace":
        # A test run stays in its temporary folder, whatever was answered.
        root = answers.get("root", "")
        chosen = str(Path(root).expanduser()) if root else ""
        same = chosen == str(Path(known["root"]).expanduser())
        _ws(*(("init",) if known["test"] or same or not chosen else ("init", "--root", chosen)))
    else:
        _ws(*_argv(step, answers))


class Session:
    """One person going through setup: the required steps the workspace still
    lacks, then each optional step once. The terminal and the browser both
    drive this."""

    def __init__(self) -> None:
        self.offered: set[str] = set()

    def current(self, known: dict) -> Step | None:
        if known["step"]:
            return STEPS[known["step"]]
        return next((step for step in OPTIONAL if step.name not in self.offered), None)

    def submit(self, step: Step, raw: dict, known: dict) -> None:
        apply(step, raw, known)
        self.offered.add(step.name)

    def skip(self, step: Step) -> None:
        self.offered.add(step.name)


def position(step: Step) -> str:
    names = [item.name for item in REQUIRED]
    if step.name in names:
        return f"Step {names.index(step.name) + 1} of {len(names)}"
    return "Optional"


def owner_summary() -> str:
    return _ws("owner").rstrip()


TEST_NOTICE = "TEST RUN: everything you enter stays in a temporary folder, deleted at the end."
TEST_OVER = "That was a test: nothing was kept. For real, run `ws setup`."


def run_terminal() -> None:
    session = Session()
    known = current_state()
    print("WS SETUP\n")
    if known["test"]:
        print(f"{TEST_NOTICE}\n")
    if not known["complete"]:
        print(f"{_text('about')}\n")
    while (step := session.current(known)) is not None:
        print(f"{position(step)}: {step.title}\n\n{explain(step, known)}\n")
        if known["test"] and step.name == "workspace":
            print("In this test run the answer is ignored.\n")
        raw = {}
        for question in step.questions:
            default = default_of(question, known)
            hint = f" [{default}]" if default else "" if question.required else " (Enter skips)"
            if question.many:
                hint = f" (separate with commas){hint}"
            while True:
                raw[question.key] = input(f"  {question.ask}{hint}: ").strip() or default
                if raw[question.key] or not question.required:
                    break
                print("  This one is needed.")
        print()
        try:
            session.submit(step, raw, known)
        except SetupError as problem:
            print(f"That did not work: {problem}\n")
        known = current_state()
    print(f"Done. What agents will find about you:\n\n{owner_summary()}\n\n{_text('done')}")
    if known["test"]:
        print(f"\n{TEST_OVER}")


def render_step(step: Step, known: dict) -> str:
    asks = "\n".join(
        f"- {question.ask}" + (f" (default: {default_of(question, known)})" if question.default else "")
        for question in step.questions
    )
    how = "\n".join(f"    {line}" for line in template(step).replace("{root}", known["root"]).splitlines())
    return f"EXPLAIN\n\n{explain(step, known)}\n\nASK\n\n{asks}\n\nRUN, leaving out what they skipped\n\n{how}"


def render(known: dict) -> str:
    """What an agent reads: one step, or the closing page with what is left to offer."""
    if known["step"]:
        step = STEPS[known["step"]]
        number = position(step).lower()
        return "\n\n".join([
            f"WS SETUP: {number}, {step.title}",
            _text("guide"),
            f"What ws is, to tell them once, unless you already have:\n\n{_text('about')}",
            render_step(step, known),
        ])
    offers = "\n\n".join(f"OFFER: {step.title.upper()}\n\n{render_step(step, known)}" for step in OPTIONAL)
    return "\n\n".join([
        "WS SETUP: complete",
        "The workspace and its owner are in place; there is no need to run `ws setup` again. "
        "Show them `ws owner` and `ws context`, tell them what follows, and offer the rest. "
        "Do only what they accept, and show them any change to their agent's settings first.",
        _text("done"),
        offers,
    ])


def _run_test() -> int:
    """This same command again, pointed at a temporary workspace and config."""
    with tempfile.TemporaryDirectory(prefix="ws-setup-test-") as folder:
        env = {key: value for key, value in os.environ.items() if not key.startswith("WS_") or key in KEPT_IN_TEST}
        env.update({
            TEST_ENV: "1",
            "WS_WORKSPACE_ROOT": str(Path(folder) / "workspace"),
            "WS_CONFIG": str(Path(folder) / "config.yaml"),
        })
        words = [word for word in sys.argv[1:] if word != "--test"]
        return subprocess.run([sys.executable, sys.argv[0], *words], env=env, cwd=folder).returncode


def command_setup(args: argparse.Namespace) -> None:
    at_terminal = args.interactive or (sys.stdin.isatty() and sys.stdout.isatty() and not args.non_interactive)
    if args.test and TEST_ENV not in os.environ:
        if not (args.web or at_terminal) or args.json:
            catalog.fail("--test needs someone to answer: run it at a terminal, or add --web")
        raise SystemExit(_run_test())
    if args.json:
        known = state()
        print(json.dumps({**known, "text": render(known)}, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.web:
        from ws_lib import setup_web

        setup_web.run(open_browser=not args.no_browser)
    elif at_terminal:
        run_terminal()
    else:
        print(render(state()))


def add_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="get started: at a terminal, in a browser, or guided by an agent",
        description="Set up ws. At a terminal it asks the questions itself; --web asks them in a "
        "browser. Run by an agent, it prints the next step instead: what to explain, what to ask, "
        "and which command to run. Which step comes next is read from the workspace, so it can stop "
        "and resume at any point.",
        epilog="""Examples:
  ws setup                 ask here, or print the next step for an agent
  ws setup --web           ask in a browser
  ws setup --test          try it at the terminal; nothing is kept
  ws setup --web --test    try it in a browser; nothing is kept
""",
    )
    parser.add_argument("--web", action="store_true", help="ask in a browser, through a server only this machine can reach")
    parser.add_argument("--test", action="store_true", help="use a temporary workspace, deleted at the end; your own is not touched")
    parser.add_argument("--no-browser", action="store_true", help="with --web, print the address instead of opening it")
    parser.add_argument("--interactive", action="store_true", help="ask questions even without a terminal")
    parser.add_argument("--non-interactive", action="store_true", help="print the next step even at a terminal")
    parser.add_argument("--json", action="store_true", help="print the state and next step as JSON")
    parser.set_defaults(func=command_setup)
