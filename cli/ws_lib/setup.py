"""`ws setup`: getting started, for an agent, at a terminal or in a browser.

One list of steps drives all three. At a terminal it asks the questions itself,
and `--web` asks them as a form in the browser (setup_web.py). An agent has no
terminal to be asked on, so for it this prints: the list of steps, and with
`--step` one of them, meaning what to explain, what to ask, and which command to
run with the answers. Whatever asks, the answers end up in the same `ws` commands,
run as separate processes because `ws init` changes where the next command finds
the workspace.

The order is the order of the story: what this is, then each kind of object in
turn, asking about whatever can be personalised, including the person once they
have seen where it all goes, then how it reaches an agent. It ends on their first
knowledge graph and the briefing an agent gets. Three steps are required, and
whether those are done is read from the workspace, so that any session can pick up
where the last one stopped.

`--test` runs the whole thing against a temporary workspace that is deleted at
the end (contracts/workspace.md).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from ws_lib import catalog, context, document_taxonomy, owner, paths, project


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
    picks: str = ""  # choose among what this session found: papers, relations


PROVENANCE = ("--source", "ws setup", "--observed-at", "{today}")

IDEA = (
    Step("brain", "a second brain", ()),
    Step("objects", "objects and relations", ()),
    Step("finding", "finding things", ()),
    Step(
        "workspace", "the workspace folder",
        (Question("root", "Where the workspace should live", "--root", default="{root}"),),
        ("init",),
    ),
)

HOLDS = (
    Step(
        "projects", "projects",
        (
            Question("fields", "Broad fields to sort your projects and papers by", many=True),
            Question("subfields", "Subfields under them, as field/subfield", many=True),
            Question("types", "Project types to add", many=True),
            Question("project", "A project you are working on now"),
            Question("purpose", "What that project is for"),
        ),
        howto="ws projects add-field FIELD\nws projects add-subfield FIELD SUBFIELD\n"
        "ws projects add-type TYPE\nws create project NAME --non-interactive\n"
        "Add its purpose to that project's .context/purpose.md.",
    ),
    Step(
        "literature", "papers and books",
        (Question("author", "The name you publish under on arXiv"),),
        howto="ws literature search-arxiv --author NAME --sort submittedDate\n"
        "Show them the results; for each one they say is theirs:\nws add literature ID --full",
    ),
    Step("papers", "your papers", (), picks="papers"),
    Step(
        "documents", "documents",
        (
            Question("types", "Document types to add", many=True),
            Question("file", "A first file to keep as a document, by its path"),
        ),
        howto="ws documents types add TYPE\nws add document PATH --mode copy --non-interactive --ensure",
    ),
    Step(
        "resources", "resources",
        (Question("resource", "A bundle of files you could start, by name"),),
        howto="ws create resource NAME --ensure",
    ),
    Step(
        "tasks", "tasks",
        (
            Question("task", "Something you have to do"),
            Question("due", "By when, as YYYY-MM-DD"),
        ),
        howto="ws create task TITLE --due YYYY-MM-DD --non-interactive --ensure",
    ),
    Step(
        "identity", "your public identity",
        (
            Question("name", "Full name, as a CV should show it", required=True, default="{name}"),
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
            Question("email", "Other email addresses, beyond the one for your CV", "--email", many=True),
            Question("phone", "Other phone numbers, beyond the one for your CV", "--phone", many=True),
            Question("description", "A sentence or two on who you are and what you do", "--description"),
        ),
        ("add", "person", "{name}", "--owner", "--ensure", "--non-interactive", *PROVENANCE),
    ),
    Step(
        "people", "the people around you",
        (
            Question("organisations", "Organisations you work or study at", many=True),
            Question("people", "People you work with most", many=True),
        ),
        howto="ws add organisation NAME --ensure --non-interactive\nws add person NAME --ensure --non-interactive",
    ),
    Step(
        "relations", "your first relations", (), picks="relations",
        howto="Propose what their answers suggest, and for each they confirm:\nws relate REF to REF as WORDS",
    ),
)

AGENT = (
    Step("agent", "making it your agent", ()),
    Step(
        "briefing", "your own notes in the briefing",
        (
            Question("goals", "What you are working towards"),
            Question("rules", "How agents should work with you"),
            Question("note", "What every agent should always know"),
        ),
        howto="Add them to {root}/.context/purpose.md, {root}/.context/instructions.md and "
        "{root}/.context/whereami.md, keeping what is there.",
    ),
)

PARTS = (("the idea", IDEA), ("what it holds", HOLDS), ("how it reaches your agent", AGENT))
ORDER = tuple(step for _, steps in PARTS for step in steps)
STEPS = {step.name: step for step in ORDER}
# What a workspace cannot do without. Everything else can be skipped and repeated.
REQUIRED = ("workspace", "identity", "person")

# How each thing this session made relates to its owner.
RELATE = {
    "projects": ("works-on", "You work on"),
    "organisations": ("works-at", "You work or study at"),
    "people": ("works-with", "You work with"),
    "papers": ("co-authored", "You co-authored"),
}
# And how it might relate to the project this session made, which only they can say.
TO_PROJECT = {
    "documents": ("belongs-to", "belongs to"),
    "resources": ("supports", "supports"),
    "tasks": ("concerns", "concerns"),
}


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


def _lacking(known: dict) -> tuple[str, ...]:
    """The required steps from the first one not done."""
    return REQUIRED[REQUIRED.index(known["step"]):] if known["step"] else ()


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
        "project_types": list(project.load_taxonomy().get("type", [])) if initialised else [],
        "document_types": list(document_taxonomy.type_ids()) if initialised else [],
        "test": TEST_ENV in os.environ,
    }


def explain(step: Step, known: dict) -> str:
    text = _text(step.name)
    for token in ("fields", "project_types", "document_types"):
        text = text.replace(f"{{{token}}}", ", ".join(known[token]))
    return text


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


def _ws(*args: str, cwd: Path | None = None) -> str:
    """Run ws in a process of its own and return what it printed."""
    result = subprocess.run(
        [sys.executable, sys.argv[0], *args],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, cwd=cwd,
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise SetupError(message.removeprefix("error: ") or f"ws {args[0]} failed")
    return result.stdout


def current_state() -> dict:
    """The workspace's state as a fresh process sees it, since `ws init` may
    have moved it since this one started."""
    return json.loads(_ws("setup", "--json"))


def _made_ref(output: str, kind: str) -> str:
    """The REF in what `ws add` or `ws create` prints, on a line of its own or
    after `created:` or `exists:`."""
    match = re.search(rf"^(?:(?:created|exists): )?({kind}:\S+)$", output, re.MULTILINE)
    if not match:
        raise SetupError(f"could not read the result: {output.strip()[:80]}")
    return match.group(1)


def _add_note(path: Path, note: str) -> None:
    """Add to one of the notes a briefing reads, keeping what is there."""
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


def _without_identity_details(answers: dict) -> dict:
    """Each fact lives in one place: what the identity holds stays off the person."""
    held = json.loads(_ws("owner", "--json"))
    identity = held["identity_details"] if held else {}
    kept = dict(answers)
    for key, field in (("email", "emails"), ("phone", "phones")):
        kept[key] = [item for item in answers.get(key, []) if not catalog.owner_overlap({field: [item]}, identity)]
    return kept


class Session:
    """One person going through setup: each step once, in order, skipping the
    required ones the workspace already has. The terminal and the browser both
    drive this, and it remembers what was made, to propose relations."""

    def __init__(self) -> None:
        self.offered: set[str] = set()
        self.touring = True
        self.author = ""
        self.found: list[dict] = []
        self.made: dict[str, list[tuple[str, str]]] = {kind: [] for kind in (*RELATE, *TO_PROJECT)}
        self.message = ""

    def default_of(self, question: Question, known: dict) -> str:
        # The name they publish under is a fair first guess at the one for a CV.
        return default_of(question, {**known, "name": known["name"] or self.author})

    def choices(self, step: Step, known: dict) -> list[dict]:
        """What a picking step offers: each with an id, words, and whether it starts chosen."""
        if step.picks == "papers":
            return [
                {
                    "id": row["id"],
                    "label": f"{row.get('title', '')} ({row.get('year', '')}), {_short_authors(row.get('authors', ''))}",
                    "checked": False,
                }
                for row in self.found
            ]
        if step.picks == "relations" and known["owner"] and known["owner"]["person"]:
            person = known["owner"]["person"]
            proposed = [
                {"id": f"{person} {word} {ref}", "label": f"{words} {name}", "checked": True}
                for kind, (word, words) in RELATE.items()
                for ref, name in self.made[kind]
            ]
            for project_ref, project_name in self.made["projects"][:1]:
                proposed += [
                    {"id": f"{ref} {word} {project_ref}", "label": f"{name} {words} {project_name}", "checked": False}
                    for kind, (word, words) in TO_PROJECT.items()
                    for ref, name in self.made[kind]
                ]
            return proposed
        return []

    def current(self, known: dict) -> Step | None:
        lacking = _lacking(known)
        if not self.touring:
            return STEPS[lacking[0]] if lacking else None
        for step in ORDER:
            if step.name in REQUIRED:
                if step.name in lacking:
                    return step
            elif step.name not in self.offered and (not step.picks or self.choices(step, known)):
                return step
        return None

    def skip(self, step: Step) -> None:
        self.offered.add(step.name)

    def end_tour(self) -> None:
        self.touring = False

    def submit(self, step: Step, raw: dict, known: dict) -> None:
        self.message = getattr(self, f"_apply_{step.name}", self._apply_command)(step, raw, known) or ""
        self.offered.add(step.name)

    def _apply_command(self, step: Step, raw: dict, known: dict) -> str:
        if step.command:
            answers = clean(step, raw)
            _ws(*_argv(step, _without_identity_details(answers) if step.name == "person" else answers))
        return ""

    def _apply_workspace(self, step: Step, raw: dict, known: dict) -> str:
        # A test run stays in its temporary folder, whatever was answered.
        root = clean(step, raw).get("root", "")
        chosen = str(Path(root).expanduser()) if root else ""
        same = chosen == str(Path(known["root"]).expanduser())
        _ws(*(("init",) if known["test"] or same or not chosen else ("init", "--root", chosen)))
        return ""

    def _apply_projects(self, step: Step, raw: dict, known: dict) -> str:
        answers = clean(step, raw)
        subfields = []
        for pair in answers.get("subfields", []):
            field, slash, subfield = pair.partition("/")
            if not slash or not field.strip() or not subfield.strip():
                raise SetupError(f"Write a subfield as field/subfield, not '{pair}'")
            subfields.append((field.strip(), subfield.strip()))
        if answers.get("purpose") and not answers.get("project"):
            raise SetupError("Name the project that purpose belongs to")
        for field in [*answers.get("fields", []), *(field for field, _ in subfields)]:
            _ws("projects", "add-field", field)
        for field, subfield in subfields:
            _ws("projects", "add-subfield", field, subfield)
        for kind in answers.get("types", []):
            _ws("projects", "add-type", kind)
        name = answers.get("project")
        if name:
            key = catalog.key_slug(name)
            try:
                _ws("create", "project", name, "--non-interactive")
            except SetupError as problem:
                if "already exists" not in str(problem):
                    raise
            if answers.get("purpose"):
                folder = Path(known["root"]).expanduser() / "projects" / "items" / key
                _add_note(folder / context.CONTEXT / "purpose.md", answers["purpose"])
            self.made["projects"].append((f"project:{key}", name))
        return ""

    def _apply_literature(self, step: Step, raw: dict, known: dict) -> str:
        author = clean(step, raw).get("author")
        if not author:
            return ""
        self.author = author
        try:
            self.found = json.loads(_ws(
                "literature", "search-arxiv", "--author", author, "--max", "25", "--sort", "submittedDate", "--json",
            ))
        except SetupError as problem:
            raise SetupError(f"Could not search arXiv: {problem}. Try again, or leave it empty to skip.") from problem
        return "" if self.found else f"arXiv has no papers under {author}."

    def _apply_papers(self, step: Step, raw: dict, known: dict) -> str:
        titles = {row["id"]: row.get("title", row["id"]) for row in self.found}
        added, failed = 0, []
        for paper in raw.get("chosen") or []:
            try:
                output = _ws("add", "literature", paper, "--full")
            except SetupError as problem:
                output = str(problem)
                if "already exists" not in output:
                    failed.append(f"{paper}: {output}")
                    continue
            match = re.search(r"items/([^/\s]+)", output)
            if match:
                self.made["papers"].append((f"literature:{match.group(1)}", titles.get(paper, paper)))
                added += 1
        note = f"Added {added} to your library."
        return f"{note} These could not be added: {'; '.join(failed)}" if failed else note

    def _apply_documents(self, step: Step, raw: dict, known: dict) -> str:
        answers = clean(step, raw)
        for kind in answers.get("types", []):
            _ws("documents", "types", "add", kind)
        if answers.get("file"):
            # A file dragged onto a terminal arrives quoted or with escaped spaces.
            path = Path(answers["file"].strip("'\"").replace("\\ ", " ")).expanduser()
            output = _ws("add", "document", str(path), "--mode", "copy", "--non-interactive", "--ensure", *_provenance())
            self.made["documents"].append((_made_ref(output, "document"), path.stem))
        return ""

    def _apply_resources(self, step: Step, raw: dict, known: dict) -> str:
        name = clean(step, raw).get("resource")
        if name:
            ref = _made_ref(_ws("create", "resource", name, "--ensure", *_provenance()), "resource")
            self.made["resources"].append((ref, name))
        return ""

    def _apply_tasks(self, step: Step, raw: dict, known: dict) -> str:
        answers = clean(step, raw)
        if answers.get("due") and not answers.get("task"):
            raise SetupError("Name the task that date belongs to")
        if answers.get("task"):
            due = ["--due", answers["due"]] if answers.get("due") else []
            ref = _made_ref(_ws("create", "task", answers["task"], *due, "--non-interactive", "--ensure", *_provenance()), "task")
            self.made["tasks"].append((ref, answers["task"]))
        return ""

    def _apply_people(self, step: Step, raw: dict, known: dict) -> str:
        answers = clean(step, raw)
        for kind, word in (("organisations", "organisation"), ("people", "person")):
            for name in answers.get(kind, []):
                ref = _made_ref(_ws("add", word, name, "--ensure", "--non-interactive", *_provenance()), word)
                self.made[kind].append((ref, name))
        return ""

    def _apply_relations(self, step: Step, raw: dict, known: dict) -> str:
        chosen = raw.get("chosen") or []
        for item in chosen:
            subject, word, ref = item.split(" ", 2)
            _ws("relate", subject, "to", ref, "as", word, *_provenance())
        return f"Made {len(chosen)} relation(s)." if chosen else ""

    def _apply_briefing(self, step: Step, raw: dict, known: dict) -> str:
        answers = clean(step, raw)
        notes = Path(known["root"]).expanduser() / context.CONTEXT
        for key, name in (("goals", "purpose.md"), ("rules", "instructions.md"), ("note", "whereami.md")):
            if answers.get(key):
                _add_note(notes / name, answers[key])
        return ""


def _short_authors(authors: str) -> str:
    """arXiv's `a and b and c`, cut short: some papers have dozens of authors."""
    names = [name.strip() for name in authors.split(" and ") if name.strip()]
    return ", ".join(names) if len(names) <= AUTHORS_SHOWN else f"{', '.join(names[:AUTHORS_SHOWN])} and {len(names) - AUTHORS_SHOWN} more"


