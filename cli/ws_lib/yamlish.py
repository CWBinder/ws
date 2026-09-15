"""Minimal, dependency-free YAML reader shared by all ws_lib modules.

Covers the subset ws writes itself: scalars (str/int/bool), block lists,
lists of mappings, nested mappings, inline [] / {} flow values, folded
block scalars (``key: >``), and ``#`` comments. It is not a general YAML
parser: anchors, multi-line quoted strings, and tabs are unsupported.
"""

from __future__ import annotations

import json
import re

FOLDED_MARKERS = {">", ">-", ">+", "|", "|-", "|+"}


def _split_flow(s: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote = ""
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[{":
            depth += 1
            buf.append(ch)
        elif ch in "]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return [p.strip() for p in parts]


def scalar(s: str):
    s = s.strip()
    if s == "":
        return ""
    if s == "[]":
        return []
    if s == "{}":
        return {}
    if s[0] == "[":
        return [scalar(x) for x in _split_flow(s[1:-1])]
    if s[0] == "{":
        out: dict = {}
        for part in _split_flow(s[1:-1]):
            key, _, val = part.partition(":")
            out[key.strip()] = scalar(val)
        return out
    if s[0] in "\"'":
        if s[0] == '"':
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
        inner = s[1:-1]
        if s[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    return s


def _clean_lines(text: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = raw
        if line.count('"') % 2 == 0:
            idx = line.find(" #")
            if idx != -1:
                line = line[:idx]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        out.append((indent, line.strip()))
    return out


def load_yaml(text: str):
    lines = _clean_lines(text)
    if not lines:
        return {}
    pos = [0]

    def parse_block(indent: int):
        return parse_seq(indent) if lines[pos[0]][1].startswith("- ") else parse_map(indent)

    def parse_folded(indent: int, marker: str) -> str:
        parts: list[str] = []
        while pos[0] < len(lines) and lines[pos[0]][0] > indent:
            parts.append(lines[pos[0]][1])
            pos[0] += 1
        joiner = " " if marker.startswith(">") else "\n"
        return joiner.join(parts)

    def parse_map(indent: int) -> dict:
        result: dict = {}
        while pos[0] < len(lines):
            ind, txt = lines[pos[0]]
            if ind != indent or txt.startswith("- "):
                break
            key, _, val = txt.partition(":")
            key, val = key.strip(), val.strip()
            pos[0] += 1
            if val in FOLDED_MARKERS:
                result[key] = parse_folded(indent, val)
            elif val == "":
                if pos[0] < len(lines) and lines[pos[0]][0] > indent:
                    result[key] = parse_block(lines[pos[0]][0])
                else:
                    result[key] = ""
            else:
                result[key] = scalar(val)
        return result

    def parse_seq(indent: int) -> list:
        items: list = []
        while pos[0] < len(lines):
            ind, txt = lines[pos[0]]
            if ind != indent or not txt.startswith("- "):
                break
            rest = txt[2:].strip()
            if rest and (rest[0] in "\"'[{" or ":" not in rest):
                items.append(scalar(rest))
                pos[0] += 1
                continue
            key, _, val = rest.partition(":")
            key, val = key.strip(), val.strip()
            pos[0] += 1
            item: dict = {}
            if val in FOLDED_MARKERS:
                item[key] = parse_folded(indent, val)
            elif val == "":
                if pos[0] < len(lines) and lines[pos[0]][0] > indent:
                    item[key] = parse_block(lines[pos[0]][0])
                else:
                    item[key] = ""
            else:
                item[key] = scalar(val)
            while pos[0] < len(lines) and lines[pos[0]][0] > indent and not lines[pos[0]][1].startswith("- "):
                item.update(parse_map(lines[pos[0]][0]))
            items.append(item)
        return items

    return parse_block(lines[0][0])


def load_mapping(text: str) -> dict:
    """Like load_yaml, but always returns a dict (empty on non-mapping input)."""
    data = load_yaml(text)
    return data if isinstance(data, dict) else {}
