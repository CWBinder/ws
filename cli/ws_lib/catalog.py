"""Canonical object catalog and adapters for existing workspace domains."""

from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import json
import re
import shutil
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from ws_lib import (
    anatomy,
    document_taxonomy,
    literature,
    paths,
    profile_taxonomy,
    project,
    records,
)


@dataclass(frozen=True)
class ObjectRef:
    id: str
    type: str
    title: str
    path: Path | None = None
    aliases: tuple[str, ...] = ()
    data: dict | None = None
    key: str = ""

    @property
    def ref(self) -> str:
        return f"{self.type}:{self.key}"


SPECS = {
    "person": {"prefix": "person", "dir": paths.PEOPLE, "plural": "people"},
    "organisation": {"prefix": "org", "dir": paths.ORGANISATIONS, "plural": "organisations"},
    "event": {"prefix": "event", "dir": paths.EVENTS, "plural": "events"},
    "task": {"prefix": "task", "dir": paths.TASKS, "plural": "tasks"},
    "document": {"prefix": "doc", "dir": paths.DOCUMENT_OBJECTS, "plural": "documents"},
    "resource": {"prefix": "resource", "dir": paths.RESOURCE_ITEMS, "plural": "resources"},
    "profile": {"prefix": "profile", "dir": paths.PROFILE_ITEMS, "plural": "profile"},
}


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _joined(value: str | list[str]) -> str:
    # Identity positionals use nargs="+" so multi-word names need no quotes;
    # tests and internal callers may still pass a plain string.
    return " ".join(value) if isinstance(value, list) else value


def key_slug(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.casefold()).strip("-")


def _record_path(type_name: str, key: str) -> Path:
    if type_name == "resource":
        return Path(SPECS[type_name]["dir"]) / key / "resource.yaml"
    return Path(SPECS[type_name]["dir"]) / f"{key}.yaml"


def _record_paths(type_name: str) -> list[Path]:
    root = Path(SPECS[type_name]["dir"])
    pattern = "*/resource.yaml" if type_name == "resource" else "*.yaml"
    return sorted(root.glob(pattern)) if root.exists() else []


def _validate_dates(type_name: str, values: dict) -> None:
    fields = ["observed_at"]
    if type_name == "event":
        fields += ["start", "end"]
    if type_name == "task":
        fields += ["due"]
    if type_name == "profile":
        for field in ("start", "end"):
            value = str(values.get(field, "") or "").strip()
            if not value or value.casefold() == "present":
                continue
            if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
                fail(f"{field} must be YYYY, YYYY-MM, YYYY-MM-DD, or present")
        return
    for field in fields:
        value = str(values.get(field, "") or "")
        if not value:
            continue
        try:
            dt.date.fromisoformat(value[:10])
        except ValueError:
            fail(f"{field} must be an ISO date or datetime")
    if type_name == "event":
        start = str(values.get("start", "") or "")[:10]
        end = str(values.get("end", "") or "")[:10]
        if start and end and start > end:
            fail("event start must not be after end")


def _ref_from_record(path: Path, data: dict) -> ObjectRef | None:
    object_id = str(data.get("id", ""))
    type_name = str(data.get("kind", ""))
    title = str(data.get("name", ""))
    if not object_id or type_name not in SPECS or not title:
        return None
    aliases = data.get("aliases", [])
    key = str(data.get("key", "") or "")
    if not key:
        # A record written before keys existed still has to be readable:
        # derive the key it would have been given.
        key = key_slug(title) or object_id.casefold()
    return ObjectRef(
        object_id,
        type_name,
        title,
        path,
        tuple(str(value) for value in aliases if isinstance(value, (str, int))),
        data,
        key,
    )


def stored_objects(type_name: str | None = None) -> list[ObjectRef]:
    names = [type_name] if type_name else list(SPECS)
    found: list[ObjectRef] = []
    for name in names:
        if name not in SPECS:
            continue
        for path in _record_paths(name):
            ref = _ref_from_record(path, records.load_record(path))
            if ref:
                found.append(ref)
    return found


def public_stored_objects(type_name: str | None = None) -> list[ObjectRef]:
    """Stored objects visible at the CLI boundary; merged tombstones stay internal."""
    return [
        obj for obj in stored_objects(type_name)
        if str((obj.data or {}).get("status", "") or "active") != "merged"
    ]


def document_type(data: dict) -> str:
    classification = data.get("classification", {})
    if isinstance(classification, dict) and classification.get("type"):
        return str(classification["type"])
    return str(data.get("document_type", "") or "")