def _provenance() -> list[str]:
    return ["--source", "ws setup", "--observed-at", dt.date.today().isoformat()]


def position(step: Step) -> str:
    for number, (words, steps) in enumerate(PARTS, start=1):
        if step in steps:
            return f"Part {number} of {len(PARTS)}: {words}"
    return ""


def progress(step: Step) -> float:
    return ORDER.index(step) / len(ORDER)


def owner_summary() -> str:
    return _ws("owner").rstrip()


GRAPH_NAMES = 3
AUTHORS_SHOWN = 4
TEST_NOTICE = "TEST RUN: everything you enter stays in a temporary folder, deleted at the end."
TEST_OVER = "That was a test: nothing was kept. For real, run `ws setup`."


def first_graph(known: dict) -> list[str]:
    """The owner's corner of the graph in words, and where to explore all of it."""
    person = known["owner"]["person"] if known["owner"] else ""
    if not person:
        return []
    edges: dict[tuple[str, str], list[str]] = {}
    for edge in json.loads(_ws("show", person, "--json")).get("relations", []):
        edges.setdefault((edge["relation"], edge["direction"]), []).append(edge["other_name"] or edge["other"])
    lines = [f"{known['name']} ({person})"]
    for (word, direction), names in sorted(edges.items()):
        arrow = f"--{word}-->" if direction == "out" else f"<--{word}--"
        more = f", and {len(names) - GRAPH_NAMES} more" if len(names) > GRAPH_NAMES else ""
        lines.append(f"  {arrow} {', '.join(sorted(names)[:GRAPH_NAMES])}{more}")
    return lines


