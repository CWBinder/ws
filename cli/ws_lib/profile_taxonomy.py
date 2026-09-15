"""Controlled vocabulary for profile-object types."""

from __future__ import annotations

import argparse

from ws_lib import paths, records, taxonomy


TAXONOMY = paths.PROFILE_TAXONOMY
DEFAULTS = {
    "type": [
        "identity",
        "education",
        "work-experience",
        "publication",
        "talk",
        "teaching",
        "award",
        "skill",
        "volunteering",
    ]
}
HEADER = [
    "Profile-object types in default CV section order.",
    "Edit this file directly, or use:",
    "  ws profile add-type <type>",
]


class TaxonomyError(ValueError):
    pass


def load_taxonomy() -> dict[str, list[str]]:
    return taxonomy.load(TAXONOMY, DEFAULTS)


def type_ids() -> list[str]:
    return load_taxonomy()["type"]


def ensure():
    if not TAXONOMY.exists():
        taxonomy.write(TAXONOMY, load_taxonomy(), HEADER)
    return TAXONOMY


def resolve(value: str) -> str | None:
    wanted = taxonomy.slug(value)
    if not wanted:
        return ""
    values = type_ids()
    if wanted in values:
        return wanted
    matches = [item for item in values if item.startswith(wanted)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise TaxonomyError(
            f"ambiguous profile type '{value}': {', '.join(matches)}"
        )
    return None


def accept_type(value: str) -> str:
    try:
        resolved = resolve(value)
    except TaxonomyError:
        raise
    if not resolved:
        raise TaxonomyError(
            f"unknown profile type: {value} "
            "(extend with `ws profile add-type`)"
        )
    return resolved


def add_type(value: str) -> str:
    type_id = taxonomy.slug(value)
    if not type_id:
        raise TaxonomyError("profile type must contain a letter or number")
    with records.write_lock(TAXONOMY.parent):
        if type_id in type_ids():
            raise TaxonomyError(f"profile type already exists: {type_id}")
        data = load_taxonomy()
        data["type"].append(type_id)
        taxonomy.write(TAXONOMY, data, HEADER)
    return type_id


def findings() -> list[dict]:
    if not TAXONOMY.exists():
        if not paths.PROFILE_ITEMS.exists() or not any(paths.PROFILE_ITEMS.iterdir()):
            return []
        return [{
            "severity": "error",
            "message": f"missing profile taxonomy: {TAXONOMY}",
        }]
    results = []
    seen = set()
    for value in type_ids():
        if value in seen:
            results.append({
                "severity": "error",
                "id": value,
                "message": f"duplicate profile type: {value}",
            })
        seen.add(value)
    return results


def command_taxonomy(_args: argparse.Namespace) -> None:
    print(f"taxonomy: {TAXONOMY}")
    print("type: " + ", ".join(type_ids()))


def command_add_type(args: argparse.Namespace) -> None:
    try:
        value = add_type(args.value)
    except TaxonomyError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(f"added: {value}")
