"""The context layer: what a fresh session needs to know about where it starts.

A briefing answers four questions about one place in the workspace: where it
is, what the object there is for, what has happened, and how to work there
(contracts/context.md). The hand-written part lives in `.context/` folders.
The workspace root and each store folder may hold `whereami.md` and
`instructions.md`; a folder-backed object (a project, a resource) may also
hold `purpose.md` and `log.md`. ws ships the generic layers for the root and
the stores under `context/` in its checkout, and the workspace's own files add
to them. Where an object stands among the others is computed from the
relations. Nothing here writes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ws_lib import catalog, dashboard, paths, relations


WORKSPACE = paths.WORKSPACE
SHIPPED = paths.SYSTEM / "context"
CONTEXT = ".context"

# The store folders, named by the word a briefing uses for them.
STORES = {
    "projects": paths.PROJECTS_DOMAIN,
    "resources": paths.RESOURCES,
    "literature": paths.LITERATURE,
    "documents": paths.DOCUMENTS,
    "tasks": paths.TASKS,
    "logistics": paths.LOGISTICS,
    "profile": paths.CAREER,
}
STORE_OF_KIND = {
    "project": "projects",
    "resource": "resources",
    "literature": "literature",
    "document": "documents",
    "task": "tasks",
    "person": "logistics",
    "organisation": "logistics",
    "event": "logistics",
    "profile": "profile",
}
FOLDER_KINDS = {"project", "resource", "literature"}

# The aspects `ws show ASPECT of REF` prints one at a time. Relations are an
# aspect too, but `ws show REF` already lists them under the record.
ASPECTS = ("purpose", "log", "location", "instructions")

# What a neighbour means for the work here. The first phrase reads along an
# outgoing edge (this --word--> other), the second along an incoming one
# (other --word--> this). Only words where the gloss tells an agent something
# beyond the word itself are listed; the vocabulary stays open (`ws relations`).
MEANINGS = {
    "contributes-to": ("the purpose this one serves", "builds towards this one"),
    "depends-on": (
        "this builds on it; change it in its own folder, not from here",
        "builds on this one; a change here can break it",
    ),
    "related-to": (
        "a sibling; its log may already hold what is needed here",
        "a sibling; its log may already hold what is needed here",
    ),
    "references": (
        "literature this builds on: read it before reinventing, cite it",
        "draws on this one",
    ),
    "works-on": ("works on it", "works on this one: who to discuss it with"),
    "describes": ("documents it", "documentation of this one: read it before changing things"),
    "presents": ("presents it", "a presentation of this one"),
    "supports": ("supporting material for it", "supporting material for this one"),
    "part-of": ("part of it", "part of this one"),
    "co-authored": ("an author of it", "one of its authors"),
    "supervises": ("supervises them", "supervises this person"),
    "co-supervises": ("co-supervises them", "co-supervises this person"),
    "advises": ("advises them", "advises this person"),
}

LATEST_LOG_ENTRIES = 3
ENTRY_LINES = 25
GROUP_ITEMS = 8
LISTED_OBJECTS = 40
DUE_SOON_DAYS = 7
EVENTS_AHEAD_DAYS = 14


@dataclass(frozen=True)
class Place:
    """Where a briefing stands: the workspace root, one store, or one object.

    `home` is the object's own folder; record-only kinds (people, tasks,
    events, ...) have none, so they have no purpose or log of their own."""

    level: str
    store: str = ""
    obj: catalog.ObjectRef | None = None
    home: Path | None = None


def _within(path: Path, folder: Path) -> bool:
    return path == folder or folder in path.parents


def _home_path(path: Path) -> str:
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def _read(path: Path) -> str:
    """A context file's text, or '' when it is absent or empty. Shipped texts
    may name the ws checkout as `{system}`."""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8").strip()
    return text.replace("{system}", _home_path(paths.SYSTEM))


def _clean(name: str, width: int = 90) -> str:
    """A display name on one line: markup from imported titles stripped."""
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", str(name))).strip()
    return text if len(text) <= width else text[: width - 1].rstrip() + "…"


def _first_paragraph(text: str) -> str:
    return text.strip().split("\n\n", 1)[0].replace("\n", " ").strip()


def home_of(ref: catalog.ObjectRef) -> Path | None:
    """The folder a folder-backed object owns: a project's (or subproject's)
    folder, a resource bundle, a literature item."""
    if ref.type in FOLDER_KINDS and ref.path is not None:
        return ref.path.parent
    return None


def _store_of(folder: Path) -> str:
    return next(
        (name for name, directory in STORES.items() if _within(folder, directory.resolve())),
        "",
    )


def place_of_folder(folder: Path, objects: list[catalog.ObjectRef]) -> Place | None:
    """The place a session started in `folder` stands, or None outside the
    workspace. The deepest enclosing object folder wins, so a session in a
    project's code/ is briefed on that project."""
    folder = folder.resolve()
    if not _within(folder, WORKSPACE.resolve()):
        return None
    enclosing = [
        (ref, home.resolve())
        for ref in objects
        if (home := home_of(ref)) is not None and _within(folder, home.resolve())
    ]
    if enclosing:
        ref, home = max(enclosing, key=lambda item: len(item[1].parts))
        return Place("object", STORE_OF_KIND.get(ref.type, ""), ref, home)
    store = _store_of(folder)
    return Place("store", store) if store else Place("workspace")