def rebuild_graph_page(known: dict) -> Path:
    _ws("rebuild", "dashboard")
    return Path(known["root"]).expanduser() / "dashboard.html"


def briefing_now(known: dict) -> str:
    """What a session starting at the workspace's root is told. A bare `ws context`
    reads the folder it runs in."""
    return _ws("context", cwd=Path(known["root"]).expanduser()).rstrip()


def _ask_choices(choices: list[dict]) -> dict:
    for number, choice in enumerate(choices, start=1):
        print(f"  {number}. {choice['label']}")
    default = "all" if all(choice["checked"] for choice in choices) else "none"
    typed = input(f"\n  Which? Numbers separated by commas, all, or none [{default}]: ").strip().lower() or default
    if typed == "none":
        return {"chosen": []}
    if typed == "all":
        return {"chosen": [choice["id"] for choice in choices]}
    picked = []
    for word in typed.split(","):
        if not word.strip().isdigit() or not 1 <= int(word) <= len(choices):
            raise SetupError(f"'{word.strip()}' is not one of the numbers")
        picked.append(choices[int(word) - 1]["id"])
    return {"chosen": picked}


def _ask_questions(step: Step, known: dict, session: Session) -> dict:
    raw = {}
    for question in step.questions:
        default = session.default_of(question, known)
        hint = f" [{default}]" if default else "" if question.required else " (Enter skips)"
        if question.many:
            hint = f" (separate with commas){hint}"
        while True:
            raw[question.key] = input(f"  {question.ask}{hint}: ").strip() or default
            if raw[question.key] or not question.required:
                break
            print("  This one is needed.")
    return raw


