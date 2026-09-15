"""Folder anatomy: one engine for every derived by-* browse tree.

The shape of the trees is data. `~/workspace/folder-anatomy.yaml` (override
with WS_FOLDER_ANATOMY) declares one ring set per domain: the facets that
may become `by-*` rings, plus a depth. The set nests into itself — every
value folder holds the items that reached it plus a `by-*` ring for each
facet not already used along the path, down to `depth` independent hops.
Code carries built-in defaults used when the file (or a domain entry) is
absent.

This module is the whole feature: spec loading and validation, the generic
tree builder, and the per-domain item supply (rebuild_projects,
rebuild_documents, rebuild_literature, rebuild_profile,
rebuild_resources). The anatomy file and this file are the only two places
view structure lives.

A facet is either a CLASSIFIER of the domain's own records (type, field,
status, author, year) or a KIND (organisation, event, person, ...) whose
folders are the names of related objects, resolved through the relations
store. Prefix with `classifier:`/`kind:` only when a name exists on both
sides. Dependent classifiers (`year > month`, `field > subfield`) ride
behind their parent: they appear only beneath a parent value, refine it in
place, and do not count toward depth.

Stability rules implemented here:
- validation happens BEFORE any wipe; a broken file aborts with the
  previous trees intact,
- every by-* directory at a domain root belongs to this engine and is
  wiped on rebuild, so removing a facet from the file removes its tree,
- a domain listed in the file is complete (exactly those rings are built);
  absent domains fall back to the defaults,
- `unclassified/` exists only at the first layer beneath a domain root:
  deeper rings simply omit items that lack the facet, so a ring nobody
  descends into is never created (empty rings prune away).
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ws_lib import paths, records, yamlish


FALLBACK = "unclassified"
DEPTH_DEFAULT = 2
MAX_DEPTH = 3
RESERVED_KEYS = {"rings", "depth"}

MONTHS = (
    "", "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)

# Kind -> canonical id prefix, for matching relation endpoints.
KIND_PREFIXES = {
    "person": "person_",
    "organisation": "org_",
    "event": "event_",
    "task": "task_",
    "document": "doc_",
    "project": "project:",
    "literature": "literature:",
    "profile": "profile_",
    "resource": "resource_",
}

CLASSIFIERS = {
    "projects": ("type", "field", "subfield", "status"),
    "documents": ("type", "year", "month"),
    "literature": ("author", "field", "subfield", "year"),
    "profile": ("type",),
    "resources": (),
}

# Dependent classifier -> the parent value it refines. A dependent never
# heads a ring of its own and never counts toward depth.
DEPENDENTS = {"month": "year", "subfield": "field"}

# Built-in defaults, used when the file or a domain entry is absent. The
# canonical answer is the folder-anatomy file.
DEFAULTS = {
    "projects": {
        "rings": ["type", "organisation", "event", "status", "field > subfield"],
        "depth": 2,
    },
    "documents": {
        "rings": ["type", "organisation", "event", "project", "year > month"],
        "depth": 2,
    },
    "literature": {
        "rings": ["author", "field > subfield", "year", "project"],
        "depth": 2,
    },
    "profile": {
        "rings": ["type", "organisation"],
        "depth": 2,
    },
    "resources": {
        "rings": ["organisation", "project", "event"],
        "depth": 1,
    },
}


class AnatomyError(RuntimeError):
    """A structural problem in folder-anatomy.yaml; nothing was wiped."""


@dataclass
class Item:
    """One object to shelve: identity, link naming, link target, facts."""

    id: str
    link_name: str
    target: Path
    data: dict = field(default_factory=dict)


@dataclass
class Grouping:
    source: str  # "classifier" | "kind"
    word: str


@dataclass
class Facet:
    """One ring: an independent head plus its dependent refinement chain."""

    head: Grouping
    dependents: list[Grouping] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Spec loading and validation


def anatomy_path() -> Path:
    return paths.FOLDER_ANATOMY


def _read_file() -> dict:
    path = anatomy_path()
    if not path.exists():
        return {}
    parsed = yamlish.load_mapping(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise AnatomyError(f"{path}: not a mapping")
    version = parsed.get("schema_version")
    if version != 1:
        raise AnatomyError(f"{path}: schema_version must be 1 (got {version!r})")
    return parsed


def load_spec() -> dict[str, dict]:
    """Merged spec: file domains verbatim, defaults for absent domains."""
    parsed = _read_file()
    spec: dict[str, dict] = {}
    for domain in DEFAULTS:
        value = parsed.get(domain)
        if value is None:
            spec[domain] = DEFAULTS[domain]
        elif isinstance(value, dict):
            spec[domain] = value
        else:
            raise AnatomyError(f"domain '{domain}' must be a mapping with rings/depth")
    unknown = set(parsed) - set(DEFAULTS) - {"schema_version"}
    if unknown:
        raise AnatomyError(
            "unknown domain(s) in folder anatomy: " + ", ".join(sorted(unknown))
        )
    return spec


def resolve_grouping(domain: str, word: str) -> Grouping:
    raw = str(word).strip()
    if raw.startswith("classifier:") or raw.startswith("kind:"):
        source, _, name = raw.partition(":")
        name = name.strip()
        known = (
            name in CLASSIFIERS[domain]
            if source == "classifier"
            else name in KIND_PREFIXES
        )
        if not known:
            raise AnatomyError(f"{domain}: unknown {source} '{name}'")
        return Grouping(source, name)
    is_classifier = raw in CLASSIFIERS[domain]
    is_kind = raw in KIND_PREFIXES
    if is_classifier and is_kind:
        raise AnatomyError(
            f"{domain}: '{raw}' is both a classifier and a kind; "
            f"prefix with classifier:{raw} or kind:{raw}"
        )
    if is_classifier:
        return Grouping("classifier", raw)
    if is_kind:
        return Grouping("kind", raw)
    raise AnatomyError(
        f"{domain}: '{raw}' is neither a classifier of this domain "
        f"({', '.join(CLASSIFIERS[domain]) or 'none'}) nor a kind"
    )


def parse_ring(domain: str, entry: str) -> Facet:
    """Parse one ring declaration: `word` or `parent > dependent [> ...]`."""
    words = [word.strip() for word in str(entry).split(">")]
    if not all(words):
        raise AnatomyError(f"{domain}: malformed ring '{entry}'")
    groupings = [resolve_grouping(domain, word) for word in words]
    head, dependents = groupings[0], groupings[1:]
    if head.source == "classifier" and head.word in DEPENDENTS:
        raise AnatomyError(
            f"{domain}: '{head.word}' refines '{DEPENDENTS[head.word]}' and "
            f"cannot head a ring; declare '{DEPENDENTS[head.word]} > {head.word}'"
        )
    previous = head
    for dependent in dependents:
        required = (
            DEPENDENTS.get(dependent.word)
            if dependent.source == "classifier"
            else None
        )
        if required is None:
            raise AnatomyError(
                f"{domain}: '{dependent.word}' is not a dependent classifier "
                f"({', '.join(sorted(DEPENDENTS))}) and cannot follow '>'"
            )
        if previous.word != required:
            raise AnatomyError(
                f"{domain}: '{dependent.word}' must follow '{required}', "
                f"not '{previous.word}'"
            )
        previous = dependent
    return Facet(head, dependents)


def domain_facets(domain: str, config: dict) -> tuple[list[Facet], int]:
    """Parse and validate one domain entry into facets and a depth."""
    if not isinstance(config, dict):
        raise AnatomyError(f"domain '{domain}' must be a mapping with rings/depth")
    unknown = set(config) - RESERVED_KEYS
    if unknown:
        raise AnatomyError(
            f"{domain}: unknown key(s): " + ", ".join(sorted(unknown))
        )
    rings = config.get("rings")
    if not isinstance(rings, list) or not rings:
        raise AnatomyError(f"{domain}: rings must be a non-empty list of facets")
    facets = [parse_ring(domain, entry) for entry in rings]
    words = [
        grouping.word
        for facet in facets
        for grouping in [facet.head, *facet.dependents]
    ]
    if len(set(words)) != len(words):
        raise AnatomyError(f"{domain}: a facet repeats in the ring set")
    depth = config.get("depth", DEPTH_DEFAULT)
    if isinstance(depth, bool) or not isinstance(depth, int) or not 1 <= depth <= MAX_DEPTH:
        raise AnatomyError(
            f"{domain}: depth must be an integer between 1 and {MAX_DEPTH}"
        )
    return facets, depth


def validate_spec(spec: dict[str, dict]) -> None:
    """Structural validation. Raises AnatomyError; touches nothing on disk."""
    for domain, config in spec.items():
        domain_facets(domain, config)


# ---------------------------------------------------------------------------
# Fact extraction


def _safe_component(value: str) -> str:
    text = re.sub(r"[/\\:\x00]+", "-", str(value).strip())
    text = re.sub(r"\s+", " ", text).strip(" .")
    return text or FALLBACK


def _date_of(data: dict) -> dt.date | None:
    classification = data.get("classification", {})
    raw = str(classification.get("date", "") or "") if isinstance(classification, dict) else ""
    try:
        return dt.date.fromisoformat(raw[:10]) if raw else None
    except ValueError:
        return None


def _classifier_values(domain: str, word: str, item: Item) -> list[str]:
    data = item.data
    if domain == "projects":
        if word == "type":
            value = str(data.get("type", "") or "")
            return [value] if value else []
        if word == "status":
            value = str(data.get("status", "") or "")
            return [value] if value else []
        if word == "field":
            values = data.get("fields") or []
            return [str(v) for v in values if str(v)]
        if word == "subfield":
            values = data.get("subfields") or []
            return [str(v) for v in values if str(v)]
    if domain == "documents":
        if word == "type":
            classification = data.get("classification", {})
            value = ""
            if isinstance(classification, dict):
                value = str(classification.get("type", "") or "")
            value = value or str(data.get("document_type", "") or "")
            return [value] if value else []
        if word == "year":
            date = _date_of(data)
            return [str(date.year)] if date else []
        if word == "month":
            date = _date_of(data)
            return [f"{date.month:02d}-{MONTHS[date.month]}"] if date else []
    if domain == "literature":
        if word == "author":
            return [str(value) for value in data.get("authors") or [] if str(value)]
        if word == "field":
            values = data.get("fields") or []
            return [str(v) for v in values if str(v)]
        if word == "subfield":
            values = data.get("subfields") or []
            return [str(v) for v in values if str(v)]
        if word == "year":
            value = str(data.get("year", "") or "")
            return [value] if value else []
    if domain == "profile" and word == "type":
        value = str(data.get("type", "") or "")
        return [value] if value else []
    return []


def _load_edges() -> list[tuple[str, str]]:
    # Lazy import: relations -> catalog -> anatomy would cycle at module
    # import time.
    from ws_lib import relations

    if not relations.RELATIONS.exists():
        return []
    pairs = []
    for path in sorted(relations.RELATIONS.glob("*.yaml")):
        row = records.load_record(path)
        subject = str(row.get("subject", "") or "")
        object_id = str(row.get("object", "") or "")
        if subject and object_id:
            pairs.append((subject, object_id))
    return pairs


def _kind_titles(kind: str) -> dict[str, str]:
    """id -> display name for one kind, read from the canonical stores."""
    from ws_lib import catalog

    titles: dict[str, str] = {}
    spec = catalog.SPECS.get(kind)
    if spec:
        store = Path(spec["dir"])
        pattern = "*/resource.yaml" if kind == "resource" else "*.yaml"
        if store.exists():
            for path in sorted(store.glob(pattern)):
                data = records.load_record(path)
                object_id = str(data.get("id", "") or "")
                if object_id:
                    # Records write `name:`; `title:` covers pre-rename records.
                    titles[object_id] = str(
                        data.get("name") or data.get("title") or object_id
                    )
        return titles
    if kind == "project":
        from ws_lib import project

        for name in project.existing_project_names():
            meta = project.parse_project_yaml(project.PROJECTS / name / "project.yaml")
            titles[f"project:{name}"] = str(meta.get("title") or name)
        return titles
    if kind == "literature":
        from ws_lib import literature

        for bib in literature.list_item_bibtex_files():
            key = bib.parent.name
            titles[f"literature:{key}"] = key
        return titles
    return titles


class _KindResolver:
    """Related-object names per item, loading edges and titles once."""

    def __init__(self) -> None:
        self._edges: list[tuple[str, str]] | None = None
        self._titles: dict[str, dict[str, str]] = {}

    def names(self, item_id: str, kind: str) -> list[str]:
        if self._edges is None:
            self._edges = _load_edges()
        if not self._edges:
            return []
        prefix = KIND_PREFIXES[kind]
        related: set[str] = set()
        for subject, object_id in self._edges:
            if subject == item_id and object_id.startswith(prefix):
                related.add(object_id)
            elif object_id == item_id and subject.startswith(prefix):
                related.add(subject)
        if not related:
            return []
        if kind not in self._titles:
            self._titles[kind] = _kind_titles(kind)
        return sorted(self._titles[kind].get(other, other) for other in related)


# ---------------------------------------------------------------------------
# Tree building


def _wipe_by_dirs(domain_root: Path) -> None:
    if not domain_root.exists():
        return
    for child in sorted(domain_root.iterdir()):
        if not child.name.startswith("by-"):
            continue
        if child.is_symlink() or not child.is_dir():
            raise RuntimeError(f"derived view root is not a directory: {child}")
        shutil.rmtree(child)


def _link(
    directory: Path, item: Item, collision: str
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / item.link_name
    if destination.exists() or destination.is_symlink():
        if collision == "id":
            source = Path(item.link_name)
            destination = directory / f"{source.stem}--{item.id}{source.suffix}"
        else:
            suffix = 2
            while destination.exists() or destination.is_symlink():
                destination = directory / f"{item.link_name}-{suffix}"
                suffix += 1
    relative = os.path.relpath(item.target.resolve(), directory.resolve())
    destination.symlink_to(relative)


def _values_for(
    domain: str,
    grouping: Grouping,
    item: Item,
    kinds: _KindResolver,
    parent: tuple[Grouping, str] | None = None,
) -> list[str]:
    if grouping.source == "classifier":
        values = _classifier_values(domain, grouping.word, item)
        if (
            domain in {"projects", "literature"}
            and grouping.word == "subfield"
            and parent is not None
            and parent[0].source == "classifier"
            and parent[0].word == "field"
        ):
            from ws_lib import project

            allowed = set(project.subfield_map().get(parent[1], []))
            values = [value for value in values if value in allowed]
    else:
        values = kinds.names(item.id, grouping.word)
    return [_safe_component(value) for value in values if str(value).strip()]


def rebuild_domain(
    domain: str,
    domain_root: Path,
    items: list[Item],
    collision: str = "suffix",
) -> dict[str, int]:
    """Validate the spec, wipe every by-* dir at domain_root, build anew."""
    spec = load_spec()
    validate_spec(spec)
    facets, depth = domain_facets(domain, spec[domain])
    _wipe_by_dirs(domain_root)
    kinds = _KindResolver()
    counts: dict[str, int] = {}

    def emit_chain(
        item: Item,
        value_dir: Path,
        chain: list[Grouping],
        parent: tuple[Grouping, str],
    ) -> int:
        # Dependent refinements under one value: by-month beneath a year,
        # by-subfield beneath a field. Free of the depth count; no fallback.
        if not chain:
            return 0
        dependent = chain[0]
        made = 0
        for value in _values_for(domain, dependent, item, kinds, parent=parent):
            target_dir = value_dir / f"by-{dependent.word}" / value
            _link(target_dir, item, collision)
            made += 1 + emit_chain(item, target_dir, chain[1:], (dependent, value))
        return made

    def emit_ring(
        item: Item,
        base: Path,
        facet: Facet,
        used: frozenset[str],
        hops_left: int,
        root_layer: bool,
    ) -> int:
        head = facet.head
        values = _values_for(domain, head, item, kinds)
        if root_layer and not values:
            values = [FALLBACK]
        made = 0
        for value in values:
            value_dir = base / f"by-{head.word}" / value
            _link(value_dir, item, collision)
            made += 1
            if value == FALLBACK:
                continue
            made += emit_chain(item, value_dir, facet.dependents, (head, value))
            if hops_left > 1:
                for other in facets:
                    if other.head.word == head.word or other.head.word in used:
                        continue
                    made += emit_ring(
                        item,
                        value_dir,
                        other,
                        used | {head.word},
                        hops_left - 1,
                        False,
                    )
        return made

    for facet in facets:
        tree = f"by-{facet.head.word}"
        counts[tree] = 0
        for item in items:
            counts[tree] += emit_ring(
                item, domain_root, facet, frozenset(), depth, True
            )
    return counts


# ---------------------------------------------------------------------------
# Per-domain item supply and public rebuild entry points

PROJECTS_DOMAIN = paths.PROJECTS_DOMAIN


def _project_items() -> list[Item]:
    from ws_lib import project

    items: list[Item] = []
    for name in project.existing_project_names():
        meta = project.parse_project_yaml(project.PROJECTS / name / "project.yaml")
        items.append(
            Item(
                id=f"project:{name}",
                link_name=name.rsplit("/", 1)[-1],
                target=project.PROJECTS / name,
                data=meta,
            )
        )
    return items


def rebuild_projects() -> dict[str, int]:
    return rebuild_domain("projects", PROJECTS_DOMAIN, _project_items())


def _document_source(data: dict) -> Path | None:
    value = str(data.get("path", "") or "")
    if not value:
        return None
    if data.get("path_root") == "documents":
        return paths.DOCUMENTS / value
    return Path(value).expanduser()


def _document_items() -> tuple[list[Item], int]:
    items: list[Item] = []
    missing = 0
    if paths.DOCUMENT_OBJECTS.exists():
        for record_path in sorted(paths.DOCUMENT_OBJECTS.glob("*.yaml")):
            data = records.load_record(record_path)
            # Records write `kind:`; `type:` is accepted for pre-rename records.
            if (data.get("kind") or data.get("type")) != "document":
                continue
            if data.get("status", "active") != "active":
                continue
            source = _document_source(data)
            if source is None or not source.is_file():
                missing += 1
                continue
            items.append(
                Item(
                    id=str(data.get("id", "") or record_path.stem),
                    link_name=source.name,
                    target=source,
                    data=data,
                )
            )
    return items, missing


def rebuild_documents() -> dict[str, int]:
    items, missing = _document_items()
    counts = rebuild_domain("documents", paths.DOCUMENTS, items, collision="id")
    return {
        "documents": len(items),
        "links": sum(counts.values()),
        "missing": missing,
    }


def _literature_items() -> list[Item]:
    from ws_lib import literature

    items: list[Item] = []
    for bib_path in literature.list_item_bibtex_files():
        folder = bib_path.parent
        key = folder.name
        bibtex = literature.read(bib_path)
        items.append(
            Item(
                id=f"literature:{key}",
                link_name=key,
                target=folder,
                data={
                    "authors": literature.bibtex_authors(bibtex),
                    "fields": literature.info_fields(folder),
                    "subfields": literature.info_subfields(folder),
                    "year": literature.bibtex_field(bibtex, "year"),
                },
            )
        )
    return items


def rebuild_literature() -> dict[str, int]:
    from ws_lib import literature

    return rebuild_domain("literature", literature.LITERATURE, _literature_items())


def _profile_items() -> list[Item]:
    from ws_lib import catalog

    return [
        Item(
            id=ref.id,
            link_name=f"{_safe_component(ref.title)}.yaml",
            target=ref.path,
            data=ref.data or {},
        )
        for ref in catalog.stored_objects("profile")
        if ref.path is not None
        and str((ref.data or {}).get("status", "") or "active") != "merged"
    ]


def rebuild_profile() -> dict[str, int]:
    return rebuild_domain("profile", paths.CAREER, _profile_items(), collision="id")


def _resource_items() -> list[Item]:
    items: list[Item] = []
    if paths.RESOURCE_ITEMS.exists():
        for record_path in sorted(paths.RESOURCE_ITEMS.glob("*/resource.yaml")):
            data = records.load_record(record_path)
            folder = record_path.parent
            items.append(
                Item(
                    id=str(data.get("id", "") or f"resource_{folder.name}"),
                    link_name=folder.name,
                    target=folder,
                    data=data,
                )
            )
    return items


def rebuild_resources() -> dict[str, int]:
    return rebuild_domain("resources", paths.RESOURCES, _resource_items())


# ---------------------------------------------------------------------------
# Check integration


def findings() -> list[dict]:
    try:
        spec = load_spec()
        validate_spec(spec)
    except AnatomyError as exc:
        return [{"severity": "error", "message": str(exc)}]
    return []