def place_of_ref(value: str) -> Place:
    ref = catalog.resolve(value)
    return Place("object", STORE_OF_KIND.get(ref.type, ""), ref, home_of(ref))


def _folder(place: Place) -> Path | None:
    """The folder whose `.context/` holds this place's own notes."""
    if place.level == "object":
        return place.home
    if place.level == "store":
        return STORES[place.store]
    return WORKSPACE


def _levels(place: Place) -> list[tuple[str, Path, str]]:
    """(label, folder, shipped text name) for each level from the root down."""
    levels = [("workspace", WORKSPACE, "workspace")]
    if place.store:
        levels.append((place.store, STORES[place.store], place.store))
    if place.level == "object" and place.home is not None:
        levels.append((place.obj.ref, place.home, ""))
    return levels


def layers(place: Place, name: str) -> list[dict]:
    """The `whereami` or `instructions` text for a place, from the root down:
    at each level the text ws ships first, then the workspace's own file."""
    rows = []
    for label, folder, shipped in _levels(place):
        sources = [(SHIPPED / name / f"{shipped}.md", True)] if shipped else []
        sources.append((folder / CONTEXT / f"{name}.md", False))
        for source, is_shipped in sources:
            text = _read(source)
            if text:
                rows.append({"level": label, "source": _home_path(source), "shipped": is_shipped, "text": text})
    return rows


def _readme_purpose(readme: Path) -> str:
    match = re.search(
        r"^##\s+Purpose\s*$(.*?)(?=^##\s|\Z)", _read(readme), re.MULTILINE | re.DOTALL
    )
    return match.group(1).strip() if match else ""


def purpose(place: Place) -> dict | None:
    """What the place is for: its `.context/purpose.md`. A project that has
    none yet falls back to its README's Purpose section, marked as such."""
    folder = _folder(place)
    if folder is None:
        return None
    source = folder / CONTEXT / "purpose.md"
    text = _read(source)
    if text:
        return {"text": text, "source": _home_path(source), "fallback": ""}
    if place.obj is not None and place.obj.type == "project":
        readme = folder / "README.md"
        text = _readme_purpose(readme)
        if text:
            return {
                "text": text,
                "source": _home_path(readme),
                "fallback": "README.md's Purpose section; no .context/purpose.md yet",
            }
    return None