def run_terminal() -> None:
    session = Session()
    known = current_state()
    print("WS SETUP\n")
    if known["test"]:
        print(f"{TEST_NOTICE}\n")
    while (step := session.current(known)) is not None:
        print(f"{position(step)}\n\n{step.title.upper()}\n\n{explain(step, known)}\n")
        if known["test"] and step.name == "workspace":
            print("In this test run the answer is ignored.\n")
        try:
            choices = session.choices(step, known)
            if choices:
                raw = _ask_choices(choices)
            elif step.questions:
                raw = _ask_questions(step, known, session)
            else:
                raw = {}
                if input("  Press Enter to go on, or type skip to jump to the end: ").strip().lower() == "skip":
                    session.end_tour()
            print()
            session.submit(step, raw, known)
            if session.message:
                print(f"{session.message}\n")
        except SetupError as problem:
            print(f"That did not work: {problem}\n")
        known = current_state()
    graph = first_graph(known)
    page = rebuild_graph_page(known) if graph else None
    if graph:
        print("Your first knowledge graph:\n\n" + "\n".join(graph) + f"\n\nThe whole graph, to explore: {page}\n")
        if sys.stdin.isatty() and input("  Open it in your browser? [Y/n]: ").strip().lower() in {"", "y", "yes"}:
            webbrowser.open(page.as_uri())
    print(f"What your agent reads:\n\n{_text('reads')}\n\n{briefing_now(known)}\n")
    print(f"When it needs your details, it runs `ws owner`:\n\n{owner_summary()}\n")
    print(_text("done"))
    if known["test"]:
        if sys.stdin.isatty():
            input("\n  This test run ends, and its graph goes, when you press Enter: ")
        print(f"\n{TEST_OVER}")


