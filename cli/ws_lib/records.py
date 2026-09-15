"""Shared helpers for small, dependency-free canonical YAML records."""

from __future__ import annotations

import datetime as dt
import contextlib
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

from ws_lib import yamlish


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_SAFE_SCALAR = re.compile(r"^[A-Za-z0-9./:@_+-][A-Za-z0-9 ./:@_+-]*$")
# A colon is only legal unquoted when it is not followed by whitespace or the
# end of the value: "10:30" and "https://x" are plain scalars, but a title like
# "The Virtual Lab: Modelling" would terminate the key and emit broken YAML.
_PLAIN_BREAKS_MAPPING = re.compile(r":(?:\s|$)")


def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def today() -> str:
    return dt.date.today().isoformat()


def _base32(value: int, width: int) -> str:
    out = ["0"] * width
    for index in range(width - 1, -1, -1):
        out[index] = _CROCKFORD[value & 31]
        value >>= 5
    return "".join(out)


def new_id(prefix: str) -> str:
    """Return a sortable ULID-shaped identifier without a third-party package."""
    milliseconds = int(dt.datetime.now().timestamp() * 1000)
    randomness = int.from_bytes(secrets.token_bytes(10), "big")
    return f"{prefix}_{_base32(milliseconds, 10)}{_base32(randomness, 16)}"


def yaml_scalar(value) -> str:
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if (
        text
        and _SAFE_SCALAR.fullmatch(text)
        and not _PLAIN_BREAKS_MAPPING.search(text)
        and text.lower() not in {"true", "false"}
    ):
        return text
    return json.dumps(text, ensure_ascii=False)


def dump_yaml(data: dict) -> str:
    """Serialize the mapping/list/scalar subset understood by ``yamlish``."""

    def emit_mapping(mapping: dict, indent: int) -> list[str]:
        lines: list[str] = []
        pad = " " * indent
        for key, value in mapping.items():
            if value is None:
                continue
            if isinstance(value, dict):
                if value:
                    lines.append(f"{pad}{key}:")
                    lines.extend(emit_mapping(value, indent + 2))
                else:
                    lines.append(f"{pad}{key}: {{}}")
            elif isinstance(value, list):
                if not value:
                    lines.append(f"{pad}{key}: []")
                elif all(not isinstance(item, (dict, list)) for item in value):
                    rendered = ", ".join(yaml_scalar(item) for item in value)
                    lines.append(f"{pad}{key}: [{rendered}]")
                else:
                    lines.append(f"{pad}{key}:")
                    for item in value:
                        if isinstance(item, dict):
                            first = True
                            for child_key, child_value in item.items():
                                prefix = f"{pad}  - " if first else f"{pad}    "
                                first = False
                                if isinstance(child_value, list):
                                    rendered = ", ".join(yaml_scalar(part) for part in child_value)
                                    lines.append(f"{prefix}{child_key}: [{rendered}]")
                                else:
                                    lines.append(f"{prefix}{child_key}: {yaml_scalar(child_value)}")
                        else:
                            lines.append(f"{pad}  - {yaml_scalar(item)}")
            else:
                lines.append(f"{pad}{key}: {yaml_scalar(value)}")
        return lines

    return "\n".join(emit_mapping(data, 0)).rstrip() + "\n"


def load_record(path: Path) -> dict:
    if not path.exists():
        return {}
    return yamlish.load_mapping(path.read_text(encoding="utf-8"))


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = dump_yaml(data)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextlib.contextmanager
def write_lock(directory: Path):
    """Serialize a read-modify-write transaction where advisory locks exist."""
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / ".write.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            import fcntl
        except ImportError:  # pragma: no cover - best-effort Windows fallback
            yield
            return
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def provenance(source: str = "", observed_at: str = "", fields: list[str] | None = None) -> dict:
    return {
        "source": source,
        "observed_at": observed_at,
        "recorded_at": now(),
        "fields": fields or [],
    }
