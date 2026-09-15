"""Controlled vocabulary for the document ``type`` classifier.

The taxonomy file is the same sparse shape as every other taxonomy: the
classifier key mapping to a flat list of allowed values, parsed and written
by the shared engine in ``ws_lib/taxonomy.py``. Unique prefixes resolve
(``pr`` -> ``presentation``); there are no aliases or labels.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import textwrap
from pathlib import Path

from ws_lib import paths, records, taxonomy


TAXONOMY = paths.DOCUMENT_TAXONOMY
DEFAULTS = {
    "type": [
        "abstract",
        "presentation",
        "contract",
        "receipt",
        "invoice",
        "report",
        "certificate",
        "form",
        "letter",
    ],
}
HEADER = [
    "Edit this file directly, or use:",
    "  ws documents types add <type>",
    "The document add wizard also offers to add unknown values here.",
]


class TaxonomyError(ValueError):
    pass


def load_taxonomy() -> dict[str, list[str]]:
    """Uniform taxonomy interface: {classifier_key: [values]}."""
    return taxonomy.load(TAXONOMY, DEFAULTS)


def type_ids() -> list[str]:
    return load_taxonomy()["type"]


def ensure() -> Path:
    if not TAXONOMY.exists():
        taxonomy.write(
            TAXONOMY, {key: list(values) for key, values in DEFAULTS.items()}, HEADER
        )
    return TAXONOMY


def findings() -> list[dict]:
    if not TAXONOMY.exists():
        if (
            not paths.DOCUMENT_OBJECTS.exists()
            or not any(paths.DOCUMENT_OBJECTS.iterdir())
        ):
            return []
        return [{
            "severity": "error",
            "message": f"missing document taxonomy: {TAXONOMY}",
        }]
    results: list[dict] = []
    seen: set[str] = set()
    for value in type_ids():
        if value in seen:
            results.append({
                "severity": "error",
                "id": value,
                "message": f"duplicate document type: {value}",
            })
        seen.add(value)
    return results


def resolve(value: str) -> str | None:
    wanted = taxonomy.slug(value)
    if not wanted:
        return ""
    ids = type_ids()
    if wanted in ids:
        return wanted
    matches = {type_id for type_id in ids if type_id.startswith(wanted)}
    if len(matches) == 1:
        return matches.pop()
    if len(matches) > 1:
        raise TaxonomyError(
            f"ambiguous document type '{value}': {', '.join(sorted(matches))}"
        )
    return None


def add_type(value: str) -> str:
    type_id = taxonomy.slug(value)
    if not type_id:
        raise TaxonomyError("document type must contain a letter or number")
    with records.write_lock(TAXONOMY.parent):
        if type_id in type_ids():
            raise TaxonomyError(f"document type already exists: {type_id}")
        data = load_taxonomy()
        data["type"].append(type_id)
        taxonomy.write(TAXONOMY, data, HEADER)
    return type_id


def add_taxonomy_value(key: str, value: str) -> None:
    if key != "type":
        raise SystemExit("error: document taxonomy has one key: type")
    try:
        type_id = add_type(value)
    except TaxonomyError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(f"added: {type_id}")


def _document_type(data: dict) -> str:
    classification = data.get("classification", {})
    if isinstance(classification, dict) and classification.get("type"):
        return str(classification["type"])
    return str(data.get("document_type", "") or "")


def rename_type(old_value: str, new_value: str, dry_run: bool = False) -> tuple[str, str, int]:
    old_id = resolve(old_value)
    if not old_id:
        raise TaxonomyError(f"unknown document type: {old_value}")
    new_id = taxonomy.slug(new_value)
    if not new_id:
        raise TaxonomyError("new document type must contain a letter or number")
    if new_id in type_ids() and new_id != old_id:
        raise TaxonomyError(f"document type already exists: {new_id}")
    affected = []
    if paths.DOCUMENT_OBJECTS.exists():
        for path in sorted(paths.DOCUMENT_OBJECTS.glob("*.yaml")):
            data = records.load_record(path)
            if _document_type(data) == old_id:
                affected.append((path, data))
    if dry_run:
        return old_id, new_id, len(affected)
    with records.write_lock(TAXONOMY.parent):
        data = load_taxonomy()
        data["type"] = [new_id if value == old_id else value for value in data["type"]]
        taxonomy.write(TAXONOMY, data, HEADER)
        for path, document in affected:
            classification = document.get("classification", {})
            if not isinstance(classification, dict):
                classification = {}
            classification["type"] = new_id
            document["classification"] = classification
            document.pop("document_type", None)
            document["updated_at"] = records.now()
            records.atomic_write(path, document)
    from ws_lib import indexing

    indexing.invalidate()
    return old_id, new_id, len(affected)


def remove_type(type_value: str, dry_run: bool = False) -> tuple[str, int]:
    type_id = resolve(type_value)
    if not type_id:
        raise TaxonomyError(f"unknown document type: {type_value}")
    affected = []
    if paths.DOCUMENT_OBJECTS.exists():
        for path in sorted(paths.DOCUMENT_OBJECTS.glob("*.yaml")):
            data = records.load_record(path)
            if _document_type(data) == type_id:
                affected.append(path)
    if affected:
        raise TaxonomyError(
            f"document type '{type_id}' is used by {len(affected)} document(s); "
            "reclassify them before removing it"
        )
    if dry_run:
        return type_id, 0
    with records.write_lock(TAXONOMY.parent):
        data = load_taxonomy()
        data["type"] = [value for value in data["type"] if value != type_id]
        taxonomy.write(TAXONOMY, data, HEADER)
    return type_id, 0


def _matches(text: str) -> list[str]:
    wanted = taxonomy.slug(text)
    return [
        type_id
        for type_id in type_ids()
        if not wanted or type_id.startswith(wanted)
    ]


@contextlib.contextmanager
def _tab_completion():
    try:
        import readline
    except ImportError:  # pragma: no cover - platform fallback
        yield
        return
    previous = readline.get_completer()
    previous_delims = readline.get_completer_delims()

    def completer(text: str, state: int):
        matches = _matches(text)
        return matches[state] if state < len(matches) else None

    readline.set_completer(completer)
    readline.set_completer_delims(" \t\n")
    if "libedit" in (readline.__doc__ or ""):
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
    try:
        yield
    finally:
        readline.set_completer(previous)
        readline.set_completer_delims(previous_delims)


def prompt_type() -> str:
    ensure()
    print("Valid document types:")
    print(
        textwrap.fill(
            ", ".join(type_ids()),
            width=max(40, shutil.get_terminal_size((80, 24)).columns),
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    with _tab_completion():
        while True:
            value = input(
                "Type [Tab completes; empty leaves unclassified; Ctrl-C cancels]: "
            ).strip()
            if not value:
                return ""
            try:
                resolved = resolve(value)
            except TaxonomyError as exc:
                print(str(exc), file=sys.stderr)
                continue
            if resolved:
                return resolved
            answer = input(
                f"'{taxonomy.slug(value)}' is not a valid document type. "
                "Add it for future use? [y/N] "
            ).strip().casefold()
            if answer in {"y", "yes"}:
                type_id = add_type(value)
                print(f"added document type: {type_id}")
                return type_id


def accept_type(
    value: str, *, prompt_add: bool = False, add_unknown: bool = False
) -> str:
    resolved = resolve(value)
    if resolved is not None:
        ensure()
        return resolved
    type_id = taxonomy.slug(value)
    if add_unknown:
        added = add_type(type_id)
        print(f"added document type: {added}")
        return added
    if prompt_add:
        answer = input(
            f"'{type_id}' is not a valid document type. "
            "Add it for future use? [y/N] "
        ).strip().casefold()
        if answer in {"y", "yes"}:
            added = add_type(type_id)
            print(f"added document type: {added}")
            return added
    raise TaxonomyError(
        f"unknown document type: {type_id}; "
        f"add it with `ws documents types add {type_id}`"
    )


def command_taxonomy(_args: argparse.Namespace) -> None:
    ensure()
    try:
        shown = "~/" + str(TAXONOMY.resolve().relative_to(Path.home()))
    except ValueError:
        shown = str(TAXONOMY)
    print(f"taxonomy: {shown}")
    print("type: " + ", ".join(type_ids()))


def command_list(args: argparse.Namespace) -> None:
    ensure()
    if args.json:
        print(json.dumps(type_ids(), ensure_ascii=False, indent=2))
        return
    for type_id in type_ids():
        print(type_id)


def command_add(args: argparse.Namespace) -> None:
    add_taxonomy_value("type", args.type)


def command_rename(args: argparse.Namespace) -> None:
    try:
        old_id, new_id, affected = rename_type(args.type, args.to, args.dry_run)
    except TaxonomyError as exc:
        raise SystemExit(f"error: {exc}") from exc
    action = "would rename" if args.dry_run else "renamed"
    if not args.dry_run:
        from ws_lib import anatomy

        anatomy.rebuild_documents()
    print(f"{action}: {old_id} -> {new_id}")
    print(f"document records: {affected}")


def command_remove(args: argparse.Namespace) -> None:
    try:
        type_id, affected = remove_type(args.type, args.dry_run)
    except TaxonomyError as exc:
        raise SystemExit(f"error: {exc}") from exc
    action = "would remove" if args.dry_run else "removed"
    print(f"{action} document type: {type_id}")
    print(f"document records: {affected}")


def add_parser(actions: argparse._SubParsersAction) -> None:
    parser = actions.add_parser("types", help="manage valid values for the type classifier")
    sub = parser.add_subparsers(dest="document_types_command", required=True)
    listing = sub.add_parser("list", help="list the allowed document types")
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=command_list)
    add = sub.add_parser("add", help="add a new allowed document type")
    add.add_argument("type")
    add.set_defaults(func=command_add)
    rename = sub.add_parser("rename", help="rename a document type, updating the documents that use it")
    rename.add_argument("type")
    rename.add_argument("--to", required=True, metavar="TYPE", help="the new type id")
    rename.add_argument("--dry-run", action="store_true")
    rename.set_defaults(func=command_rename)
    remove = sub.add_parser("remove", help="remove an unused document type")
    remove.add_argument("type")
    remove.add_argument("--dry-run", action="store_true")
    remove.set_defaults(func=command_remove)