def render_step(step: Step, known: dict) -> str:
    parts = [f"EXPLAIN\n\n{explain(step, known)}"]
    if step.questions:
        asks = []
        for question in step.questions:
            default = default_of(question, known)
            asks.append(f"- {question.ask}" + (f" (default: {default})" if default else ""))
        parts.append("ASK\n\n" + "\n".join(asks))
    if step.questions or step.howto:
        how = "\n".join(f"    {line}" for line in template(step).replace("{root}", known["root"]).splitlines())
        parts.append(f"RUN, leaving out what they skipped\n\n{how}")
    return "\n\n".join(parts)


# What an agent goes through. Which papers to pick only arises from its own search.
FOR_AGENTS = tuple(step for step in ORDER if step.picks != "papers")
END = "end"


def render(known: dict) -> str:
    """What an agent reads first: the steps, and which are done already."""
    lacking = _lacking(known)
    rows = [
        f"  {step.name:<12}{step.title}" + ("  (already in place)" if step.name in REQUIRED and step.name not in lacking else "")
        for step in FOR_AGENTS
    ]
    rows.append(f"  {END:<12}their first knowledge graph, the briefing, and what follows")
    state_line = (
        "The workspace and its owner are in place, so everything left is optional."
        if known["complete"]
        else f"Required and still missing: {', '.join(lacking)}."
    )
    return "\n\n".join([
        "WS SETUP",
        _text("guide"),
        state_line,
        "THE STEPS, IN ORDER",
        "\n".join(rows),
        f"Start with: ws setup --step {FOR_AGENTS[0].name}",
    ])


