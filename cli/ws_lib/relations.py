"""Canonical cross-domain relationship records."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import io
import json
import re
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


# An edge is addressed like an object: `relation:<key>`, where the key is its
# id without the storage prefix (contracts/relations.md, Addressing an edge).
REF_KIND = "relation"


def ref_of(row: dict) -> str:
    return f"{REF_KIND}:{str(row.get('id', '')).removeprefix('rel_')}"


def find(value: str) -> dict | None:
    """The edge a REF names. The bare storage id (`rel_...`) that the older
    spellings printed still resolves; anything else names no edge."""
    key = value.removeprefix(f"{REF_KIND}:")
    if not re.fullmatch(r"[0-9A-Za-z_]+", key):
        return None
    return get(key if key.startswith("rel_") else f"rel_{key}")


def require(value: str) -> dict:
    row = find(value)
    if not row:
        fail(f"no relation {value}; `ws show REF` lists an object's relations with their REFs")
    return row


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


def _endpoints(ids: set[str]) -> dict[str, tuple[str, str]]:
    """REF and name for each object id: from the derived index when it exists
    (fresh or absent, never stale), otherwise from one catalog scan."""
    from ws_lib import indexing

    if not ids:
        # Nothing to name; without this the fallback scans the whole catalog.
        return {}
    if indexing.INDEX.exists():
        try:
            connection = indexing.connect()
            try:
                found = connection.execute(
                    f"SELECT id, ref, title FROM objects WHERE id IN ({','.join('?' * len(ids))})",
                    sorted(ids),
                ).fetchall()
            finally:
                connection.close()
            return {object_id: (ref, title) for object_id, ref, title in found}
        except Exception:
            pass
    return {
        object_id: (obj.ref, obj.title)
        for object_id, obj in object_lookup().items()
        if object_id in ids
    }


def edges_of(object_id: str, relation: str = "") -> list[dict]:
    """One object's edges as `ws show REF` lists them: each edge's REF and
    words, the direction seen from this object, and the other endpoint."""
    rows = [
        row for row in for_object(object_id)
        if not relation or row.get("relation") == relation
    ]
    others = {
        str(row.get("object") if row.get("subject") == object_id else row.get("subject"))
        for row in rows
    }
    names = _endpoints(others)
    edges = []
    for row in rows:
        outgoing = row.get("subject") == object_id
        other = str(row.get("object") if outgoing else row.get("subject"))
        other_ref, other_name = names.get(other, (other, ""))
        edges.append({
            "ref": ref_of(row),
            "relation": str(row.get("relation") or "related"),
            "direction": "out" if outgoing else "in",
            "other": other_ref,
            "other_name": other_name,
            "valid_from": str(row.get("valid_from") or ""),
            "valid_until": str(row.get("valid_until") or ""),
        })
    edges.sort(key=lambda edge: (
        edge["direction"] != "out", edge["relation"], edge["other_name"].casefold(), edge["other"],
    ))
    return edges


def _window(row: dict) -> str:
    start, end = str(row.get("valid_from") or ""), str(row.get("valid_until") or "")
    if start and end:
        return f"  [{start} to {end}]"
    if start or end:
        return f"  [from {start}]" if start else f"  [until {end}]"
    return ""


def edge_lines(edges: list[dict]) -> list[str]:
    """The relations block under a shown record: `-->` leaves the object,
    `<--` arrives at it, and each line starts with the edge's own REF."""
    if not edges:
        return ["relations: none"]
    width = max(len(edge["ref"]) for edge in edges)
    lines = [f"relations: {len(edges)}"]
    for edge in edges:
        words = edge["relation"]
        arrow = f"--{words}-->" if edge["direction"] == "out" else f"<--{words}--"
        other = f"{edge['other']} ({edge['other_name']})" if edge["other_name"] else edge["other"]
        lines.append(f"  {edge['ref']:<{width}}  {arrow} {other}{_window(edge)}")
    return lines


def show_record(row: dict) -> dict:
    """One edge in full, as `ws show relation:<key>` prints it."""
    public = {key: value for key, value in row.items() if not key.startswith("_")}
    subject, object_value = str(row.get("subject", "")), str(row.get("object", ""))
    names = _endpoints({subject, object_value})
    public["ref"] = ref_of(row)
    public["subject"], public["subject_name"] = names.get(subject, (subject, ""))
    public["object"], public["object_name"] = names.get(object_value, (object_value, ""))
    return public