def serves(obj: catalog.ObjectRef, by_ref: dict[str, catalog.ObjectRef]) -> list[dict]:
    """The chain of purposes above an object, following outgoing
    `contributes-to` edges until one has none (or the chain loops)."""
    chain: list[dict] = []
    seen = {obj.id}
    current = obj
    while True:
        upward = [
            edge for edge in relations.edges_of(current.id, "contributes-to")
            if edge["direction"] == "out"
        ]
        target = by_ref.get(upward[0]["other"]) if upward else None
        if target is None or target.id in seen:
            return chain
        seen.add(target.id)
        found = purpose(Place("object", STORE_OF_KIND.get(target.type, ""), target, home_of(target)))
        chain.append({
            "ref": target.ref,
            "name": _clean(target.title),
            "purpose": _first_paragraph(found["text"]) if found else "",
        })
        current = target


def _task_row(task: catalog.ObjectRef, today: dt.date) -> dict:
    data = task.data or {}
    due = dashboard._day(data.get("due"))
    return {
        "ref": task.ref,
        "name": _clean(task.title),
        "due": due,
        "priority": str(data.get("priority", "") or ""),
        "status": str(data.get("status", "") or "") or "open",
        "overdue": bool(due) and due < today.isoformat(),
    }


def _is_open(task: catalog.ObjectRef) -> bool:
    status = str((task.data or {}).get("status", "") or "").strip().lower()
    return status not in dashboard.CLOSED_TASKS


def _by_due(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (not row["due"], row["due"], row["name"].casefold()))


def neighbourhood(obj: catalog.ObjectRef, by_ref: dict[str, catalog.ObjectRef]) -> tuple[list[dict], list[dict]]:
    """An object's neighbours grouped by relation and direction, each group
    with what it means for the work here, plus the open tasks around it.
    Tasks list separately; the purpose chain shows under the purpose."""
    today = dt.date.today()
    groups: dict[tuple[str, str], list[dict]] = {}
    tasks: list[dict] = []
    for edge in relations.edges_of(obj.id):
        if edge["relation"] == "contributes-to" and edge["direction"] == "out":
            continue
        other = by_ref.get(edge["other"])
        if other is not None and other.type == "task" and obj.type != "task":
            if _is_open(other):
                tasks.append(_task_row(other, today))
            continue
        name = _clean(edge["other_name"]) if edge["other_name"] else ""
        groups.setdefault((edge["relation"], edge["direction"]), []).append(
            {"ref": edge["other"], "name": name}
        )
    rows = []
    for (word, direction), items in groups.items():
        out_meaning, in_meaning = MEANINGS.get(word, ("", ""))
        rows.append({
            "relation": word,
            "direction": direction,
            "meaning": out_meaning if direction == "out" else in_meaning,
            "count": len(items),
            "items": sorted(items, key=lambda item: (item["name"].casefold(), item["ref"])),
        })
    rows.sort(key=lambda row: (row["direction"] != "out", -row["count"], row["relation"]))
    return rows, _by_due(tasks)


def agenda(objects: list[catalog.ObjectRef]) -> dict:
    """What the whole workspace asks for now: open tasks overdue or due within
    a week, events in the next two weeks, and the active projects."""
    today = dt.date.today()
    soon = (today + dt.timedelta(days=DUE_SOON_DAYS)).isoformat()
    horizon = (today + dt.timedelta(days=EVENTS_AHEAD_DAYS)).isoformat()
    due, later = [], 0
    events, projects = [], []
    for ref in objects:
        data = ref.data or {}
        if ref.type == "task" and _is_open(ref):
            row = _task_row(ref, today)
            if row["due"] and row["due"] <= soon:
                due.append(row)
            else:
                later += 1
        elif ref.type == "event":
            start = dashboard._day(data.get("start"))
            end = dashboard._day(data.get("end")) or start
            if start and start <= horizon and end >= today.isoformat():
                events.append({"ref": ref.ref, "name": _clean(ref.title), "start": start, "end": end})
        elif ref.type == "project" and str(data.get("status", "") or "active") == "active":
            projects.append({"ref": ref.ref, "name": _clean(ref.title)})
    return {
        "due": _by_due(due),
        "other_open_tasks": later,
        "events": sorted(events, key=lambda row: (row["start"], row["name"])),
        "active_projects": sorted(projects, key=lambda row: row["ref"]),
    }


