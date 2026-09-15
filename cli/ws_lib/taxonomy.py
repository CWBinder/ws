"""One engine for classifier taxonomies.

A taxonomy is the allowed-value list behind a classifier, stored as one YAML
file per domain in workspace data. Keys are the classifier names themselves
(`type`, `fields`). Every taxonomy-bearing domain wraps this engine with the
same two calls, so agents can rely on one interface everywhere:

    <domain>.load_taxonomy()               -> {classifier_key: [values]}
    <domain>.add_taxonomy_value(key, val)  -> slug, dedupe, append, write

Statuses are deliberately not taxonomies: lifecycle vocabularies are fixed in
contracts/statuses.md and are never extendable from the CLI.
"""

from __future__ import annotations

import re
from pathlib import Path

from ws_lib import yamlish


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")


def _text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def load(
    path: Path,
    defaults: dict[str, list[str] | dict[str, list[str]]],
) -> dict[str, list[str] | dict[str, list[str]]]:
    """Read a taxonomy file into lists and optional parent -> children maps.

    Missing files, missing keys, and empty lists fall back to the domain
    defaults, so a fresh workspace works before any file exists."""
    data = {
        key: (
            {parent: list(children) for parent, children in values.items()}
            if isinstance(values, dict)
            else list(values)
        )
        for key, values in defaults.items()
    }
    if not path.exists():
        return data
    parsed = yamlish.load_mapping(path.read_text(encoding="utf-8"))
    for key, default in defaults.items():
        value = parsed.get(key)
        if isinstance(default, list) and isinstance(value, list) and value:
            data[key] = [_text(item) for item in value]
        elif isinstance(default, dict) and isinstance(value, dict):
            nested: dict[str, list[str]] = {}
            for parent, children in value.items():
                if isinstance(children, list):
                    nested[_text(parent)] = [_text(item) for item in children]
            if nested:
                data[key] = nested
    return data


def write(
    path: Path,
    data: dict[str, list[str] | dict[str, list[str]]],
    header: list[str],
) -> None:
    lines = ["schema_version: 1", ""]
    lines.extend(f"# {line}" if line else "#" for line in header)
    for key, values in data.items():
        lines.append("")
        lines.append(f"{key}:")
        if isinstance(values, dict):
            if not values:
                lines[-1] += " {}"
            for parent, children in values.items():
                if children:
                    lines.append(f"  {parent}:")
                    lines.extend(f"    - {value}" for value in children)
                else:
                    lines.append(f"  {parent}: []")
        elif values:
            lines.extend(f"  - {value}" for value in values)
        else:
            lines.append("  []")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def add(
    path: Path,
    defaults: dict[str, list[str] | dict[str, list[str]]],
    header: list[str],
    key: str,
    value: str,
) -> None:
    entry = slug(value)
    if not entry:
        raise ValueError("taxonomy value must contain a letter or number")
    data = load(path, defaults)
    values = data.setdefault(key, [])
    if not isinstance(values, list):
        raise ValueError(f"taxonomy key is not a flat list: {key}")
    if entry in values:
        print(f"exists: {entry}")
        return
    values.append(entry)
    write(path, data, header)
    print(f"added: {entry}")


def add_nested(
    path: Path,
    defaults: dict[str, list[str] | dict[str, list[str]]],
    header: list[str],
    key: str,
    parent: str,
    value: str,
) -> None:
    parent_id = slug(parent)
    entry = slug(value)
    if not parent_id or not entry:
        raise ValueError("taxonomy parent and value must contain a letter or number")
    data = load(path, defaults)
    mapping = data.setdefault(key, {})
    if not isinstance(mapping, dict):
        raise ValueError(f"taxonomy key is not a parent mapping: {key}")
    values = mapping.setdefault(parent_id, [])
    if entry in values:
        print(f"exists: {parent_id}/{entry}")
        return
    values.append(entry)
    write(path, data, header)
    print(f"added: {parent_id}/{entry}")