def show_lines(record: dict) -> list[str]:
    def label(side: str) -> str:
        name = record.get(f"{side}_name")
        return f"{record[side]} ({name})" if name else str(record[side])

    lines = [
        f"ref: {record['ref']}",
        f"subject: {label('subject')}",
        f"relation: {record.get('relation') or 'related'}",
        f"object: {label('object')}",
    ]
    for key in ("valid_from", "valid_until", "source", "observed_at", "created_at", "updated_at"):
        if record.get(key):
            lines.append(f"{key}: {record[key]}")
    lines.extend(f"provenance: {entry}" for entry in record.get("provenance") or [])
    return lines


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
    output["ref"] = ref_of(row)
    output["created"] = created
    _rebuild_document_views_if_touched(row)
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        action = "created" if created else "exists"
        print(f"{action}: {output['ref']}")
        print(f"{output['subject']} --{row['relation']}--> {output['object']}")


def _older_spelling(newer: str) -> None:
    """The older edge spellings still run; stderr names what replaced them."""
    print(f"note: the current spelling is `{newer}`", file=sys.stderr)


def _delete_row(row: dict, dry_run: bool) -> None:
    record = show_record(row)
    edge = f"{record['ref']} ({record['subject']} --{record.get('relation') or 'related'}--> {record['object']})"
    if dry_run:
        print(f"would delete: {edge}")
        return
    remove(row)
    _rebuild_document_views_if_touched(row)
    print(f"deleted: {edge}")
    # The store is not under git, so the undo path is the command itself.
    print(f"restore with: {restore_hint(row)}")


def delete_refs(values: list[str], dry_run: bool = False) -> None:
    """`ws delete relation:<id> ...`. Every REF must resolve before any edge
    goes, so a typo in the second cannot leave the first half-done."""
    for row in [require(value) for value in values]:
        _delete_row(row, dry_run)


def edit_arguments(parser: argparse.ArgumentParser) -> None:
    """The flags that change an edge, shared by `ws edit relation:<id>` and
    the older `ws relations edit`; their help is the registry's shared text."""
    parser.add_argument("--as", dest="relation")
    parser.add_argument("--from", dest="valid_from")
    parser.add_argument("--until", dest="valid_until")
    parser.add_argument("--source")
    parser.add_argument("--observed-at")
    parser.add_argument("--json", action="store_true")