def render_end(known: dict) -> str:
    """The last page for an agent: show them what they built, then what follows."""
    instructions = (
        f"Run `ws rebuild dashboard` and show them the graph in {known['root']}/dashboard.html. Then run "
        f"`ws context` in {known['root']} and show them its output, and `ws owner`. Tell them what follows, "
        "in your own words. Do only what they accept, and show them any change to their agent's settings first."
    )
    return "\n\n".join([
        f"WS SETUP: {END}",
        instructions,
        f"ABOUT THE BRIEFING\n\n{_text('reads')}",
        _text("done"),
    ])


def render_named(name: str, known: dict) -> str:
    """One step for an agent, ending on which to read next."""
    if name == END:
        return render_end(known)
    names = [step.name for step in FOR_AGENTS]
    if name not in names:
        catalog.fail(f"no setup step called '{name}'; the steps are {', '.join([*names, END])}")
    step = STEPS[name]
    done = step.name in REQUIRED and step.name not in _lacking(known)
    upcoming = names[names.index(name) + 1] if names.index(name) + 1 < len(names) else END
    body = "This is already in place, so there is nothing to ask. Go on to the next step." if done else render_step(step, known)
    return "\n\n".join([
        f"WS SETUP: {step.title} ({position(step).lower()})",
        body,
        f"NEXT\n\n    ws setup --step {upcoming}",
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
    elif args.step:
        print(render_named(args.step, state()))
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
        "browser. Run by an agent, it prints the steps instead, and --step prints one: what to explain, "
        "what to ask, and which command to run. What is required and still missing is read from the "
        "workspace, so it can stop and resume at any point.",
        epilog="""Examples:
  ws setup                 ask here, or print the steps for an agent
  ws setup --step projects print one step, for an agent
  ws setup --web           ask in a browser
  ws setup --test          try it at the terminal; nothing is kept
  ws setup --web --test    try it in a browser; nothing is kept
""",
    )
    parser.add_argument("--web", action="store_true", help="ask in a browser, through a server only this machine can reach")
    parser.add_argument("--test", action="store_true", help="use a temporary workspace, deleted at the end; your own is not touched")
    parser.add_argument("--no-browser", action="store_true", help="with --web, print the address instead of opening it")
    parser.add_argument("--step", metavar="NAME", help="print one step, for an agent to carry out")
    parser.add_argument("--interactive", action="store_true", help="ask questions even without a terminal")
    parser.add_argument("--non-interactive", action="store_true", help="print the steps even at a terminal")
    parser.add_argument("--json", action="store_true", help="print the state and the steps as JSON")
    parser.set_defaults(func=command_setup)