def store_listing(store: str, objects: list[catalog.ObjectRef]) -> dict:
    """A store's contents in brief: the projects or resources themselves,
    otherwise how many records it holds."""
    kinds = {kind for kind, name in STORE_OF_KIND.items() if name == store}
    members = [ref for ref in objects if ref.type in kinds]
    rows = []
    if store in {"projects", "resources"}:
        rows = [
            {
                "ref": ref.ref,
                "name": _clean(ref.title),
                "status": str((ref.data or {}).get("status", "") or ""),
            }
            for ref in sorted(members, key=lambda ref: ref.ref)
        ]
    return {"count": len(members), "objects": rows}


def parse_log(text: str) -> list[dict]:
    """A log's entries, newest first as written: every `## ` heading starts
    one. Text before the first heading is the log's own preamble."""
    entries: list[dict] = []
    for line in text.splitlines():
        if line.startswith("## "):
            entries.append({"heading": line[3:].strip(), "body": []})
        elif entries:
            entries[-1]["body"].append(line)
    for entry in entries:
        entry["body"] = "\n".join(entry["body"]).strip()
    return entries


def log(place: Place) -> dict | None:
    """The place's log: `.context/log.md`, or a project's root `LOG.md`
    where it has not moved yet."""
    folder = _folder(place)
    if folder is None:
        return None
    path = folder / CONTEXT / "log.md"
    older = False
    is_project = place.obj is not None and place.obj.type == "project"
    if not path.is_file() and is_project and (folder / "LOG.md").is_file():
        path, older = folder / "LOG.md", True
    if not path.is_file():
        return None
    return {
        "path": _home_path(path),
        "older_location": older,
        "entries": parse_log(path.read_text(encoding="utf-8")),
    }


def _briefed_entries(entries: list[dict]) -> list[dict]:
    """The latest entries, plus any condensed summary further down."""
    latest = entries[:LATEST_LOG_ENTRIES]
    summaries = [entry for entry in entries[LATEST_LOG_ENTRIES:] if "summar" in entry["heading"].casefold()]
    return latest + summaries


def subject(place: Place) -> str:
    if place.level == "object":
        return f"{place.obj.ref} ({_clean(place.obj.title)})"
    if place.level == "store":
        return f"{place.store} (a store)"
    return "the workspace root"


def build(place: Place, objects: list[catalog.ObjectRef]) -> dict:
    """Everything one briefing says, as plain data."""
    by_ref = {ref.ref: ref for ref in objects}
    brief: dict = {
        "briefing": place.level,
        "subject": subject(place),
        "ref": place.obj.ref if place.obj else "",
        "store": place.store,
        "folder": _home_path(_folder(place)) if _folder(place) else "",
        "whereami": layers(place, "whereami"),
        "instructions": layers(place, "instructions"),
        "purpose": purpose(place),
        "log": log(place),
    }
    if place.obj is not None:
        neighbours, tasks = neighbourhood(place.obj, by_ref)
        brief["description"] = str((place.obj.data or {}).get("description", "") or "").strip()
        brief["neighbours"] = neighbours
        brief["tasks"] = tasks
        brief["serves"] = serves(place.obj, by_ref)
    elif place.level == "store":
        brief["listing"] = store_listing(place.store, objects)
    else:
        brief["agenda"] = agenda(objects)
    return brief


def _indented(text: str, depth: int = 4) -> list[str]:
    pad = " " * depth
    return [pad + line if line.strip() else "" for line in text.splitlines()]


