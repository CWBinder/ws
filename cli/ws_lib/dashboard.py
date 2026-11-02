"""The workspace dashboard: one derived, self-contained HTML page.

`ws rebuild dashboard` reads every object and relation and renders
`dashboard.html` at the workspace root -- what is due, what is new, which
projects are live, what is still unconnected, and the whole graph. Like the
index and the wiki it is derived: deleting it loses nothing, and rebuilding it
never touches a record (contracts/dashboard.md).
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import os
import tempfile
from pathlib import Path

from ws_lib import catalog, paths, relations


DASHBOARD = paths.WORKSPACE / "dashboard.html"
TEMPLATE = paths.TEMPLATES / "dashboard.html"

# Task statuses that no longer ask for anything; shared with `ws list tasks --open`.
CLOSED_TASKS = catalog.CLOSED_TASKS


def _day(value) -> str:
    """The ISO date at the front of a date or datetime value, else ''."""
    text = str(value or "").strip()
    try:
        return dt.date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return ""


def _added(ref: catalog.ObjectRef) -> str:
    """When an object entered the workspace: its record's created_at, a
    project's created date, or -- for literature, which records none -- the
    day its citation file was written."""
    data = ref.data or {}
    day = _day(data.get("created_at")) or _day(data.get("created"))
    if not day and ref.type == "literature" and ref.path is not None and ref.path.exists():
        day = dt.date.fromtimestamp(ref.path.stat().st_mtime).isoformat()
    return day


def collect() -> dict:
    """Everything the page shows, as plain data. Reads records only."""
    objects = catalog.all_objects()
    by_id = {ref.id: ref for ref in objects}
    edges = [
        row for row in relations.load_all()
        if str(row.get("subject", "")) in by_id and str(row.get("object", "")) in by_id
    ]
    degree = collections.Counter()
    for row in edges:
        degree[str(row["subject"])] += 1
        degree[str(row["object"])] += 1

    # Hubs first: the page lays them out from the centre and labels them first.
    order = sorted(objects, key=lambda ref: (-degree[ref.id], ref.type, str(ref.title).casefold()))
    position = {ref.id: index for index, ref in enumerate(order)}
    name = lambda ref: " ".join(str(ref.title).split())

    pairs: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for row in edges:
        word = str(row.get("relation") or "related")
        pairs[word][f"{by_id[str(row['subject'])].type} → {by_id[str(row['object'])].type}"] += 1

    tasks, events, projects, recent = [], [], [], []
    for ref in objects:
        data = ref.data or {}
        status = str(data.get("status", "") or "").strip().lower()
        if ref.type == "task" and status not in CLOSED_TASKS:
            tasks.append({
                "i": position[ref.id], "due": _day(data.get("due")),
                "priority": str(data.get("priority", "") or ""), "status": status or "open",
            })
        elif ref.type == "event" and _day(data.get("start")):
            events.append({"i": position[ref.id], "start": _day(data.get("start")), "end": _day(data.get("end"))})
        elif ref.type == "project":
            projects.append({"i": position[ref.id], "status": status or "active"})
        added = _added(ref)
        if added:
            recent.append({"i": position[ref.id], "added": added})
    recent.sort(key=lambda item: item["added"], reverse=True)

    now = dt.datetime.now()
    return {
        "built": now.isoformat(timespec="minutes"),
        "root": str(paths.WORKSPACE),
        "nodes": [
            {"ref": ref.ref, "kind": ref.type, "name": name(ref), "deg": degree[ref.id]}
            for ref in order
        ],
        "links": [
            {"s": position[str(row["subject"])], "t": position[str(row["object"])], "w": str(row.get("relation") or "related")}
            for row in edges
        ],
        "vocab": [
            {"w": word, "n": sum(counter.values()), "pairs": counter.most_common()}
            for word, counter in sorted(pairs.items())
        ],
        "kinds": dict(collections.Counter(ref.type for ref in objects)),
        "tasks": tasks,
        "events": events,
        "projects": projects,
        "recent": recent[:40],
        "totals": {
            "objects": len(objects),
            "relations": len(edges),
            "words": len(pairs),
            "connected": sum(1 for ref in objects if degree[ref.id]),
        },
    }


def render(data: dict) -> str:
    # `</` would end the embedding script element early; JSON allows `<\/`.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", payload)


def build(target: Path | None = None) -> dict:
    target = target or DASHBOARD
    data = collect()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".dashboard.", suffix=".html", dir=target.parent)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(render(data))
    # mkstemp makes the file private; the page is an ordinary document.
    os.chmod(temporary, 0o644)
    os.replace(temporary, target)
    return {"path": str(target), **data["totals"], "open_tasks": len(data["tasks"])}
