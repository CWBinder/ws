"""Rebuildable SQLite index for workspace objects and relationships."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import textwrap
from pathlib import Path

from ws_lib import catalog, paths, registry, relations


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
        return [{"severity": "warning", "message": f"index does not exist; run `ws rebuild index`: {INDEX}"}]
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


# Words that carry no meaning for matching, so natural phrasing such as
# `ws search resources for delft` finds what `ws search resources delft` does.
FILLER_WORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "for", "about", "on", "in", "at",
    "to", "from", "with", "by", "my", "is", "are", "where", "what", "which",
})


def _query_terms(phrase: str) -> list[str]:
    """The words every hit must contain: the query without filler, unless
    filler is all it has."""
    words = list(dict.fromkeys(phrase.split()))
    return [word for word in words if word not in FILLER_WORDS] or words


def _values(value) -> list[str]:
    """Every scalar in a record, without its field names: a field called
    `description` is not a discovery term, its text is."""
    if isinstance(value, dict):
        return [text for item in value.values() for text in _values(item)]
    if isinstance(value, list):
        return [text for item in value for text in _values(item)]
    return [] if value is None else [str(value)]


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
    # argparse hands the first of several words to KIND whether or not it
    # names a kind, so the words are rejoined and the kind recognised here.
    if getattr(args, "scope", None):
        query_words.insert(0, args.scope)
    kind = ""
    # Filler in front ("for resources delft") does not hide a kind word. The
    # word is compared as typed, so quoting it together with the next word
    # keeps it a query word: `ws search "event horizon"`.
    lead = 0
    while lead < len(query_words) - 1 and query_words[lead].casefold() in FILLER_WORDS:
        lead += 1
    if query_words and query_words[lead] in registry.KIND_OF_WORD:
        kind = registry.KIND_OF_WORD[query_words[lead]]
        query_words = query_words[lead + 1:]
        if not query_words:
            # Enumeration is list's job, so hand the user the command that
            # does what they asked -- carrying the filters they already typed.
            hint = f"ws list {registry.KIND_PLURALS[kind]}"
            for flag, value in (
                ("--type", getattr(args, "type", "")),
                ("--limit", getattr(args, "limit", None) if getattr(args, "limit", 50) != 50 else None),
            ):
                if value:
                    hint += f" {flag} {value}"
            if getattr(args, "json", False):
                hint += " --json"
            catalog.fail(
                f"searching within {registry.KIND_PLURALS[kind]} needs query words; "
                f"to enumerate them use `{hint}`"
            )
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
    phrase = " ".join(" ".join(query_words).casefold().split())
    words = _query_terms(phrase)
    # The whole query, or its content words alone, may name a hit outright:
    # "journal of physics", "the maria schwarz".
    phrases = {phrase, " ".join(words)}
    # Canonical mutations invalidate this derived cache. Reuse it between
    # searches; rebuilding every query makes broad workspaces needlessly slow.
    ensure()
    connection = connect()
    try:
        sql = "SELECT ref, type, title, aliases, data FROM objects"
        parameters: list = []
        if kind:
            sql += " WHERE type = ?"
            parameters.append(kind)
        candidates = list(connection.execute(sql, parameters))
    finally:
        connection.close()

    # Words are matched here rather than in SQL: each must appear, in any
    # order, and casefold() also folds non-ASCII letters, which SQLite's
    # lower() leaves alone.
    full: list[tuple] = []
    partial: list[tuple] = []
    matched: set[str] = set()
    for ref, row_kind, title, aliases_json, data_json in candidates:
        data = json.loads(data_json or "{}")
        if wanted_type and _object_type(kind, data) != wanted_type:
            continue
        key = str(data.get("key", "") or ref.partition(":")[2])
        names = [
            " ".join(str(value).casefold().split())
            for value in (title, key, *json.loads(aliases_json or "[]"))
        ]
        metadata = "\n".join(value.casefold() for value in _values(data))
        in_names = [word for word in words if any(word in name for name in names)]
        found = [word for word in words if word in in_names or word in metadata]
        if not found:
            continue
        matched.update(found)
        row = {"ref": ref, "kind": row_kind, "name": title}
        order = (str(title).casefold(), ref.casefold())
        if len(found) < len(words):
            partial.append(((-len(found), -len(in_names), *order), row))
        elif phrases & set(names):
            full.append(((0, *order), row))
        elif any(name.startswith(text) for name in names for text in phrases):
            full.append(((1, *order), row))
        elif any(text in name for name in names for text in phrases):
            full.append(((2, *order), row))
        else:
            # Every word is there: all in the names, or some only in metadata.
            full.append(((3 if len(in_names) == len(words) else 4, *order), row))

    rows = [row for _, row in sorted(full or partial, key=lambda hit: hit[0])[: args.limit]]
    note = ""
    if partial and not full:
        note = "no hit has every word"
        missing = [f'"{word}"' for word in words if word not in matched]
        if missing:
            note += f" ({', '.join(missing)} {'matches' if len(missing) == 1 else 'match'} nothing)"
    if args.json:
        # Programs get only hits that have every word; the hint goes to stderr.
        if note:
            print(note, file=sys.stderr)
        print(json.dumps(rows if full else [], ensure_ascii=False, indent=2, sort_keys=True))
    else:
        if note:
            print(f"{note}; partial matches:")
        for row in rows:
            print(f"{row['ref']}  —  {row['name']}")
        if not rows:
            print("none")


def add_parsers(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("index")
    actions = parser.add_subparsers(dest="index_command", required=True)
    stat_parser = actions.add_parser("stat", help="report the index's size, age, and row counts")
    stat_parser.add_argument("--json", action="store_true")
    stat_parser.set_defaults(func=command_stat)

    kinds = textwrap.fill(
        ", ".join(sorted(set(registry.KIND_PLURALS.values()))),
        width=76, initial_indent="  ", subsequent_indent="  ",
    )
    search = sub.add_parser(
        "search",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="search every kind of object, or only the kind named first",
        description="Search every kind of object, or only one kind: name it first.",
        epilog=f"""Kinds, singular or plural:
{kinds}

Examples:
  ws search march report                  every kind; words in any order
  ws search documents march report        documents only
  ws search people for maria              'for' is ignored
  ws search documents slides --type presentation
  ws search "event horizon"               quoted: 'event' is a word, not a kind
""",
    )
    search.add_argument(
        "scope",
        nargs="?",
        metavar="KIND",
        help="optional; search only this kind (listed below)",
    )
    search.add_argument(
        "query",
        nargs="+",
        metavar="WORDS",
        help="words to find; every word must match, in any order, and filler "
        "such as 'for' or 'the' is ignored",
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