def _layer_lines(rows: list[dict]) -> list[str]:
    """Each layer under a label naming its level and where its text comes
    from: `ws` for the text ws ships, otherwise the workspace's own file."""
    lines = []
    for row in rows:
        origin = "ws" if row.get("shipped") else row["source"]
        lines.append(f"  [{row['level']} · {origin}]")
        lines.extend(_indented(row["text"]))
    return lines


def _task_line(row: dict) -> str:
    details = [f"due {row['due']}" + (" (overdue)" if row["overdue"] else "")] if row["due"] else []
    if row["priority"]:
        details.append(row["priority"])
    suffix = f"  [{', '.join(details)}]" if details else ""
    return f"    {row['ref']}  {row['name']}{suffix}"


def location_lines(brief: dict) -> list[str]:
    lines = ["WHERE YOU ARE"]
    lines.extend(_layer_lines(brief["whereami"]))
    if brief["briefing"] == "object":
        lines.append(f"  This: {brief['subject']}" + (f", {brief['folder']}" if brief["folder"] else ""))
        if brief.get("description"):
            lines.extend(_indented(brief["description"]))
        if brief["neighbours"]:
            lines.append("  Around it:")
            for group in brief["neighbours"]:
                word = group["relation"]
                arrow = f"--{word}-->" if group["direction"] == "out" else f"<--{word}--"
                meaning = f"  ({group['meaning']})" if group["meaning"] else ""
                lines.append(f"    {arrow}{meaning}")
                for item in group["items"][:GROUP_ITEMS]:
                    lines.append(f"        {item['ref']}  {item['name']}".rstrip())
                hidden = group["count"] - GROUP_ITEMS
                if hidden > 0:
                    lines.append(f"        ... {hidden} more: ws show {brief['ref']} --as {word}")
        else:
            lines.append("  Around it: no relations yet")
    elif brief["briefing"] == "store":
        listing = brief["listing"]
        lines.append(f"  This store holds {listing['count']} object(s).")
        for row in listing["objects"][:LISTED_OBJECTS]:
            status = f"  [{row['status']}]" if row["status"] else ""
            lines.append(f"    {row['ref']}  {row['name']}{status}")
        if len(listing["objects"]) > LISTED_OBJECTS:
            lines.append(f"    ... {len(listing['objects']) - LISTED_OBJECTS} more")
    else:
        agenda_data = brief["agenda"]
        lines.append(f"  Active projects ({len(agenda_data['active_projects'])}):")
        lines.extend(f"    {row['ref']}  {row['name']}" for row in agenda_data["active_projects"])
    return lines


def upcoming_lines(brief: dict) -> list[str]:
    """What waits on the place: an object's open tasks, or the root's due
    tasks and coming events. A store has nothing of its own here."""
    if brief["briefing"] == "store":
        return []
    lines = ["UPCOMING"]
    if brief["briefing"] == "object":
        if brief["tasks"]:
            lines.append("  Open tasks about it:")
            lines.extend(_task_line(row) for row in brief["tasks"])
        else:
            lines.append("  no open tasks about it")
        return lines
    agenda_data = brief["agenda"]
    lines.append(f"  Due within {DUE_SOON_DAYS} days or overdue:")
    if agenda_data["due"]:
        lines.extend(_task_line(row) for row in agenda_data["due"])
    else:
        lines.append("    nothing")
    lines.append(f"  Other open tasks: {agenda_data['other_open_tasks']}")
    lines.append(f"  Events in the next {EVENTS_AHEAD_DAYS} days:")
    if agenda_data["events"]:
        for row in agenda_data["events"]:
            when = row["start"] if row["end"] == row["start"] else f"{row['start']} to {row['end']}"
            lines.append(f"    {when}  {row['ref']}  {row['name']}")
    else:
        lines.append("    none")
    return lines


