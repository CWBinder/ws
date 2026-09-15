"""Canonical cross-domain relationship records."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import shlex
import sys
from pathlib import Path

from ws_lib import catalog, paths, records


RELATIONS = paths.RELATIONS


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def relation_path(relation_id: str) -> Path:
    return RELATIONS / f"{relation_id}.yaml"


def load_all() -> list[dict]:
    if not RELATIONS.exists():
        return []
    rows = []
    for path in sorted(RELATIONS.glob("*.yaml")):
        row = records.load_record(path)
        if row:
            row["_path"] = str(path)
            rows.append(row)
    return rows


def get(relation_id: str) -> dict | None:
    path = relation_path(relation_id)
    if not path.exists():
        return None
    row = records.load_record(path)
    if row:
        row["_path"] = str(path)
    return row or None


def object_lookup() -> dict:
    """One id -> object map from a single catalog scan. Pass it to
    public_relation when rendering many rows: catalog.get is a full catalog
    scan per call, which turns a row loop quadratic."""
    return {obj.id: obj for obj in catalog.all_objects()}


def public_relation(row: dict, lookup: dict | None = None) -> dict:
    public = {key: value for key, value in row.items() if not key.startswith("_")}
    if lookup is None:
        subject = catalog.get(str(row.get("subject", "")))
        object_ref = catalog.get(str(row.get("object", "")))
    else:
        subject = lookup.get(str(row.get("subject", "")))
        object_ref = lookup.get(str(row.get("object", "")))
    public["subject"] = subject.ref if subject else ""
    public["object"] = object_ref.ref if object_ref else ""
    public["subject_name"] = subject.title if subject else ""
    public["object_name"] = object_ref.title if object_ref else ""
    return public


def _indexed_rows(object_id: str) -> list[dict] | None:
    """Serve adjacency from the derived index when it exists. Mutations delete
    the index, so it is either fresh or absent -- never stale. Reads never
    trigger a rebuild; absent means the caller falls back to the YAML scan."""
    from ws_lib import indexing

    if not indexing.INDEX.exists():
        return None
    try:
        connection = indexing.connect()
        try:
            found = connection.execute(
                "SELECT data FROM relationships WHERE subject = ? OR object = ? ORDER BY id",
                (object_id, object_id),
            ).fetchall()
        finally:
            connection.close()
        return [json.loads(data) for (data,) in found]
    except Exception:
        return None


def for_object(object_id: str) -> list[dict]:
    rows = _indexed_rows(object_id)
    if rows is not None:
        return rows
    return [
        row for row in load_all()
        if row.get("subject") == object_id or row.get("object") == object_id
    ]


def create(
    subject_value: str,
    object_value: str,
    relation: str = "",
    valid_from: str = "",
    valid_until: str = "",
    source: str = "",
    observed_at: str = "",
) -> tuple[dict, bool]:
    # Internal callers already hold immutable storage IDs; CLI callers supply
    # canonical public REFs. Names and aliases are deliberately not resolved.
    subject = catalog.get(subject_value) or catalog.resolve(subject_value)
    object_ref = catalog.get(object_value) or catalog.resolve(object_value)
    if subject.id == object_ref.id:
        fail("cannot relate an object to itself")
    relation = relation.strip().lower().replace(" ", "-") or "related"
    for field, value in (
        ("from", valid_from), ("until", valid_until), ("observed-at", observed_at),
    ):
        if value and _date_error(value):
            fail(f"--{field} must be an ISO date or datetime")
    if valid_from and valid_until and valid_from[:10] > valid_until[:10]:
        fail("--from must not be after --until")
    identity = (subject.id, object_ref.id, relation, valid_from, valid_until)
    with records.write_lock(RELATIONS):
        for row in load_all():
            current = (
                str(row.get("subject", "")),
                str(row.get("object", "")),
                str(row.get("relation", "")),
                str(row.get("valid_from", "")),
                str(row.get("valid_until", "")),
            )
            if current == identity:
                return row, False
        timestamp = records.now()
        row = {
            "schema_version": 1,
            "id": records.new_id("rel"),
            "subject": subject.id,
            "object": object_ref.id,
            "relation": relation,
            "valid_from": valid_from,
            "valid_until": valid_until,
            "source": source,
            "observed_at": observed_at,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        records.atomic_write(relation_path(row["id"]), row)
    from ws_lib import indexing
    indexing.invalidate()
    return row, True


def edit(relation_id: str, changes: dict, source: str = "", observed_at: str = "") -> dict:
    row = get(relation_id)
    if not row:
        fail(f"relationship does not exist: {relation_id}")
    path = Path(row.pop("_path"))
    candidate = {**row, **{key: value for key, value in changes.items() if value is not None}}
    for field in ("valid_from", "valid_until"):
        value = str(candidate.get(field, ""))
        if value and _date_error(value):
            fail(f"{field} must be an ISO date or datetime")
    if observed_at and _date_error(observed_at):
        fail("observed_at must be an ISO date or datetime")
    if (
        candidate.get("valid_from") and candidate.get("valid_until")
        and str(candidate["valid_from"])[:10] > str(candidate["valid_until"])[:10]
    ):
        fail("valid_from must not be after valid_until")
    changed_fields = []
    for key, value in changes.items():
        if value is not None and row.get(key) != value:
            row[key] = value
            changed_fields.append(key)
    if changed_fields:
        row["updated_at"] = records.now()
        history = row.get("provenance", [])
        if not isinstance(history, list):
            history = []
        if source or observed_at:
            history.append(records.provenance(source, observed_at, changed_fields))
            row["provenance"] = history
        records.atomic_write(path, row)
        from ws_lib import indexing
        indexing.invalidate()
    return row


def remove(row: dict) -> None:
    """Delete a relation record. Relations are stateless assertions: they
    exist or they do not, so unrelate deletes rather than retires. The
    caller prints a restore hint because the store is not under git."""
    path = Path(row.get("_path") or relation_path(str(row["id"])))
    with records.write_lock(RELATIONS):
        if path.exists():
            path.unlink()
    from ws_lib import indexing
    indexing.invalidate()


def restore_hint(row: dict) -> str:
    public = public_relation(row)
    parts = [
        "ws relate",
        shlex.quote(str(public.get("subject", ""))),
        shlex.quote(str(public.get("object", ""))),
        "--as",
        shlex.quote(str(row.get("relation") or "related")),
    ]
    for flag, key in (
        ("--from", "valid_from"),
        ("--until", "valid_until"),
        ("--source", "source"),
        ("--observed-at", "observed_at"),
    ):
        value = str(row.get(key, "") or "")
        if value:
            parts.extend([flag, shlex.quote(value)])
    return " ".join(parts)


def redirect_object(old_id: str, new_id: str) -> None:
    for row in load_all():
        changes = {}
        if row.get("subject") == old_id:
            changes["subject"] = new_id
        if row.get("object") == old_id:
            changes["object"] = new_id
        if changes:
            candidate = {**row, **changes}
            identity = (
                str(candidate.get("subject", "")),
                str(candidate.get("object", "")),
                str(candidate.get("relation", "")),
                str(candidate.get("valid_from", "")),
                str(candidate.get("valid_until", "")),
            )
            duplicate = next(
                (
                    other for other in load_all()
                    if str(other.get("id", "")) != str(row.get("id", ""))
                    and (
                        str(other.get("subject", "")),
                        str(other.get("object", "")),
                        str(other.get("relation", "")),
                        str(other.get("valid_from", "")),
                        str(other.get("valid_until", "")),
                    ) == identity
                ),
                None,
            )
            if duplicate:
                remove(row)
            else:
                edit(str(row["id"]), changes, source=f"merge {old_id} into {new_id}")


def _date_error(value: str) -> bool:
    if not value:
        return False
    try:
        dt.date.fromisoformat(value[:10])
        return False
    except ValueError:
        return True


def findings() -> list[dict]:
    results: list[dict] = []
    legacy = paths.LEGACY_RELATIONS
    if legacy != RELATIONS and legacy.exists() and any(legacy.glob("*.yaml")):
        results.append({
            "severity": "warning",
            "message": (
                f"legacy relationship records remain in {legacy}; "
                f"move them into {RELATIONS} by hand"
            ),
        })
    objects = {obj.id for obj in catalog.all_objects()}
    seen: dict[tuple, str] = {}
    for row in load_all():
        relation_id = str(row.get("id", ""))
        for endpoint in ("subject", "object"):
            value = str(row.get(endpoint, ""))
            if value not in objects:
                results.append({
                    "severity": "error",
                    "id": relation_id,
                    "message": f"{endpoint} does not resolve: {value}",
                })
        if row.get("subject") == row.get("object"):
            results.append({"severity": "error", "id": relation_id, "message": "self relationship"})
        for field in ("valid_from", "valid_until", "observed_at"):
            value = str(row.get(field, ""))
            if _date_error(value):
                results.append({
                    "severity": "error", "id": relation_id, "message": f"invalid {field}: {value}",
                })
        start = str(row.get("valid_from", ""))
        end = str(row.get("valid_until", ""))
        if start and end and not _date_error(start) and not _date_error(end) and start[:10] > end[:10]:
            results.append({"severity": "error", "id": relation_id, "message": "valid_from is after valid_until"})
        identity = (
            row.get("subject"), row.get("object"), row.get("relation"),
            row.get("valid_from"), row.get("valid_until"),
        )
        if identity in seen:
            results.append({
                "severity": "error",
                "id": relation_id,
                "message": f"duplicates {seen[identity]}",
            })
        else:
            seen[identity] = relation_id
        if row.get("relation") == "related":
            results.append({
                "severity": "warning",
                "id": relation_id,
                "message": "generic relationship can be refined with --as",
            })
    return results


def migrate_legacy() -> tuple[int, int]:
    legacy = paths.LEGACY_RELATIONS
    if legacy.resolve() == RELATIONS.resolve():
        RELATIONS.mkdir(parents=True, exist_ok=True)
        return 0, 0
    sources = sorted(legacy.glob("*.yaml")) if legacy.exists() else []
    RELATIONS.mkdir(parents=True, exist_ok=True)
    conflicts = [
        source
        for source in sources
        if (RELATIONS / source.name).exists()
        and (RELATIONS / source.name).read_bytes() != source.read_bytes()
    ]
    if conflicts:
        fail(
            "migration conflict; destination already contains different record(s): "
            + ", ".join(path.name for path in conflicts)
        )
    moved = 0
    identical = 0
    for source in sources:
        destination = RELATIONS / source.name
        if destination.exists():
            source.unlink()
            identical += 1
        else:
            source.replace(destination)
            moved += 1
    lock = legacy / ".write.lock"
    if lock.exists() and not any(legacy.glob("*.yaml")):
        lock.unlink()
    if legacy.exists() and not any(legacy.iterdir()):
        legacy.rmdir()
    return moved, identical


def _rebuild_document_views_if_touched(row: dict) -> None:
    """Document by-* trees are the only edge-fed views; rebuilding them costs
    seconds, so skip it for edges that touch no document."""
    if any(str(row.get(end, "")).startswith("doc_") for end in ("subject", "object")):
        from ws_lib import anatomy

        anatomy.rebuild_documents()


def _resolves(value: str):
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            return catalog.resolve(value)
    except SystemExit:
        return None


def _natural_endpoints(tokens: list[str], relation: str) -> tuple[str, str, str]:
    """Parse two whitespace-free canonical REFs and an optional relation."""
    tokens = list(tokens)
    if "as" in tokens:
        idx = tokens.index("as")
        phrase = " ".join(tokens[idx + 1:])
        if not phrase:
            fail("nothing follows 'as'")
        if not relation:
            relation = phrase
        tokens = tokens[:idx]
    if "to" in tokens:
        idx = tokens.index("to")
        subject = " ".join(tokens[:idx])
        object_value = " ".join(tokens[idx + 1:])
        if not subject or not object_value:
            fail("expected SUBJECT to OBJECT")
        return subject, object_value, relation
    if len(tokens) < 2:
        fail("relate expects SUBJECT_REF and OBJECT_REF")
    if len(tokens) == 2:
        return tokens[0], tokens[1], relation
    fail("expected exactly SUBJECT_REF and OBJECT_REF; use `as` or --as for the relation")


def command_relate(args: argparse.Namespace) -> None:
    subject_value, object_value, relation = _natural_endpoints(
        args.references, args.relation or ""
    )
    row, created = create(
        subject_value,
        object_value,
        relation,
        args.valid_from or "",
        args.valid_until or "",
        args.source or "",
        args.observed_at or "",
    )
    output = public_relation(row)
    output["created"] = created
    _rebuild_document_views_if_touched(row)
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        action = "created" if created else "exists"
        print(f"{action}: {row['id']}")
        print(f"{output['subject']} --{row['relation']}--> {output['object']}")


def command_unrelate(args: argparse.Namespace) -> None:
    values = args.references
    if "as" in values or "to" in values:
        subject_value, object_value, phrase = _natural_endpoints(values, args.relation or "")
        values = [subject_value, object_value]
        args.relation = phrase.strip().lower().replace(" ", "-") if phrase else args.relation
    if len(values) == 1:
        row = get(values[0])
        if not row:
            fail(f"relationship does not exist: {values[0]}")
        matches = [row]
    elif len(values) == 2:
        subject = catalog.resolve(values[0])
        object_ref = catalog.resolve(values[1])
        matches = [
            row for row in load_all()
            if row.get("subject") == subject.id
            and row.get("object") == object_ref.id
            and (not args.relation or row.get("relation") == args.relation)
        ]
    else:
        fail("unrelate expects RELATION_ID or SUBJECT OBJECT")
    if len(matches) != 1:
        if not matches:
            fail("no relationship matches")
        fail("relationship is ambiguous: " + ", ".join(str(row.get("id")) for row in matches))
    row = matches[0]
    if args.dry_run:
        print(f"would delete: {row['id']}")
        return
    remove(row)
    _rebuild_document_views_if_touched(row)
    print(f"deleted: {row['id']}")
    print(f"restore with: {restore_hint(row)}")


def command_relations_show(args: argparse.Namespace) -> None:
    direct = get(args.reference)
    if direct:
        rows = [direct]
    else:
        ref = catalog.resolve(args.reference)
        rows = for_object(ref.id)
    if args.relation:
        rows = [row for row in rows if row.get("relation") == args.relation]
    lookup = object_lookup()
    public = [public_relation(row, lookup) for row in rows]
    if args.json:
        print(json.dumps(public[0] if direct and public else public, ensure_ascii=False, indent=2, sort_keys=True))
        return
    if not public:
        print("none")
        return
    for row in public:
        subject = row["subject"]
        object_ref = row["object"]
        subject_label = f"{subject} ({row['subject_name']})" if row.get("subject_name") else subject
        object_label = f"{object_ref} ({row['object_name']})" if row.get("object_name") else object_ref
        print(
            f"{row['id']}\t{subject_label} --{row['relation']}--> {object_label}"
        )


def command_relations_edit(args: argparse.Namespace) -> None:
    changes = {
        "relation": args.relation,
        "valid_from": args.valid_from,
        "valid_until": args.valid_until,
    }
    row = edit(args.relation_id, changes, args.source or "", args.observed_at or "")
    _rebuild_document_views_if_touched(row)
    if args.json:
        print(json.dumps(public_relation(row), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"updated: {row['id']}")


def command_relations_vocabulary(_args: argparse.Namespace) -> None:
    """Bare `ws relations`: which relation words this workspace actually uses.

    The vocabulary is open -- `ws relate` accepts any words -- so the only
    truthful listing is the one read back from the edges themselves."""
    counts: dict[str, int] = {}
    for row in load_all():
        word = str(row.get("relation", "") or "related")
        counts[word] = counts.get(word, 0) + 1
    if not counts:
        print("none")
        return
    width = max(14, max(len(word) for word in counts) + 1)
    for word in sorted(counts):
        edges = counts[word]
        print(f"{word:<{width}} {edges} edge{'s' if edges != 1 else ''}")


def add_parsers(sub: argparse._SubParsersAction) -> None:
    relate = sub.add_parser(
        "relate",
        help="assert one edge between two objects",
        description="Assert one edge: `ws relate A to B as works-at`. The filler "
        "words `to` and `as` are optional. Duplicate edges are no-ops.",
    )
    relate.add_argument(
        "references",
        nargs="+",
        metavar="REF",
        help="SUBJECT_REF [to] OBJECT_REF [as RELATION WORDS]",
    )
    relate.add_argument("--as", dest="relation", default="")
    relate.add_argument("--from", dest="valid_from")
    relate.add_argument("--until", dest="valid_until")
    relate.add_argument("--source")
    relate.add_argument("--observed-at")
    relate.add_argument("--json", action="store_true")
    relate.set_defaults(func=command_relate)

    unrelate = sub.add_parser(
        "unrelate",
        help="remove an edge, by relation id or by sentence",
        description="Remove an edge, named either by its relation id or by the "
        "same sentence that created it.",
    )
    unrelate.add_argument(
        "references", nargs="+", metavar="REF",
        help="RELATION_ID, or SUBJECT_REF [to] OBJECT_REF [as RELATION WORDS]",
    )
    unrelate.add_argument("--as", dest="relation")
    unrelate.add_argument("--dry-run", action="store_true")
    unrelate.set_defaults(func=command_unrelate)

    parser = sub.add_parser(
        "relations",
        help="the graph layer: bare, it lists the relation words in use",
        description="The graph of edges between objects. Bare, it lists the "
        "relation vocabulary actually in use, with how many edges carry each "
        "word. Edges are written only by `ws relate`/`ws unrelate` and read "
        "with `ws show relations of REF`.",
    )
    parser.set_defaults(func=command_relations_vocabulary)
    actions = parser.add_subparsers(dest="relations_command", metavar="COMMAND")
    # Reading edges is `ws show relations of REF`; this service keeps only
    # the edge maintenance tools.
    edit_parser = actions.add_parser("edit", help="change one existing edge's relation words or validity")
    edit_parser.add_argument("relation_id")
    edit_parser.add_argument("--as", dest="relation")
    edit_parser.add_argument("--from", dest="valid_from")
    edit_parser.add_argument("--until", dest="valid_until")
    edit_parser.add_argument("--source")
    edit_parser.add_argument("--observed-at")
    edit_parser.add_argument("--json", action="store_true")
    edit_parser.set_defaults(func=command_relations_edit)
