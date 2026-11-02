"""The owner: whose workspace this is (contracts/objects.md).

Two records hold the answer: the person labelled `owner`, for private facts,
and the profile identity, for public ones. Either may be missing; with neither
there is no owner and `ws owner` prints nothing, so anything may call it.
Nothing here writes.
"""

from __future__ import annotations

import argparse
import json

from ws_lib import catalog


# Bookkeeping, and what the header already says.
HIDDEN = {
    "schema_version", "id", "key", "kind", "name", "type", "owner", "status",
    "created_at", "updated_at", "provenance", "redirect_to",
}


def _is_identity(ref: catalog.ObjectRef) -> bool:
    data = ref.data or {}
    return ref.type == "profile" and data.get("type") == "identity" and str(data.get("status", "") or "") != "merged"


def _records(objects: list[catalog.ObjectRef]) -> tuple[catalog.ObjectRef | None, catalog.ObjectRef | None]:
    return next(filter(catalog.is_owner, objects), None), next(filter(_is_identity, objects), None)


def find(objects: list[catalog.ObjectRef]) -> dict | None:
    """The owner's name and REFs, or None when neither record exists. The
    person's name wins: it is the one others use for them."""
    person, identity = _records(objects)
    if person is None and identity is None:
        return None
    return {
        "name": (person or identity).title,
        "person": person.ref if person else "",
        "identity": identity.ref if identity else "",
    }


def _details(ref: catalog.ObjectRef | None) -> dict:
    return {
        key: value for key, value in (ref.data or {}).items()
        if key not in HIDDEN and value not in (None, "", [])
    } if ref else {}


def _lines(ref: catalog.ObjectRef | None, label: str) -> list[str]:
    if ref is None:
        return []
    lines = [f"{label}: {ref.ref}"]
    for key, value in _details(ref).items():
        lines.append(f"  {key}: {', '.join(map(str, value)) if isinstance(value, list) else value}")
    return lines


def command_owner(args: argparse.Namespace) -> None:
    objects = [*catalog.stored_objects("person"), *catalog.stored_objects("profile")]
    found = find(objects)
    person, identity = _records(objects)
    if args.json:
        print(json.dumps(
            found and {**found, "person_details": _details(person), "identity_details": _details(identity)},
            ensure_ascii=False, indent=2, sort_keys=True,
        ))
    elif found:
        print("\n".join([f"owner: {found['name']}", *_lines(person, "person"), *_lines(identity, "identity")]))


def add_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser(
        "owner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="whose workspace this is: the owner's person record and profile identity",
        description="Print whose workspace this is: the person labelled as the owner, "
        "with their private facts, and the profile identity, with their public ones. "
        "With neither it prints nothing and succeeds, so anything may call it.",
    )
    parser.add_argument("--json", action="store_true", help="print JSON; null when there is no owner")
    parser.set_defaults(func=command_owner)