def _missing(brief: dict, note: str) -> str:
    """What to say when a place has no purpose or log of its own."""
    if brief["briefing"] == "store":
        return {"purpose": "a store has no purpose of its own; its objects do", "log": "none"}[note]
    if not brief["folder"]:
        return {
            "purpose": "a record-only object has no purpose of its own",
            "log": "a record-only object keeps no log",
        }[note]
    if brief["briefing"] == "workspace" and note == "purpose":
        return f"none recorded yet: {brief['folder']}/{CONTEXT}/purpose.md holds the owner's goals"
    if brief["briefing"] == "workspace":
        return "none"
    return f"none recorded yet: {brief['folder']}/{CONTEXT}/{note}.md holds it"


def purpose_lines(brief: dict) -> list[str]:
    found = brief["purpose"]
    if found is None:
        lines = ["PURPOSE", f"  {_missing(brief, 'purpose')}"]
    else:
        origin = found["fallback"] or found["source"]
        lines = [f"PURPOSE  (from {origin})"]
        lines.extend(_indented(found["text"], 2))
    if brief["briefing"] == "object":
        if brief["serves"]:
            lines.append("  Serves:")
            for row in brief["serves"]:
                purpose_text = f": {_clean(row['purpose'], 110)}" if row["purpose"] else ""
                lines.append(f"    {row['ref']}  {row['name']}{purpose_text}")
        elif brief["folder"]:
            lines.append(f"  Serves: not recorded (ws relate {brief['ref']} to REF as contributes-to)")
    return lines


def log_lines(brief: dict, full: bool = False) -> list[str]:
    found = brief["log"]
    if found is None:
        return ["LOG", f"  {_missing(brief, 'log')}"]
    entries = found["entries"]
    note = ", older location: move it to .context/log.md" if found["older_location"] else ""
    lines = [f"LOG  ({found['path']}, {len(entries)} entries, newest first{note})"]
    shown = entries if full else _briefed_entries(entries)
    for entry in shown:
        lines.append(f"  ## {entry['heading']}")
        body = entry["body"].splitlines()
        if not full and len(body) > ENTRY_LINES:
            body = body[:ENTRY_LINES] + ["..."]
        lines.extend(_indented("\n".join(body), 2))
    if not full and len(shown) < len(entries):
        lines.append(f"  ... {len(entries) - len(shown)} older entries: ws show log of {brief['ref']}".rstrip())
    if not entries:
        lines.append("  no entries yet")
    return lines


def instruction_lines(brief: dict) -> list[str]:
    return ["HOUSE RULES", *_layer_lines(brief["instructions"])]


def _keeps_notes(brief: dict) -> bool:
    """Whether the place can hold a purpose and a log: the root and
    folder-backed objects can, stores and record-only objects cannot."""
    return brief["briefing"] == "workspace" or (brief["briefing"] == "object" and bool(brief["folder"]))


def render(brief: dict) -> str:
    """The briefing in reading order, most lasting first: where you are, how
    to work here, what it is for, what waits, what has happened. A section
    the place cannot have is left out unless a note for it exists anyway
    (a store that keeps a log shows it)."""
    keeps_notes = _keeps_notes(brief)
    has_purpose = keeps_notes or brief["purpose"] is not None or bool(brief.get("serves"))
    sections = [
        [
            f"WORKSPACE BRIEFING: {brief['subject']}",
            "Where you are, how to work here, what it is for, what is coming up, and what has happened.",
        ],
        location_lines(brief),
        instruction_lines(brief),
        purpose_lines(brief) if has_purpose else [],
        upcoming_lines(brief),
        log_lines(brief) if keeps_notes or brief["log"] is not None else [],
    ]
    return "\n\n".join("\n".join(lines) for lines in sections if lines)