def _document_date(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return dt.date.fromisoformat(text).isoformat()
    except ValueError:
        fail("document date must be YYYY-MM-DD")
    raise AssertionError("unreachable")


def _prompt_value(label: str) -> str:
    try:
        return input(f"{label}: ").strip()
    except EOFError:
        return ""


def _prompt_values(label: str) -> list[str]:
    raw = _prompt_value(f"{label} [comma-separated, Enter skips]")
    return [part.strip() for part in raw.split(",") if part.strip()]


def _interactive_create(args: argparse.Namespace) -> bool:
    return bool(
        getattr(args, "interactive", False)
        or (
            not getattr(args, "non_interactive", False)
            and not getattr(args, "json", False)
            and sys.stdin.isatty()
            and sys.stdout.isatty()
        )
    )


def _prompt_date(label: str) -> str:
    """One ISO date, re-asked until valid; Enter skips."""
    while True:
        typed = _prompt_value(f"{label} [YYYY-MM-DD, Enter skips]")
        if not typed:
            return ""
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", typed):
            try:
                dt.date.fromisoformat(typed)
                return typed
            except ValueError:
                pass
        print("use YYYY-MM-DD", file=sys.stderr)


def _wizard_collect(args: argparse.Namespace, type_name: str) -> None:
    """Ask for the kind's own facts not already supplied via flags. Every
    prompt is Enter-skippable. Relations are never asked: `ws relate` is the
    only way edges come into being."""
    if type_name == "task":
        # A task is quick capture: what, by when, how urgent. Aliases last;
        # the project or person it belongs to is an edge, made with `ws relate`.
        if not getattr(args, "description", None):
            args.description = _prompt_value("Description [Enter skips]") or None
        if getattr(args, "due", None) is None:
            args.due = _prompt_date("Due") or None
        if not getattr(args, "priority", None):
            args.priority = _prompt_value("Priority [e.g. low, normal, high; Enter skips]") or None
        if not getattr(args, "alias", None):
            args.alias = _prompt_values("Aliases") or None
        return
    if not getattr(args, "alias", None):
        args.alias = _prompt_values("Aliases") or None
    if not getattr(args, "description", None):
        args.description = _prompt_value("Description [Enter skips]") or None
    if type_name == "person":
        if not getattr(args, "preferred_name", None):
            args.preferred_name = _prompt_value("Preferred name [Enter skips]") or None
        if not getattr(args, "email", None):
            args.email = _prompt_values("Emails") or None
        if not getattr(args, "phone", None):
            args.phone = _prompt_values("Phones") or None
    elif type_name == "organisation":
        if not getattr(args, "type", None):
            args.type = _prompt_value("Type [Enter skips]") or None
        if not getattr(args, "website", None):
            args.website = _prompt_value("Website [Enter skips]") or None
    elif type_name == "event":
        if not getattr(args, "start", None):
            args.start = _prompt_value("Start [YYYY-MM-DD, Enter skips]") or None
        if not getattr(args, "end", None):
            args.end = _prompt_value("End [YYYY-MM-DD, Enter skips]") or None
        if not getattr(args, "location", None):
            args.location = _prompt_value("Location [Enter skips]") or None


def _prompt_document_date() -> str:
    while True:
        value = input(
            "Date [YYYY-MM-DD; empty leaves unclassified; Ctrl-C cancels]: "
        ).strip()
        try:
            return _document_date(value)
        except SystemExit:
            continue


def project_objects() -> list[ObjectRef]:
    found: list[ObjectRef] = []
    for name in project.existing_project_names():
        root = project.PROJECTS / name
        meta = project.parse_project_yaml(root / "project.yaml")
        title = meta.get("title") or name
        leaf = name.rsplit("/", 1)[-1]
        aliases = (name, leaf, f"project_{leaf}")
        found.append(ObjectRef(f"project:{name}", "project", title, root / "project.yaml", aliases, meta, name))
        # Subprojects are projects in identity: co-located to borrow the
        # parent's venv, but fully resolvable and relatable.
        for subrel in project.subproject_names(root):
            sub_root = root / subrel
            sub_meta = project.parse_project_yaml(sub_root / "subproject.yaml")
            sub_leaf = subrel.rsplit("/", 1)[-1]
            found.append(ObjectRef(
                f"project:{name}/{subrel}",
                "project",
                sub_meta.get("title") or project.project_title(sub_leaf, None),
                sub_root / "subproject.yaml",
                (f"{name}/{subrel}", sub_leaf),
                {**sub_meta, "parent": sub_meta.get("parent") or name},
                f"{name}/{subrel}",
            ))
    return found


def literature_objects() -> list[ObjectRef]:
    found: list[ObjectRef] = []
    for bib_path in literature.list_item_bibtex_files():
        key = bib_path.parent.name
        bibtex = literature.read(bib_path)
        title = literature.bibtex_field(bibtex, "title") or key
        found.append(
            ObjectRef(
                f"literature:{key}",
                "literature",
                re.sub(r"\s+", " ", title).strip(),
                bib_path,
                (key,),
                {
                    "key": key,
                    "citation": bibtex,
                    "fields": literature.info_fields(bib_path.parent),
                    "subfields": literature.info_subfields(bib_path.parent),
                    "summary": literature.read(bib_path.parent / "summary.md")
                    if (bib_path.parent / "summary.md").exists() else "",
                    "notes": literature.read(bib_path.parent / "notes.md")
                    if (bib_path.parent / "notes.md").exists() else "",
                },
                key,
            )
        )
    return found


def all_objects() -> list[ObjectRef]:
    return public_stored_objects() + project_objects() + literature_objects()


def findings(type_names: set[str] | None = None, stale_after: int = 180) -> list[dict]:
    names = type_names or set(SPECS)
    results: list[dict] = []
    seen: dict[tuple[str, str], str] = {}
    today = dt.date.today()
    for type_name in names:
        if type_name not in SPECS:
            continue
        root = Path(SPECS[type_name]["dir"])
        if not root.exists():
            continue
        for path in _record_paths(type_name):
            data = records.load_record(path)
            object_id = str(data.get("id", ""))
            if not object_id or str(data.get("kind", "")) != type_name or not str(data.get("name", "")):
                results.append({
                    "severity": "error",
                    "id": object_id or path.name,
                    "message": f"invalid {type_name} record: {path}",
                })
                continue
            key = str(data.get("key", "") or "")
            expected = "resource.yaml" if type_name == "resource" else (
                f"{key}.yaml" if key else "<stable-key>.yaml"
            )
            path_matches = path.name == expected
            if type_name == "resource":
                path_matches = path_matches and bool(key) and path.parent.name == key
            if not path_matches:
                results.append({
                    "severity": "error",
                    "id": object_id,
                    "message": (
                        f"resource record should be {key}/resource.yaml"
                        if type_name == "resource"
                        else f"filename should be {expected}"
                    ),
                })
            if str(data.get("status", "")) == "merged":
                # Tombstones redirect to their canonical record; they must not
                # trigger duplicate, staleness, or file checks.
                continue
            values = [str(data["name"]), *[str(item) for item in data.get("aliases", [])]]
            for value in values:
                identity = (type_name, _norm(value))
                if identity in seen and seen[identity] != object_id:
                    results.append({
                        "severity": "warning",
                        "id": object_id,
                        "message": f"duplicate name or alias '{value}' also used by {seen[identity]}",
                    })
                else:
                    seen[identity] = object_id
            if type_name == "event":
                start = str(data.get("start", ""))
                if start:
                    try:
                        event_date = dt.date.fromisoformat(start[:10])
                        if event_date < today and (data.get("status") or "active") in {"active", "tentative", "confirmed"}:
                            results.append({
                                "severity": "warning",
                                "id": object_id,
                                "message": f"past event is still {data.get('status')}",
                            })
                    except ValueError:
                        results.append({
                            "severity": "error", "id": object_id, "message": f"invalid start date: {start}",
                        })
            if type_name == "person" and (data.get("emails") or data.get("phones")):
                updated = str(data.get("updated_at", ""))[:10]
                try:
                    age = (today - dt.date.fromisoformat(updated)).days
                    if age > stale_after:
                        results.append({
                            "severity": "warning",
                            "id": object_id,
                            "message": f"contact facts have not been updated for {age} days",
                        })
                except ValueError:
                    pass
            if type_name == "document":
                assigned_type = document_type(data)
                try:
                    known_type = (
                        document_taxonomy.resolve(assigned_type)
                        if assigned_type
                        else ""
                    )
                except document_taxonomy.TaxonomyError as exc:
                    known_type = None
                    results.append({
                        "severity": "error",
                        "id": object_id,
                        "message": str(exc),
                    })
                if assigned_type and known_type is None:
                    results.append({
                        "severity": "error",
                        "id": object_id,
                        "message": f"unknown document type: {assigned_type}",
                    })
                stored_path = str(data.get("path", ""))
                if not stored_path:
                    results.append({"severity": "error", "id": object_id, "message": "document has no path"})
                elif data.get("path_root") == "documents":
                    file_path = paths.DOCUMENTS / stored_path
                    if not file_path.exists():
                        results.append({
                            "severity": "error", "id": object_id, "message": f"document file is missing: {stored_path}",
                        })
                elif not Path(stored_path).exists():
                    results.append({
                        "severity": "error", "id": object_id, "message": f"external document file is missing: {stored_path}",
                    })
            if type_name == "profile":
                profile_type = str(data.get("type", "") or "")
                try:
                    resolved_type = profile_taxonomy.resolve(profile_type)
                except profile_taxonomy.TaxonomyError as exc:
                    resolved_type = None
                    results.append({
                        "severity": "error",
                        "id": object_id,
                        "message": str(exc),
                    })
                if not profile_type or resolved_type is None:
                    results.append({
                        "severity": "error",
                        "id": object_id,
                        "message": f"unknown profile type: {profile_type or '(empty)'}",
                    })
    if "profile" in names:
        identities = [
            obj for obj in stored_objects("profile")
            if str((obj.data or {}).get("type", "")) == "identity"
            and str((obj.data or {}).get("status", "") or "active") != "merged"
        ]
        if len(identities) > 1:
            results.append({
                "severity": "error",
                "message": "profile may contain at most one active identity object",
            })
    ids: dict[str, ObjectRef] = {}
    refs: dict[str, ObjectRef] = {}
    for obj in all_objects():
        if type_names is not None and obj.type not in names:
            continue
        if obj.id in ids and ids[obj.id].path != obj.path:
            results.append({
                "severity": "error",
                "id": obj.id,
                "message": f"duplicate object ID in {ids[obj.id].path} and {obj.path}",
            })
        else:
            ids[obj.id] = obj
        if obj.ref in refs and refs[obj.ref].path != obj.path:
            results.append({
                "severity": "error",
                "id": obj.ref,
                "message": f"duplicate public REF in {refs[obj.ref].path} and {obj.path}",
            })
        else:
            refs[obj.ref] = obj
    return results


def resolve(value: str, type_name: str | None = None) -> ObjectRef:
    """Resolve one canonical public REF (`kind:key`), never a name or alias."""
    raw = value.strip()
    if ":" not in raw:
        expected = f"{type_name}:<key>" if type_name else "<kind>:<key>"
        fail(f"expected REF {expected}, got '{value}'; find it with `ws search {json.dumps(value)}`")
    kind, _separator, key = raw.partition(":")
    if not kind or not key:
        fail(f"invalid REF: {value}")
    if type_name and kind != type_name:
        fail(f"expected {type_name}:<key>, got {value}")
    candidates = [obj for obj in all_objects() if (not type_name or obj.type == type_name) and obj.ref == raw]
    if len(candidates) == 1:
        redirect = str((candidates[0].data or {}).get("redirect_to", ""))
        if redirect:
            return get(redirect) or candidates[0]
        return candidates[0]
    if len(candidates) > 1:
        fail(f"duplicate REF '{value}': " + ", ".join(obj.id for obj in candidates))
    # A repeated kind prefix is a typing accident, not a missing object: say so
    # rather than sending the user to search for a key that still carries one.
    if key.startswith(f"{kind}:"):
        fail(f"the kind prefix is repeated in '{value}'; you mean {kind}:{key[len(kind) + 1:]}")
    fail(f"object does not exist: {value}; find it with `ws search {json.dumps(key)}`")


def get(object_id: str) -> ObjectRef | None:
    return next((obj for obj in all_objects() if obj.id == object_id), None)


def public_object_data(ref: ObjectRef) -> dict:
    """Object metadata for CLI output without internal identity fields."""
    hidden = {"id", "key", "redirect_to"}
    public = {
        "ref": ref.ref,
        **{key: value for key, value in (ref.data or {}).items() if key not in hidden},
    }
    if ref.type == "resource" and ref.path:
        public["folder"] = str(ref.path.parent)
    return public


def _matches_ensure(
    type_name: str,
    title: str,
    email: str = "",
    path_value: str = "",
    start: str = "",
    website: str = "",
    classifier_type: str = "",
) -> list[ObjectRef]:
    wanted = _norm(title)
    matches: list[ObjectRef] = []
    for obj in public_stored_objects(type_name):
        data = obj.data or {}
        if data.get("status") == "merged":
            continue
        if (
            type_name == "profile"
            and classifier_type
            and str(data.get("type", "")) != classifier_type
        ):
            continue
        title_matches = wanted == _norm(obj.title) or any(wanted == _norm(alias) for alias in obj.aliases)
        if path_value:
            if _norm(path_value) == _norm(str(data.get("path", ""))):
                matches.append(obj)
            continue
        if start:
            if title_matches and start[:10] == str(data.get("start", ""))[:10]:
                matches.append(obj)
            continue
        if website:
            if _norm(website) == _norm(str(data.get("website", ""))) or title_matches:
                matches.append(obj)
            continue
        if email and any(_norm(email) == _norm(str(item)) for item in data.get("emails", [])):
            matches.append(obj)
            continue
        if title_matches:
            matches.append(obj)
    return list({obj.id: obj for obj in matches}.values())


def unique_key(type_name: str, title: str) -> str:
    base = key_slug(title) or str(SPECS[type_name]["prefix"])
    used = {obj.key for obj in stored_objects(type_name)}
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def create_object(type_name: str, title: str, values: dict, ensure: bool = False) -> tuple[ObjectRef, bool]:
    if type_name not in SPECS:
        fail(f"unsupported object type: {type_name}")
    title = title.strip()
    if not title:
        fail("title or name is required")
    _validate_dates(type_name, values)
    matches = _matches_ensure(
        type_name,
        title,
        str(values.get("email", "")),
        str(values.get("path", "")),
        str(values.get("start", "")),
        str(values.get("website", "")),
        str(values.get("type", "")) if type_name == "profile" else "",
    )
    if ensure and len(matches) == 1:
        existing = matches[0]
        existing_data = existing.data or {}
        source = str(values.get("source", "") or "")
        observed_at = str(values.get("observed_at", "") or "")
        changes: dict = {}
        for key in ("aliases", "emails", "phones", "tags"):
            if values.get(key):
                changes[f"add_{key}"] = values[key]
        for key, value in values.items():
            if key in {"source", "observed_at", "email", "aliases", "emails", "phones", "tags", "status"}:
                continue
            if value not in (None, "", []) and existing_data.get(key) in (None, "", []):
                changes[key] = value
        return edit_object(existing, changes, source, observed_at), False
    if ensure and len(matches) > 1:
        fail("ambiguous ensure: " + ", ".join(f"{obj.ref} ({obj.title})" for obj in matches))
    prefix = str(SPECS[type_name]["prefix"])
    object_id = records.new_id(prefix)
    key = unique_key(type_name, title)
    timestamp = records.now()
    data: dict = {
        "schema_version": 1,
        "id": object_id,
        "key": key,
        # `kind` names the concept; `type` stays free for domain classifiers.
        "kind": type_name,
        "name": title,
        "aliases": list(dict.fromkeys(values.pop("aliases", []) or [])),
    }
    # status is an optional classifier: written only when set; absent = active
    status_value = str(values.pop("status", "") or "")
    if status_value and status_value != "active":
        data["status"] = status_value
    source = str(values.pop("source", "") or "")
    observed_at = str(values.pop("observed_at", "") or "")
    values.pop("email", None)
    for field, value in values.items():
        if value not in (None, "", []):
            data[field] = value
    data["created_at"] = timestamp
    data["updated_at"] = timestamp
    if source or observed_at:
        fields = [field for field in data if field not in {"schema_version", "id", "kind", "created_at", "updated_at"}]
        data["provenance"] = [records.provenance(source, observed_at, fields)]
    path = _record_path(type_name, key)
    records.atomic_write(path, data)
    from ws_lib import indexing
    indexing.invalidate()
    return _ref_from_record(path, data), True  # type: ignore[return-value]


def edit_object(ref: ObjectRef, changes: dict, source: str = "", observed_at: str = "") -> ObjectRef:
    if ref.type not in SPECS or ref.path is None:
        fail(f"{ref.id} is owned by {ref.type}; edit it through that domain's command")
    data = records.load_record(ref.path)
    candidate = dict(data)
    candidate.update({
        key: value for key, value in changes.items()
        if not key.startswith(("add_", "remove_")) and value is not None
    })
    candidate["observed_at"] = observed_at
    _validate_dates(ref.type, candidate)
    changed: list[str] = []
    for key, value in changes.items():
        if key.startswith("add_"):
            target = key[4:]
            current = [str(item) for item in data.get(target, [])]
            for item in value or []:
                if item not in current:
                    current.append(item)
                    changed.append(target)
            data[target] = current
        elif key.startswith("remove_"):
            target = key[7:]
            remove = {str(item) for item in value or []}
            current = [str(item) for item in data.get(target, []) if str(item) not in remove]
            if current != data.get(target, []):
                changed.append(target)
            data[target] = current
        elif value is not None and data.get(key) != value:
            data[key] = value
            changed.append(key)
            if ref.type == "document" and key == "classification":
                if "document_type" in data:
                    data.pop("document_type")
                    changed.append("document_type")
    if changed:
        data["updated_at"] = records.now()
        if source or observed_at:
            history = data.get("provenance", [])
            if not isinstance(history, list):
                history = []
            history.append(records.provenance(source, observed_at, sorted(set(changed))))
            data["provenance"] = history
        records.atomic_write(ref.path, data)
        from ws_lib import indexing
        indexing.invalidate()
    return _ref_from_record(ref.path, data)  # type: ignore[return-value]


def merge_objects(duplicate: ObjectRef, canonical: ObjectRef, dry_run: bool = False) -> None:
    if duplicate.type != canonical.type or duplicate.type not in SPECS:
        fail("merge requires two stored objects of the same type")
    if duplicate.id == canonical.id:
        fail("cannot merge an object into itself")
    if dry_run:
        print(f"would merge: {duplicate.ref} -> {canonical.ref}")
        return
    from ws_lib import relations

    relations.redirect_object(duplicate.id, canonical.id)
    duplicate_data = records.load_record(duplicate.path)  # type: ignore[arg-type]
    canonical_data = records.load_record(canonical.path)  # type: ignore[arg-type]
    aliases = [*canonical_data.get("aliases", []), duplicate.title, *duplicate_data.get("aliases", [])]
    canonical_data["aliases"] = list(dict.fromkeys(str(item) for item in aliases if item))
    canonical_data["updated_at"] = records.now()
    records.atomic_write(canonical.path, canonical_data)  # type: ignore[arg-type]
    duplicate_data["status"] = "merged"
    duplicate_data["redirect_to"] = canonical.id
    duplicate_data["updated_at"] = records.now()
    records.atomic_write(duplicate.path, duplicate_data)  # type: ignore[arg-type]
    from ws_lib import indexing
    indexing.invalidate()
    print(f"merged: {duplicate.ref} -> {canonical.ref}")


def _json_or_lines(value, as_json: bool, lines: list[str]) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("\n".join(lines))


def command_create(args: argparse.Namespace) -> None:
    title = _joined(args.title)
    interactive = _interactive_create(args)
    if not title.strip() and interactive:
        label = "Name" if args.object_type in {"person", "organisation"} else "Title"
        while not title.strip():
            title = _prompt_value(label)
            if not title and not sys.stdin.isatty():
                fail(f"{label.lower()} is required")
    if interactive and args.object_type == "resource" and not getattr(args, "description", None):
        args.description = _prompt_value("Description (empty for none)") or None
    if args.object_type in {"person", "organisation", "event", "task"} and interactive:
        _wizard_collect(args, args.object_type)
    values = _values_from_args(args)
    ref, created = create_object(
        args.object_type, title, values, ensure=bool(getattr(args, "ensure", False))
    )
    _json_or_lines(
        {"ref": ref.ref, "kind": ref.type, "name": ref.title, "created": created},
        args.json,
        [f"created: {ref.ref}" if created else f"exists: {ref.ref}", f"{ref.type}: {ref.title}"],
    )


def command_ensure(args: argparse.Namespace) -> None:
    values = _values_from_args(args)
    ref, created = create_object(args.object_type, _joined(args.title), values, ensure=True)
    _json_or_lines(
        {"ref": ref.ref, "kind": ref.type, "name": ref.title, "created": created},
        args.json,
        [ref.ref],
    )


def command_list(args: argparse.Namespace) -> None:
    if args.object_type == "literature":
        objects = [obj for obj in all_objects() if obj.type == "literature"]
    else:
        objects = public_stored_objects(args.object_type)
    if getattr(args, "type", None):
        objects = [obj for obj in objects if str((obj.data or {}).get("type", "")) == args.type]
    if getattr(args, "document_type", None):
        try:
            wanted_type = document_taxonomy.accept_type(args.document_type)
        except document_taxonomy.TaxonomyError as exc:
            fail(str(exc))
        objects = [
            obj for obj in objects
            if document_type(obj.data or {}) == wanted_type
        ]
    if getattr(args, "untyped", False):
        objects = [obj for obj in objects if not document_type(obj.data or {})]
    if args.object_type == "event":
        today = dt.date.today().isoformat()
        if getattr(args, "upcoming", False):
            objects = [
                obj for obj in objects
                if str((obj.data or {}).get("start", ""))[:10]
                and str((obj.data or {}).get("start", ""))[:10] >= today
            ]
        if getattr(args, "past", False):
            objects = [
                obj for obj in objects
                if str((obj.data or {}).get("start", ""))[:10]
                and str((obj.data or {}).get("start", ""))[:10] < today
            ]
        if getattr(args, "year", None):
            objects = [obj for obj in objects if str((obj.data or {}).get("start", "")).startswith(str(args.year))]
        if getattr(args, "date_from", None):
            objects = [obj for obj in objects if str((obj.data or {}).get("start", ""))[:10] >= args.date_from]
        if getattr(args, "date_to", None):
            objects = [obj for obj in objects if str((obj.data or {}).get("start", ""))[:10] <= args.date_to]
    rows = [
        {"ref": obj.ref, "kind": obj.type, "name": obj.title, "status": (obj.data or {}).get("status", "")}
        for obj in objects[: args.limit]
    ]
    _json_or_lines(rows, args.json, [f"{row['ref']}\t{row['name']}\t{row['status']}" for row in rows] or ["none"])


def _show_data(value: str, type_name: str | None) -> dict:
    ref = resolve(value, type_name)
    return public_object_data(ref)


def _show_lines(data: dict) -> list[str]:
    return [
        f"{key}: {', '.join(map(str, value)) if isinstance(value, list) else value}"
        for key, value in data.items()
    ]


def command_edit(args: argparse.Namespace) -> None:
    ref = resolve(_joined(args.object), args.object_type)
    changes: dict = {}
    if ref.type == "document":
        classification = (ref.data or {}).get("classification", {})
        if not isinstance(classification, dict):
            classification = {}
        updated_classification = dict(classification)
        classification_changed = False
        if getattr(args, "document_type", None) is not None:
            try:
                type_id = document_taxonomy.accept_type(args.document_type)
            except document_taxonomy.TaxonomyError as exc:
                fail(str(exc))
            updated_classification["type"] = type_id
            classification_changed = True
        if getattr(args, "document_date", None) is not None:
            date_value = _document_date(args.document_date)
            if date_value:
                updated_classification["date"] = date_value
            else:
                updated_classification.pop("date", None)
            classification_changed = True
        if classification_changed:
            changes["classification"] = updated_classification
    scalar_fields = [
        "status", "preferred_name", "type", "website", "start", "end",
        "timezone", "location", "due", "priority", "description",
    ]
    if getattr(args, "title", None) is not None:
        changes["name"] = args.title
    for field in scalar_fields:
        if field == "type" and ref.type == "document":
            continue  # document --type is classification, handled above
        value = getattr(args, field, None)
        if value is not None:
            changes[field] = value
    for field in ["aliases", "emails", "phones", "tags"]:
        added = getattr(args, f"add_{field}", None)
        removed = getattr(args, f"remove_{field}", None)
        if added:
            changes[f"add_{field}"] = added
        if removed:
            changes[f"remove_{field}"] = removed
    edited = edit_object(ref, changes, args.source or "", args.observed_at or "")
    if edited.type == "document":
        anatomy.rebuild_documents()
    _json_or_lines(
        {"ref": edited.ref, "kind": edited.type, "name": edited.title, "updated": bool(changes)},
        args.json,
        [f"updated: {edited.ref}"],
    )


def command_merge(args: argparse.Namespace) -> None:
    duplicate = resolve(_joined(args.duplicate), args.object_type)
    canonical = resolve(args.into, args.object_type)
    merge_objects(duplicate, canonical, args.dry_run)


def command_document_register(args: argparse.Namespace) -> None:
    interactive = bool(
        getattr(args, "interactive", False)
        or (
            getattr(args, "interactive_add", False)
            and not getattr(args, "non_interactive", False)
            and sys.stdin.isatty()
            and sys.stdout.isatty()
        )
    )
    if not args.file and interactive:
        while not args.file:
            typed = _prompt_value("File")
            if not typed:
                if not sys.stdin.isatty():
                    break
                continue
            candidate = Path(typed).expanduser()
            if candidate.exists() and candidate.is_file():
                args.file = typed
            else:
                print(f"not a file: {candidate}", file=sys.stderr)
    if not args.file:
        fail("file is required: `ws add document <file>`")
    file_path = Path(args.file).expanduser().resolve()
    if not file_path.exists() or not file_path.is_file():
        fail(f"document file does not exist: {file_path}")
    if getattr(args, "add_type", False) and not getattr(args, "type", None):
        fail("--add-type requires --type")
    try:
        if getattr(args, "type", None):
            type_id = document_taxonomy.accept_type(
                args.type,
                prompt_add=interactive,
                add_unknown=getattr(args, "add_type", False),
            )
        elif interactive:
            type_id = document_taxonomy.prompt_type()
        else:
            document_taxonomy.ensure()
            type_id = ""
    except document_taxonomy.TaxonomyError as exc:
        fail(str(exc))
    date_value = getattr(args, "document_date", None)
    if date_value is None and interactive:
        date_value = _prompt_document_date()
    else:
        date_value = _document_date(date_value)
    mode = getattr(args, "mode", "move")
    if mode in {"copy", "move"}:
        destination_dir = paths.DOCUMENT_FILES
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / file_path.name
        if destination.exists() and destination.resolve() != file_path:
            # --ensure asks for the existing record when this file is already
            # registered. A destination holding the same bytes is exactly that
            # case, so adopt it and let the ensure lookup dedupe by path. A
            # different file sharing the name is a real collision either way.
            # The comparison is transient and nothing is stored; see
            # contracts/documents.md on duplicate detection.
            if getattr(args, "ensure", False) and filecmp.cmp(
                file_path, destination, shallow=False
            ):
                file_path = destination.resolve()
            else:
                fail(f"document destination exists: {destination}")
        if destination.resolve() != file_path:
            if mode == "copy":
                shutil.copy2(file_path, destination)
            else:
                shutil.move(str(file_path), destination)
            file_path = destination.resolve()
    try:
        stored_path = str(file_path.relative_to(paths.DOCUMENTS.resolve()))
        path_root = "documents"
    except ValueError:
        stored_path = str(file_path)
        path_root = "external"
    classification = {}
    if type_id:
        classification["type"] = type_id
    if date_value:
        classification["date"] = date_value
    values = {
        "path": stored_path,
        "path_root": path_root,
        "classification": classification,
        "aliases": args.alias or [],
        "tags": args.tag or [],
        "status": args.status,
        "source": args.source,
        "observed_at": args.observed_at,
    }
    ref, created = create_object("document", args.title or file_path.stem, values, ensure=args.ensure)
    anatomy.rebuild_documents()
    _json_or_lines(
        {"ref": ref.ref, "kind": ref.type, "name": ref.title, "created": created},
        args.json,
        [ref.ref],
    )


def command_document_views_rebuild(args: argparse.Namespace) -> None:
    result = anatomy.rebuild_documents()
    _json_or_lines(
        result,
        args.json,
        [
            f"documents: {result['documents']}",
            f"links: {result['links']}",
            f"missing files: {result['missing']}",
        ],
    )


def command_id_resolve(args: argparse.Namespace) -> None:
    ref = resolve(args.query, args.type)
    value = {"ref": ref.ref, "kind": ref.type, "name": ref.title}
    _json_or_lines(value, args.json, [ref.ref])


def command_id_show(args: argparse.Namespace) -> None:
    ref = resolve(args.object)
    value = {
        "ref": ref.ref,
        "kind": ref.type,
        "name": ref.title,
        "aliases": list(ref.aliases),
        "path": str(ref.path) if ref.path else "",
    }
    _json_or_lines(
        value,
        args.json,
        [f"{key}: {', '.join(item) if isinstance(item, list) else item}" for key, item in value.items()],
    )


def _values_from_args(args: argparse.Namespace) -> dict:
    values: dict = {
        "aliases": getattr(args, "alias", None) or [],
        "status": getattr(args, "status", None) or "",
        "description": getattr(args, "description", None) or "",
        "source": getattr(args, "source", None) or "",
        "observed_at": getattr(args, "observed_at", None) or "",
    }
    mapping = {
        "preferred_name": "preferred_name",
        "email": "emails",
        "phone": "phones",
        "type": "type",
        "website": "website",
        "start": "start",
        "end": "end",
        "timezone": "timezone",
        "location": "location",
        "due": "due",
        "priority": "priority",
    }
    for source, target in mapping.items():
        value = getattr(args, source, None)
        if value not in (None, "", []):
            values[target] = value
    # Used solely for idempotent person matching.
    emails = values.get("emails", [])
    if emails:
        values["email"] = emails[0]
    return values


def _common_create(parser: argparse.ArgumentParser, type_name: str) -> None:
    parser.set_defaults(object_type=type_name)
    if type_name in {"person", "organisation"}:
        # Stored uniformly as the object's title; surfaced as the natural word.
        parser.add_argument(
            "title", nargs="*", metavar="NAME",
            help=f"the {type_name}'s name; omitted on a terminal, the wizard asks for it",
        )
    else:
        parser.add_argument("title", nargs="*")
    if type_name in {"person", "organisation", "event", "task"}:
        parser.add_argument("--interactive", action="store_true", help="force the guided prompts")
        parser.add_argument("--non-interactive", action="store_true", help="never prompt")
    parser.add_argument("--alias", action="append")
    parser.add_argument("--description")
    parser.add_argument("--status")
    parser.add_argument("--source")
    parser.add_argument("--observed-at")
    parser.add_argument("--json", action="store_true")
    if type_name == "person":
        parser.add_argument("--preferred-name")
        parser.add_argument("--email", action="append")
        parser.add_argument("--phone", action="append")
    elif type_name == "organisation":
        parser.add_argument("--type")
        parser.add_argument("--website")
    elif type_name == "event":
        parser.add_argument("--start")
        parser.add_argument("--end")
        parser.add_argument("--timezone")
        parser.add_argument("--location")
        parser.add_argument("--type")
    elif type_name == "task":
        parser.add_argument("--due")
        parser.add_argument("--priority")


def _document_type_hint() -> str:
    """The document type vocabulary for help strings; empty when unreadable."""
    try:
        return ", ".join(document_taxonomy.type_ids())
    except Exception:
        return ""


def _list_arguments(listing: argparse.ArgumentParser, type_name: str) -> None:
    """One kind's list filter set: only the kind's own fields, plus plumbing.

    Graph questions live elsewhere (`ws show relations of REF`, `ws relations`,
    the by-* trees) -- list never filters through the relation store.
    """
    if type_name == "organisation":
        listing.add_argument("--type", help="only this organisation type")
    elif type_name == "event":
        listing.add_argument("--type", help="only this event type")
        listing.add_argument("--upcoming", action="store_true", help="only events from today on")
        listing.add_argument("--past", action="store_true", help="only events before today")
        listing.add_argument("--from", dest="date_from", help="only events on or after YYYY-MM-DD")
        listing.add_argument("--to", dest="date_to", help="only events on or before YYYY-MM-DD")
        listing.add_argument("--year", type=int, help="only events in this year")
    elif type_name == "document":
        listing.add_argument("--type", dest="document_type", help="only this document type")
        listing.add_argument("--untyped", action="store_true", help="only documents without a type")
    listing.add_argument("--limit", type=int, default=100, help="show at most this many rows (default 100)")
    listing.add_argument("--json", action="store_true", help="print rows as JSON")


def _edit_arguments(edit: argparse.ArgumentParser, type_name: str) -> None:
    """One kind's edit flag set; shared by the domain parsers and `ws edit`."""
    edit.add_argument("--name", dest="title", help="rename the object")
    if type_name == "document":
        types_hint = _document_type_hint()
        edit.add_argument(
            "--type",
            dest="document_type",
            help=(
                f"one of: {types_hint} (extend with `ws documents types add`)"
                if types_hint
                else "document type from the taxonomy"
            ),
        )
        edit.add_argument(
            "--date",
            dest="document_date",
            help="document date as YYYY-MM-DD; pass an empty value to clear it",
        )
    else:
        edit.add_argument("--description")
    edit.add_argument("--status")
    edit.add_argument("--add-alias", dest="add_aliases", action="append")
    edit.add_argument("--remove-alias", dest="remove_aliases", action="append")
    if type_name == "document":
        edit.add_argument("--add-tag", dest="add_tags", action="append")
        edit.add_argument("--remove-tag", dest="remove_tags", action="append")
    elif type_name == "person":
        edit.add_argument("--preferred-name")
        edit.add_argument("--add-email", dest="add_emails", action="append")
        edit.add_argument("--remove-email", dest="remove_emails", action="append")
        edit.add_argument("--add-phone", dest="add_phones", action="append")
        edit.add_argument("--remove-phone", dest="remove_phones", action="append")
    elif type_name == "organisation":
        edit.add_argument("--type")
        edit.add_argument("--website")
    elif type_name == "event":
        edit.add_argument("--start")
        edit.add_argument("--end")
        edit.add_argument("--timezone")
        edit.add_argument("--location")
        edit.add_argument("--type")
    elif type_name == "task":
        edit.add_argument("--due")
        edit.add_argument("--priority")
    edit.add_argument("--source")
    edit.add_argument("--observed-at")
    edit.add_argument("--json", action="store_true")


def add_object_parser(
    sub: argparse._SubParsersAction,
    command: str,
    type_name: str,
    merge: bool = True,
    *,
    help_text: str | None = None,
) -> argparse.ArgumentParser:
    """The domain home of one kind: only its specialists live here.
    The generic tools exist exactly once, verb-first (`ws add person`,
    `ws show REF`, `ws list tasks`, ...)."""
    parser = sub.add_parser(command, help=help_text)
    actions = parser.add_subparsers(dest=f"{command}_command", required=True)
    ensure = actions.add_parser(
        "ensure", help=f"get-or-create one {type_name} idempotently"
    )
    _common_create(ensure, type_name)
    ensure.set_defaults(func=command_ensure)
    if merge:
        merge_parser = actions.add_parser(
            "merge",
            help="fold a duplicate into a canonical object, leaving a redirect",
        )
        merge_parser.set_defaults(func=command_merge, object_type=type_name)
        merge_parser.add_argument("duplicate", metavar="REF", help="duplicate object's canonical REF")
        merge_parser.add_argument("--into", required=True, metavar="REF", help="canonical object's REF")
        merge_parser.add_argument("--dry-run", action="store_true")
    return parser


def _rebuild_views_after_delete(kind: str) -> None:
    if kind == "document":
        anatomy.rebuild_documents()
    elif kind == "resource":
        anatomy.rebuild_resources()
    elif kind == "profile":
        anatomy.rebuild_profile()


TRASH = Path.home() / ".Trash"


def _trash(path: Path) -> str:
    """Move a payload to the Trash (reversible); plain removal if none exists."""
    if TRASH.is_dir():
        destination = TRASH / path.name
        counter = 1
        while destination.exists() or destination.is_symlink():
            destination = TRASH / f"{path.stem}-{counter}{path.suffix}"
            counter += 1
        shutil.move(str(path), str(destination))
        return f"payload to Trash: {destination.name}"
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return "payload removed"


def command_delete(args: argparse.Namespace) -> None:
    """Delete records of any stored kind; their relations go with them.

    Deletion means deletion: a document's managed file and a resource's
    folder go to the Trash (recoverable), the record and its edges are
    removed. Projects and literature have no delete -- lifecycle status and
    manual curation govern those.
    """
    from ws_lib import relations

    kind = args.object_type
    refs = [resolve(value, kind) for value in args.objects]
    deleted = False
    for ref in refs:
        data = ref.data or {}
        managed_file = None
        if kind == "document":
            stored = str(data.get("path", "") or "")
            if stored and data.get("path_root") == "documents":
                candidate = paths.DOCUMENTS / stored
                if candidate.exists():
                    managed_file = candidate
        folder = ref.path.parent if kind == "resource" and ref.path is not None else None
        edges = [
            row
            for row in relations.load_all()
            if row.get("subject") == ref.id or row.get("object") == ref.id
        ]
        if args.dry_run:
            payload = ""
            if managed_file is not None:
                payload = f", file to Trash: {managed_file.name}"
            elif folder is not None:
                payload = ", folder to Trash"
            print(f"would delete: {ref.ref} ({len(edges)} relation(s){payload})")
            continue
        for row in edges:
            relations.remove(row)
        notes = []
        if folder is not None:
            # The record travels inside the folder -- one recoverable unit.
            notes.append(_trash(folder))
        else:
            if managed_file is not None:
                notes.append(_trash(managed_file))
            if ref.path is not None:
                ref.path.unlink()
        deleted = True
        suffix = f"; {'; '.join(notes)}" if notes else ""
        print(f"deleted: {ref.ref} ({len(edges)} relation(s) removed{suffix})")
    if deleted:
        _rebuild_views_after_delete(kind)


def command_delete_any(args: argparse.Namespace) -> None:
    """Top-level delete: the REF carries its kind, so no domain prefix is needed."""
    groups: dict[str, list[str]] = {}
    for value in args.objects:
        kind = value.split(":", 1)[0] if ":" in value else ""
        if kind in ("project", "literature"):
            fail(
                f"{kind} has no delete: a project retires through its lifecycle "
                "status, a literature item by hand"
            )
        if kind not in SPECS:
            known = ", ".join(sorted(SPECS))
            fail(f"expected a full REF (kind:key) of a deletable kind ({known}), got '{value}'")
        groups.setdefault(kind, []).append(value)
    for kind, values in groups.items():
        command_delete(argparse.Namespace(
            object_type=kind, objects=values, dry_run=args.dry_run,
        ))


def _document_add_arguments(register: argparse.ArgumentParser) -> None:
    """The document ingest flag set; shared by `ws documents add` and `ws add document`."""
    register.add_argument(
        "file", nargs="?", help="path to the file; omitted on a terminal, the wizard asks for it"
    )
    register.add_argument("--name", dest="title", help="document name; defaults to a title derived from the file name")
    types_hint = _document_type_hint()
    register.add_argument(
        "--type",
        help=(
            f"one of: {types_hint}; --add-type adds an unknown type"
            if types_hint
            else "document type from the taxonomy"
        ),
    )
    register.add_argument(
        "--date",
        dest="document_date",
        help="document date as YYYY-MM-DD; year and month views are derived",
    )
    interaction = register.add_mutually_exclusive_group()
    interaction.add_argument(
        "--interactive", action="store_true", help="force the guided type prompt"
    )
    interaction.add_argument(
        "--non-interactive", action="store_true", help="never prompt"
    )
    register.add_argument(
        "--add-type",
        action="store_true",
        help="add an unknown --type to the document taxonomy",
    )
    register.add_argument("--alias", action="append")
    register.add_argument("--tag", action="append")
    register.add_argument("--status", default="active")
    register.add_argument("--source")
    register.add_argument("--observed-at")
    register.add_argument("--ensure", action="store_true")
    register.add_argument(
        "--mode",
        choices=["reference", "copy", "move"],
        default="move",
        metavar="MODE",
        help="move the file into the workspace (default), copy it, or reference it in place",
    )
    register.add_argument("--json", action="store_true")


def extend_create_parser(create_sub: argparse._SubParsersAction) -> None:
    """Hoisted creation: `ws create task|resource ...` mints like the domain verbs."""
    for type_name in ("task", "resource"):
        plural = SPECS[type_name]["plural"]
        kind_parser = create_sub.add_parser(
            type_name, aliases=[plural], help=f"create a {type_name}"
        )
        _common_create(kind_parser, type_name)
        kind_parser.add_argument("--ensure", action="store_true")
        kind_parser.set_defaults(func=command_create)


def expand_add_target(argv: list[str]) -> list[str]:
    """`ws add resource:<key> <path>` is the sentence form of
    `ws add resource resource:<key> <path>`: a REF right after `add` targets
    the existing object it names. Resources are the only kind whose object is
    a container for plain files, so only resource REFs are expanded."""
    if len(argv) >= 2 and argv[0] == "add" and argv[1].startswith("resource:"):
        return [argv[0], "resource", *argv[1:]]
    return argv


def add_add_parser(sub: argparse._SubParsersAction) -> None:
    """Top-level add: ingest something that already exists, kind as first word."""
    from ws_lib import literature, resources

    adder = sub.add_parser(
        "add",
        help="add (ingest) an existing thing: a person, a file, a paper",
        description="Ingest something that already exists; the kind is the first word.",
    )
    kinds = adder.add_subparsers(metavar="KIND", required=True)
    for type_name in ("person", "organisation", "event"):
        plural = SPECS[type_name]["plural"]
        aliases = [plural] + (["organizations"] if type_name == "organisation" else [])
        article = "an" if type_name[0] in "aeiou" else "a"
        kind_parser = kinds.add_parser(type_name, aliases=aliases, help=f"add {article} {type_name}")
        _common_create(kind_parser, type_name)
        kind_parser.add_argument("--ensure", action="store_true")
        kind_parser.set_defaults(func=command_create)
    document_parser = kinds.add_parser(
        "document", aliases=["documents"], help="ingest a file as a document"
    )
    document_parser.set_defaults(func=command_document_register, interactive_add=True)
    _document_add_arguments(document_parser)
    literature.attach_add_parser(kinds, name="literature")
    resource_parser = kinds.add_parser(
        "resource",
        aliases=["resources"],
        help="put a file/folder into an existing resource bundle",
        description="Move or copy a file/folder into an existing resource; "
        "`ws add resource:<key> <path>` is the usual spelling. "
        "New bundles are minted with `ws create resource`.",
    )
    resources.add_arguments(resource_parser)


def add_delete_parser(sub: argparse._SubParsersAction) -> None:
    delete = sub.add_parser(
        "delete",
        help="delete objects by REF; their relations are removed with them",
        description="Delete objects by REF; their relations are removed with them.",
    )
    delete.add_argument(
        "objects",
        nargs="+",
        metavar="REF",
        help="canonical kind:<key> references; the kind is read from the REF",
    )
    delete.add_argument("--dry-run", action="store_true")
    delete.set_defaults(func=command_delete_any)


def command_show_any(args: argparse.Namespace) -> None:
    """Top-level show: the REF carries its kind, so no domain prefix is needed.

    `ws show relations [of] REF` is the sentence form for edges -- the same
    grammar `ws relate A to B as words` established.
    """
    values = list(args.objects)
    if values and values[0] == "relations":
        values = values[1:]
        if values and values[0] == "of":
            values = values[1:]
        if len(values) != 1:
            fail("show relations takes exactly one REF: `ws show relations of <kind>:<key>`")
        from ws_lib import relations

        relations.command_relations_show(argparse.Namespace(
            reference=values[0], relation=args.relation, json=args.json,
        ))
        return
    if args.relation:
        fail("--as filters edges; use it with `ws show relations of <kind>:<key>`")
    known = sorted(set(SPECS) | {"project", "literature"})
    resolved = []
    for value in values:
        kind = value.split(":", 1)[0] if ":" in value else ""
        if kind not in known:
            fail(f"expected a full REF (kind:key) of a known kind ({', '.join(known)}), got '{value}'")
        resolved.append((value, kind))
    if args.json:
        records = [_show_data(value, kind) for value, kind in resolved]
        _json_or_lines(records[0] if len(records) == 1 else records, True, [])
        return
    for index, (value, kind) in enumerate(resolved):
        if index:
            print()
        # Literature and projects carry rich derived views (acquisition
        # status, derived links); the other kinds render their record.
        if kind == "literature":
            literature.command_literature_show(argparse.Namespace(ref=value))
        elif kind == "project":
            project.command_project_show(
                argparse.Namespace(ref=value, projects_dir=None)
            )
        else:
            print("\n".join(_show_lines(_show_data(value, kind))))


def command_edit_any(args: argparse.Namespace) -> None:
    """Top-level edit: read the kind from the REF, then apply that kind's flags."""
    value = args.object
    kind = value.split(":", 1)[0] if ":" in value else ""
    if kind == "project":
        fail("project has no edit: curated by hand through `ws projects` commands")
    if kind not in SPECS and kind != "literature":
        known = ", ".join(sorted(set(SPECS) | {"literature"}))
        fail(f"expected a full REF (kind:key) of an editable kind ({known}), got '{value}'")
    flags = argparse.ArgumentParser(prog=f"ws edit {kind}:<key>", description=f"edit one {kind}")
    if kind == "literature":
        from ws_lib import literature

        literature.literature_edit_arguments(flags)
        namespace = flags.parse_args(args.flags)
        namespace.ref = value
        literature.command_literature_edit(namespace)
        return
    if kind == "profile":
        from ws_lib import career

        career.profile_edit_arguments(flags)
        namespace = flags.parse_args(args.flags)
        namespace.object = value
        career.command_profile_edit(namespace)
        return
    _edit_arguments(flags, kind)
    namespace = flags.parse_args(args.flags)
    namespace.object = value
    namespace.object_type = kind
    command_edit(namespace)


def add_show_parser(sub: argparse._SubParsersAction) -> None:
    show = sub.add_parser(
        "show",
        help="show objects by REF, or `show relations of REF` for edges",
        description="Show objects by REF; `ws show relations of REF` shows edges.",
    )
    show.add_argument(
        "objects",
        nargs="+",
        metavar="REF",
        help="canonical kind:<key> references, or `relations [of] <kind>:<key>`",
    )
    show.add_argument(
        "--as", dest="relation", help="with `relations of`: only edges with this relation word"
    )
    show.add_argument("--json", action="store_true", help="print JSON")
    show.set_defaults(func=command_show_any)


def command_list_overview(args: argparse.Namespace) -> None:
    """Bare `ws list`: object counts per kind across the whole workspace."""
    counts: dict[str, int] = {}
    for obj in all_objects():
        counts[obj.type] = counts.get(obj.type, 0) + 1
    rows = [{"kind": kind, "count": counts[kind]} for kind in sorted(counts)]
    _json_or_lines(
        rows,
        args.json,
        [f"{row['kind']}\t{row['count']}" for row in rows] or ["none"],
    )


def add_list_parser(sub: argparse._SubParsersAction) -> None:
    """Top-level list: the kind is the first word, then that kind's filters."""
    from ws_lib import career, project

    listing = sub.add_parser(
        "list",
        help="list objects of one kind; bare `ws list` counts every kind",
        description="List objects of one kind; bare `ws list` counts every kind.",
    )
    listing.add_argument("--json", action="store_true", help="print counts as JSON")
    listing.set_defaults(func=command_list_overview)
    kinds = listing.add_subparsers(metavar="KIND")
    for type_name in ("person", "organisation", "event", "task", "document", "resource"):
        plural = SPECS[type_name]["plural"]
        aliases = ["organizations"] if type_name == "organisation" else []
        kind_parser = kinds.add_parser(plural, aliases=aliases, help=f"list {plural}")
        kind_parser.set_defaults(func=command_list, object_type=type_name)
        _list_arguments(kind_parser, type_name)
    profile_parser = kinds.add_parser("profile", help="list profile objects")
    career.profile_list_arguments(profile_parser)
    profile_parser.set_defaults(func=career.command_profile_list)
    projects_parser = kinds.add_parser("projects", help="list projects")
    project.project_list_arguments(projects_parser)
    projects_parser.set_defaults(func=project.command_project_list)
    lit_parser = kinds.add_parser("literature", help="list literature items")
    lit_parser.add_argument("--limit", type=int, default=100, help="show at most this many rows (default 100)")
    lit_parser.add_argument("--json", action="store_true", help="print rows as JSON")
    lit_parser.set_defaults(func=command_list, object_type="literature")


def add_edit_parser(sub: argparse._SubParsersAction) -> None:
    edit = sub.add_parser(
        "edit",
        help="edit one object by REF; flags follow the object's kind",
        description="Edit one object by REF; the flags follow the object's kind.",
    )
    edit.add_argument("object", metavar="REF", help="canonical kind:<key> reference")
    edit.add_argument(
        "flags",
        nargs=argparse.REMAINDER,
        metavar="FLAG",
        help="kind-specific flags; `ws edit <kind>:<key> --help` lists them",
    )
    edit.set_defaults(func=command_edit_any)


def add_document_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    """The documents domain home: taxonomy and view specialists only.
    Documents enter through `ws add document` and are read, changed, and
    removed through the universal REF tools."""
    parser = sub.add_parser("documents")
    actions = parser.add_subparsers(dest="document_command", required=True)
    taxonomy_cmd = actions.add_parser(
        "taxonomy",
        help="show the allowed classifier values",
    )
    taxonomy_cmd.set_defaults(func=document_taxonomy.command_taxonomy)
    document_taxonomy.add_parser(actions)
    views = actions.add_parser(
        "views",
        help="manage derived by-type, by-date, and by-organisation views",
    )
    view_actions = views.add_subparsers(
        dest="document_views_command",
        required=True,
    )
    rebuild = view_actions.add_parser("rebuild", help="rebuild the derived by-* browse views from current data")
    rebuild.add_argument("--json", action="store_true")
    rebuild.set_defaults(func=command_document_views_rebuild)
    return parser


def add_id_parser(sub: argparse._SubParsersAction) -> None:
    parser = sub.add_parser("id")
    actions = parser.add_subparsers(dest="id_command", required=True)
    resolve_parser = actions.add_parser("resolve", help="resolve a reference to its internal id")
    resolve_parser.add_argument("query", metavar="REF", help="canonical object reference")
    resolve_parser.add_argument("--type")
    resolve_parser.add_argument("--json", action="store_true")
    resolve_parser.set_defaults(func=command_id_resolve)
    show = actions.add_parser("show", help="show one object's stored identity fields")
    show.add_argument("object", metavar="REF", help="canonical object reference")
    show.add_argument("--json", action="store_true")
    show.set_defaults(func=command_id_show)