def edit_ref(value: str, args: argparse.Namespace) -> dict:
    """`ws edit relation:<id> --as WORDS --from DATE --until DATE`."""
    row = require(value)
    words = args.relation.strip().lower().replace(" ", "-") if args.relation else None
    changes = {"relation": words, "valid_from": args.valid_from, "valid_until": args.valid_until}
    row = edit(str(row["id"]), changes, args.source or "", args.observed_at or "")
    _rebuild_document_views_if_touched(row)
    if args.json:
        print(json.dumps(show_record(row), ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"updated: {ref_of(row)}")
    return row


def command_unrelate(args: argparse.Namespace) -> None:
    """The older spelling of `ws delete relation:<id>`; it also still takes
    the sentence that created the edge."""
    values = args.references
    if "as" in values or "to" in values:
        subject_value, object_value, phrase = _natural_endpoints(values, args.relation or "")
        values = [subject_value, object_value]
        args.relation = phrase.strip().lower().replace(" ", "-") if phrase else args.relation
    if len(values) == 1:
        matches = [require(values[0])]
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
        fail("unrelate expects a relation REF, or SUBJECT to OBJECT")
    if len(matches) != 1:
        if not matches:
            fail("no relationship matches")
        fail("relationship is ambiguous: " + ", ".join(ref_of(row) for row in matches))
    _delete_row(matches[0], args.dry_run)
    _older_spelling(f"ws delete {ref_of(matches[0])}")


def command_relations_show(args: argparse.Namespace) -> None:
    """The older `ws show relations of REF`: `ws show REF` lists the same
    edges under the record, and `ws show relation:<id>` shows one."""
    direct = find(args.reference)
    if direct:
        record = show_record(direct)
        if args.json:
            print(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("\n".join(show_lines(record)))
        _older_spelling(f"ws show {record['ref']}")
        return
    ref = catalog.resolve(args.reference)
    edges = edges_of(ref.id, args.relation or "")
    if args.json:
        print(json.dumps(edges, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("\n".join(edge_lines(edges)))
    _older_spelling(f"ws show {ref.ref}" + (f" --as {args.relation}" if args.relation else ""))


def command_relations_edit(args: argparse.Namespace) -> None:
    """The older spelling of `ws edit relation:<id>`."""
    row = edit_ref(args.relation_id, args)
    _older_spelling(f"ws edit {ref_of(row)}")


def command_relations_vocabulary(_args: argparse.Namespace) -> None:
    """Bare `ws relations`: which relation words this workspace actually uses,
    how often, and between which kinds, subject first.

    The vocabulary is open -- `ws relate` accepts any words -- so the only
    truthful listing is the one read back from the edges themselves. The
    kinds show which way round a word is used, which the count alone hides."""
    pairs: dict[str, dict[str, int]] = {}
    for row in load_all():
        word = str(row.get("relation", "") or "related")
        pair = f"{_kind_of(str(row.get('subject', '')))} → {_kind_of(str(row.get('object', '')))}"
        pairs.setdefault(word, {})
        pairs[word][pair] = pairs[word].get(pair, 0) + 1
    if not pairs:
        print("none")
        return
    width = max(14, max(len(word) for word in pairs) + 1)
    for word in sorted(pairs):
        edges = sum(pairs[word].values())
        ranked = sorted(pairs[word].items(), key=lambda item: (-item[1], item[0]))
        kinds = ", ".join(
            pair if len(ranked) == 1 else f"{pair} ({count})" for pair, count in ranked[:4]
        )
        if len(ranked) > 4:
            kinds += f", +{len(ranked) - 4} more"
        count = f"{edges} edge{'s' if edges != 1 else ''}"
        print(f"{word:<{width}} {count:<10} {kinds}")


def _kind_of(object_id: str) -> str:
    """An endpoint's kind, read from its id without loading the object:
    minted ids carry their kind's prefix (`org_...`), adapter kinds store
    their REF (`project:...`)."""
    if ":" in object_id:
        return object_id.split(":", 1)[0]
    prefix = object_id.split("_", 1)[0]
    return next((kind for kind, spec in catalog.SPECS.items() if spec["prefix"] == prefix), "?")


def point_edge_reads_at_show(argv: list[str]) -> None:
    """`ws relations of REF` and `ws relations REF` are the natural guesses for
    an object's edges, and argparse answers both with a bare `invalid
    choice`. `ws show REF` lists them, so refuse with that command."""
    if argv[:1] != ["relations"] or len(argv) < 2:
        return
    if argv[1] != "of" and (":" not in argv[1] or argv[1].startswith("-")):
        return
    words = argv[2:] if argv[1] == "of" else argv[1:]
    fail(
        "an object's relations are listed by `ws show`, under the record\n"
        f"try: ws show {' '.join(words) if words else 'REF'}"
    )


def add_parsers(sub: argparse._SubParsersAction) -> None:
    relate = sub.add_parser(
        "relate",
        help="assert one edge between two objects",
        description="Assert one edge: `ws relate A to B as works-at`. The filler "
        "words `to` and `as` are optional. Duplicate edges are no-ops. Prints "
        "the edge's REF, relation:<id>, for `ws show`, `ws edit` and `ws delete`.",
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
        help="remove an edge; the older spelling of `ws delete relation:<id>`",
        description="Remove an edge, named by its relation REF or by the sentence "
        "that created it. The older spelling of `ws delete relation:<id>`.",
    )
    unrelate.add_argument(
        "references", nargs="+", metavar="REF",
        help="relation:<id>, or SUBJECT_REF [to] OBJECT_REF [as RELATION WORDS]",
    )
    unrelate.add_argument("--as", dest="relation")
    unrelate.add_argument("--dry-run", action="store_true")
    unrelate.set_defaults(func=command_unrelate)

    parser = sub.add_parser(
        "relations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="the graph layer: bare, it lists the relation words in use",
        description="The graph of edges between objects. Bare, it lists the relation\n"
        "words in use, with how many edges carry each.",
        epilog="""Every edge command:
  ws relate REF to REF as WORDS        add an edge; prints its relation:<id>
  ws show REF                          an object, then its relations with their REFs
  ws show relation:<id>                one edge in full: dates, source, history
  ws edit relation:<id> --as WORDS     change its words or validity dates
  ws delete relation:<id>              remove it
""",
    )
    parser.set_defaults(func=command_relations_vocabulary)
    actions = parser.add_subparsers(dest="relations_command", metavar="COMMAND")
    # Edges are read, changed and removed through the universal REF tools;
    # `edit` stays here as the older spelling of `ws edit relation:<id>`.
    edit_parser = actions.add_parser(
        "edit", help="change an edge; the older spelling of `ws edit relation:<id>`"
    )
    edit_parser.add_argument("relation_id")
    edit_arguments(edit_parser)
    edit_parser.set_defaults(func=command_relations_edit)