def command_context(args: argparse.Namespace) -> None:
    """`ws context [REF]`: the briefing for an object, or for the folder the
    command runs in. Outside the workspace it prints nothing, so one
    session-start hook can run it everywhere."""
    if not args.ref and not _within(Path.cwd().resolve(), WORKSPACE.resolve()):
        # The hook runs this in every session; outside the workspace it must
        # cost nothing, so the early out comes before any catalog scan.
        if sys.stderr.isatty():
            print(
                f"note: {Path.cwd()} is outside the workspace ({_home_path(WORKSPACE)}); nothing to brief",
                file=sys.stderr,
            )
        return
    objects = catalog.all_objects()
    place = place_of_ref(args.ref) if args.ref else place_of_folder(Path.cwd(), objects)
    if place is None:
        return
    brief = build(place, objects)
    if args.json:
        print(json.dumps(brief, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render(brief))


def command_show_aspect(aspect: str, value: str, as_json: bool) -> None:
    """`ws show ASPECT of REF`: one aspect of an object, in full."""
    objects = catalog.all_objects()
    brief = build(place_of_ref(value), objects)
    if aspect == "purpose":
        data = {"ref": brief["ref"], "purpose": brief["purpose"], "serves": brief["serves"]}
        lines = purpose_lines(brief)
    elif aspect == "log":
        data = {"ref": brief["ref"], "log": brief["log"]}
        lines = log_lines(brief, full=True)
    elif aspect == "location":
        data = {
            key: brief[key]
            for key in ("ref", "folder", "store", "description", "whereami", "neighbours", "tasks")
        }
        lines = location_lines(brief) + [""] + upcoming_lines(brief)
    else:
        data = {"ref": brief["ref"], "instructions": brief["instructions"]}
        lines = instruction_lines(brief)
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("\n".join(lines))


def show_summary(ref: catalog.ObjectRef) -> dict:
    """What `ws show REF` adds for an object's own context notes: the first
    paragraph of its purpose and the shape of its log. Only `.context/`
    counts here; older fallbacks belong to the briefing."""
    home = home_of(ref)
    if home is None:
        return {}
    summary: dict = {}
    text = _read(home / CONTEXT / "purpose.md")
    if text:
        summary["purpose"] = _first_paragraph(text)
    log_path = home / CONTEXT / "log.md"
    if log_path.is_file():
        entries = parse_log(log_path.read_text(encoding="utf-8"))
        summary["log"] = {
            "path": _home_path(log_path),
            "entries": len(entries),
            "latest": entries[0]["heading"] if entries else "",
        }
    return summary


def show_summary_lines(ref: catalog.ObjectRef, summary: dict) -> list[str]:
    lines = []
    if "purpose" in summary:
        lines.append(f"purpose: {_clean(summary['purpose'], 160)}  (ws show purpose of {ref.ref})")
    if "log" in summary:
        found = summary["log"]
        latest = f", latest {found['latest']}" if found["latest"] else ""
        lines.append(f"log: {found['entries']} entries{latest}  (ws show log of {ref.ref})")
    return lines


def add_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "context",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="brief a session on where it is: location, house rules, purpose, upcoming, log",
        description="Brief a fresh session on one place in the workspace: where it is, "
        "how to work there, what the object there is for, what is coming up, and what has happened. "
        "Without a REF it briefs the folder it runs in, and outside the workspace "
        "it prints nothing, so a session-start hook can run it anywhere.",
        epilog="""Examples:
  ws context                          the folder you are in: an object, a store, or the root
  ws context project:<key>            one object, wherever you are
  ws show purpose of project:<key>    one aspect in full: purpose, log, location, instructions

The notes behind a briefing live in .context/ folders (whereami.md,
instructions.md, purpose.md, log.md); the relations supply the neighbourhood.
""",
    )
    parser.add_argument(
        "ref",
        nargs="?",
        metavar="REF",
        help="canonical kind:<key>; omitted, the folder the command runs in",
    )
    parser.add_argument("--json", action="store_true", help="print JSON")
    parser.set_defaults(func=command_context)
