"""Rebuildable SQLite index for workspace objects and relationships."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from ws_lib import catalog, paths, relations


INDEX = paths.INDEX


SCHEMA = """
CREATE TABLE objects (
    id TEXT PRIMARY KEY,
    ref TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    aliases TEXT NOT NULL,
    path TEXT,
    data TEXT NOT NULL
);
CREATE TABLE relationships (
    id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    object TEXT NOT NULL,
    relation TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE INDEX objects_type ON objects(type);
CREATE INDEX relationships_subject ON relationships(subject);
CREATE INDEX relationships_object ON relationships(object);
CREATE INDEX relationships_relation ON relationships(relation);
"""


def connect() -> sqlite3.Connection:
    return sqlite3.connect(INDEX)


def invalidate() -> None:
    """Remove the derived index after a canonical mutation."""
    if INDEX.exists():
        INDEX.unlink()


def searchable_data(obj: catalog.ObjectRef) -> dict:
    """Domain metadata for discovery, excluding implementation bookkeeping."""
    hidden = {
        "id", "schema_version", "created_at", "updated_at", "redirect_to",
    }
    data = {key: value for key, value in (obj.data or {}).items() if key not in hidden}
    if obj.type == "resource" and obj.path:
        root = obj.path.parent
        data["files"] = [
            str(path.relative_to(root))
            for path in sorted(root.rglob("*"))
            if path.is_file() and path != obj.path and not path.name.startswith(".")
        ]
    return data


def rebuild(quiet: bool = False) -> dict:
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".index.", suffix=".sqlite", dir=INDEX.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    temporary.unlink()
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(SCHEMA)
        objects = catalog.all_objects()
        rows = relations.load_all()
        connection.executemany(
            "INSERT INTO objects(id, ref, type, title, aliases, path, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    obj.id,
                    obj.ref,
                    obj.type,
                    obj.title,
                    json.dumps(obj.aliases, ensure_ascii=False),
                    str(obj.path) if obj.path else None,
                    json.dumps(searchable_data(obj), ensure_ascii=False, sort_keys=True),
                )
                for obj in objects
            ],
        )
        connection.executemany(
            "INSERT INTO relationships(id, subject, object, relation, data) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    str(row.get("id", "")),
                    str(row.get("subject", "")),
                    str(row.get("object", "")),
                    str(row.get("relation", "related")),
                    json.dumps(
                        {key: value for key, value in row.items() if not key.startswith("_")},
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                )
                for row in rows
            ],
        )
        connection.commit()
    finally:
        connection.close()
    try:
        temporary.replace(INDEX)
    finally:
        if temporary.exists():
            temporary.unlink()
    result = {"path": str(INDEX), "objects": len(objects), "relationships": len(rows)}
    if not quiet:
        print(f"rebuilt: {INDEX}")
        print(f"objects: {len(objects)}")
        print(f"relationships: {len(rows)}")
    return result


def stat() -> dict:
    if not INDEX.exists():
        return {"path": str(INDEX), "exists": False, "objects": 0, "relationships": 0, "types": {}}
    connection = connect()
    try:
        object_count = connection.execute("SELECT count(*) FROM objects").fetchone()[0]
        relation_count = connection.execute("SELECT count(*) FROM relationships").fetchone()[0]
        types = dict(connection.execute("SELECT type, count(*) FROM objects GROUP BY type ORDER BY type"))
    finally:
        connection.close()
    return {
        "path": str(INDEX),
        "exists": True,
        "objects": object_count,
        "relationships": relation_count,
        "types": types,
    }


def findings() -> list[dict]:
    if not INDEX.exists():
        return [{"severity": "warning", "message": f"index does not exist; run `ws index rebuild`: {INDEX}"}]
    current_objects = {obj.id for obj in catalog.all_objects()}
    current_relations = {str(row.get("id", "")) for row in relations.load_all()}
    connection = connect()
    try:
        indexed_objects = {row[0] for row in connection.execute("SELECT id FROM objects")}
        indexed_relations = {row[0] for row in connection.execute("SELECT id FROM relationships")}
    except sqlite3.DatabaseError as exc:
        return [{"severity": "error", "message": f"cannot read index: {exc}"}]
    finally:
        connection.close()
    results = []
    if current_objects != indexed_objects:
        results.append({
            "severity": "error",
            "message": f"object index stale: canonical={len(current_objects)} indexed={len(indexed_objects)}",
        })
    if current_relations != indexed_relations:
        results.append({
            "severity": "error",
            "message": f"relationship index stale: canonical={len(current_relations)} indexed={len(indexed_relations)}",
        })
    return results


def ensure() -> None:
    if not INDEX.exists():
        rebuild(quiet=True)


def command_rebuild(args: argparse.Namespace) -> None:
    result = rebuild(quiet=args.json)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


def command_stat(args: argparse.Namespace) -> None:
    result = stat()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return
    print(f"index: {result['path']}")
    print(f"exists: {'yes' if result['exists'] else 'no'}")
    print(f"objects: {result['objects']}")
    print(f"relationships: {result['relationships']}")
    for type_name, count in result["types"].items():
        print(f"  {type_name}: {count}")


def _kind_words() -> dict[str, str]:
    """CLI kind words accepted as a scoping first token of `ws search`."""
    words = {spec["plural"]: kind for kind, spec in catalog.SPECS.items()}
    words["organizations"] = "organisation"
    words["projects"] = "project"
    words["literature"] = "literature"
    return words


TYPED_KINDS = {"document", "organisation", "event", "profile", "project"}


def _classifier_values(kind: str) -> list[str]:
    """Allowed classifier types for a kind, or [] when the vocabulary is open
    or unreadable."""
    try:
        if kind == "document":
            from ws_lib import document_taxonomy

            return list(document_taxonomy.type_ids())
        if kind == "profile":
            from ws_lib import profile_taxonomy

            return list(profile_taxonomy.type_ids())
        if kind == "project":
            from ws_lib import project

            return list(project.load_taxonomy()["type"])
    except Exception:
        return []
    return []


def _object_type(kind: str, data: dict) -> str:
    if kind == "document":
        return catalog.document_type(data)
    return str(data.get("type", "") or "")


def command_search(args: argparse.Namespace) -> None:
    query_words = list(args.query) if isinstance(args.query, list) else [args.query]
    kind = ""
    if query_words and query_words[0] in _kind_words():
        scope = query_words.pop(0)
        if not query_words:
            # Enumeration is list's job, so hand the user the command that
            # does what they asked -- carrying the filters they already typed.
            hint = f"ws list {scope}"
            for flag, value in (
                ("--type", getattr(args, "type", "")),
                ("--limit", getattr(args, "limit", None) if getattr(args, "limit", 50) != 50 else None),
            ):
                if value:
                    hint += f" {flag} {value}"
            if getattr(args, "json", False):
                hint += " --json"
            catalog.fail(
                f"searching within {scope} needs query words; "
                f"to enumerate them use `{hint}`"
            )
        kind = _kind_words()[scope]
        args.query = query_words
    # `--type` is the kind's own classifier here, exactly as on `ws list`.
    # The kind itself is named by the first word and has no second spelling.
    wanted_type = (getattr(args, "type", "") or "").strip()
    if wanted_type:
        if not kind:
            catalog.fail(
                "--type filters a kind's own classifier, so name the kind first: "
                f"`ws search <kind> <words> --type {wanted_type}`"
            )
        if kind not in TYPED_KINDS:
            catalog.fail(f"{kind} has no type classifier; drop --type")
        allowed = _classifier_values(kind)
        if allowed and wanted_type not in allowed:
            catalog.fail(
                f"unknown {kind} type '{wanted_type}'; allowed: {', '.join(allowed)}"
            )
    # Canonical mutations invalidate this derived cache. Reuse it between
    # searches; rebuilding every query makes broad workspaces needlessly slow.
    ensure()
    connection = connect()
    try:
        raw_query = " ".join(args.query) if isinstance(args.query, list) else args.query
        normalized_query = " ".join(raw_query.casefold().split())
        query = f"%{normalized_query}%"
        sql = (
            "SELECT ref, type, title, aliases, data FROM objects "
            "WHERE (lower(title) LIKE ? OR lower(aliases) LIKE ? OR lower(data) LIKE ?)"
        )
        parameters: list = [query, query, query]
        if kind:
            sql += " AND type = ?"
            parameters.append(kind)
        candidates = list(connection.execute(sql, parameters))
        if wanted_type:
            candidates = [
                row for row in candidates
                if _object_type(kind, json.loads(row[4] or "{}")) == wanted_type
            ]

        def rank(row) -> tuple:
            ref, _kind, title, aliases_json, data_json = row
            aliases = json.loads(aliases_json or "[]")
            data = json.loads(data_json or "{}")
            key = str(data.get("key", "") or ref.partition(":")[2])
            primary = [str(title), key, *[str(alias) for alias in aliases]]
            normalized = [" ".join(value.casefold().split()) for value in primary]
            if normalized_query in normalized:
                score = 0
            elif any(value.startswith(normalized_query) for value in normalized):
                score = 1
            elif any(normalized_query in value for value in normalized):
                score = 2
            else:
                score = 3
            return score, str(title).casefold(), str(ref).casefold()

        candidates.sort(key=rank)
        rows = [
            {"ref": row[0], "kind": row[1], "name": row[2]}
            for row in candidates[: args.limit]
        ]
    finally:
        connection.close()
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(f"{row['ref']}  —  {row['name']}")
        if not rows:
            print("none")


def add_parsers(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("index")
    actions = parser.add_subparsers(dest="index_command", required=True)
    rebuild_parser = actions.add_parser("rebuild", help="rebuild the derived search index now")
    rebuild_parser.add_argument("--json", action="store_true")
    rebuild_parser.set_defaults(func=command_rebuild)
    stat_parser = actions.add_parser("stat", help="report the index's size, age, and row counts")
    stat_parser.add_argument("--json", action="store_true")
    stat_parser.set_defaults(func=command_stat)

    search = sub.add_parser(
        "search",
        help="search everything; a first word naming a kind scopes",
        description="Search the whole workspace; a first word naming a kind scopes.",
    )
    search.add_argument(
        "query",
        nargs="+",
        help="query words; a first word naming a kind (documents, people, ...) "
        "scopes the search to that kind. Quotes are optional.",
    )
    search.add_argument(
        "--type",
        metavar="TYPE",
        help="only this classifier type, as on `ws list`; name the kind first "
        "(`ws search documents slides --type presentation`)",
    )
    search.add_argument("--limit", type=int, default=50, help="show at most this many hits (default 50)")
    search.add_argument("--json", action="store_true", help="print hits as JSON")
    search.set_defaults(func=command_search)
