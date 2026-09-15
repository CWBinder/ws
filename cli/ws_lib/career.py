"""First-class profile objects and comprehensive CV generation."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from ws_lib import (
    anatomy,
    catalog,
    literature,
    paths,
    profile_taxonomy,
    records,
    yamlish,
)


fail = literature.fail
rel_home = literature.rel_home

CAREER = paths.CAREER
ITEMS = paths.PROFILE_ITEMS
APPLICATIONS = paths.PROFILE_APPLICATIONS
TAXONOMY = paths.PROFILE_TAXONOMY
CAREER_CONTRACT_DOC = paths.CONTRACTS / "career.md"

SECTION_TITLES = {
    "education": "Education",
    "work-experience": "Work Experience",
    "publication": "Publications",
    "talk": "Talks & Conference Contributions",
    "teaching": "Teaching",
    "award": "Awards & Honors",
    "skill": "Skills",
    "volunteering": "Volunteering",
}

README = """# Profile

Canonical career material is stored as one first-class object per YAML file in
`items/`. `profile-taxonomy.yaml` defines the allowed object types and their
default CV section order. `by-type/` is a disposable generated view.

`applications/` is deliberately unstructured. Put job descriptions, notes,
generated CVs, letters, and supporting material directly wherever useful.

```bash
ws profile create "University education" --type education
ws profile list --type education
ws profile make-cv --out applications/example
ws profile make-cv --spec applications/example/cv-spec.yaml --out applications/example
```

`make-cv` writes both editable `cv.tex` and compiled `cv.pdf` by default. A
spec selects and orders profile objects and supplies application-specific
headline and summary text without changing canonical profile facts.
"""

GITIGNORE = """.DS_Store

# Generated browse views
by-*/

# Generated LaTeX build artifacts
out/
*.aux
*.bbl
*.bcf
*.blg
*.fdb_latexmk
*.fls
*.log
*.out
*.run.xml
*.synctex.gz
"""

VSCODE_SETTINGS = """{
  "latex-workshop.latex.outDir": "%DIR%/out",
  "latex-workshop.latex.autoBuild.run": "onSave"
}
"""


def write_if_missing(path: Path, content: str) -> None:
    if path.exists():
        print(f"ok: {rel_home(path)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"created: {rel_home(path)}")


def ensure_dir(path: Path) -> None:
    if path.is_dir():
        print(f"ok: {rel_home(path)}/")
        return
    path.mkdir(parents=True, exist_ok=True)
    print(f"created: {rel_home(path)}/")


def git_init_local() -> None:
    git_dir = CAREER / ".git"
    if git_dir.exists():
        print(f"ok: {rel_home(git_dir)}")
        return
    subprocess.run(["git", "init", "-q", "-b", "main", str(CAREER)], check=True)
    print(f"created: {rel_home(git_dir)} (local, no remote)")


def command_career_init(_args: argparse.Namespace) -> None:
    ensure_dir(CAREER)
    ensure_dir(ITEMS)
    ensure_dir(APPLICATIONS)
    created_taxonomy = not TAXONOMY.exists()
    profile_taxonomy.ensure()
    print(f"{'created' if created_taxonomy else 'ok'}: {rel_home(TAXONOMY)}")
    ensure_dir(CAREER / ".vscode")
    write_if_missing(CAREER / ".vscode" / "settings.json", VSCODE_SETTINGS)
    write_if_missing(CAREER / "README.md", README)
    write_if_missing(CAREER / ".gitignore", GITIGNORE)
    git_init_local()


def _joined(value: str | list[str]) -> str:
    return " ".join(value) if isinstance(value, list) else value


def _list(value) -> list[str]:
    return [str(item) for item in (value or []) if str(item).strip()]


def _profile_type(value: str) -> str:
    try:
        return profile_taxonomy.accept_type(value)
    except profile_taxonomy.TaxonomyError as exc:
        fail(str(exc))
    raise AssertionError("unreachable")


def _identity_objects(exclude: str = "") -> list[catalog.ObjectRef]:
    return [
        ref for ref in catalog.stored_objects("profile")
        if ref.id != exclude
        and str((ref.data or {}).get("type", "")) == "identity"
        and str((ref.data or {}).get("status", "") or "active") != "merged"
    ]


def _create_values(args: argparse.Namespace, type_id: str) -> dict:
    values = {
        "type": type_id,
        "aliases": args.alias or [],
        "description": args.description or "",
        "bullets": args.bullet or [],
        "status": args.status or "",
        "source": args.source or "",
        "observed_at": args.observed_at or "",
    }
    for field in (
        "subtitle", "start", "end", "year", "location", "headline",
        "qualification_status", "post_nominals", "date_of_birth", "orcid",
        "author", "venue", "doi", "isbn",
    ):
        value = getattr(args, field, None)
        if value not in (None, ""):
            values[field] = value
    for source, target in (
        ("email", "emails"),
        ("phone", "phones"),
        ("address", "address"),
        ("link", "links"),
    ):
        value = getattr(args, source, None)
        if value:
            values[target] = value
    return values


def command_profile_create(args: argparse.Namespace) -> None:
    if not _joined(args.name).strip():
        if not getattr(args, "json", False) and sys.stdin.isatty() and sys.stdout.isatty():
            typed = ""
            while not typed:
                try:
                    typed = input("Name: ").strip()
                except EOFError:
                    break
            args.name = [typed] if typed else []
        if not _joined(args.name).strip():
            fail("name is required")
    if not args.type:
        if not getattr(args, "json", False) and sys.stdin.isatty() and sys.stdout.isatty():
            values = profile_taxonomy.type_ids()
            typed = ""
            while not typed:
                try:
                    typed = input(f"Type ({', '.join(values)}): ").strip()
                except EOFError:
                    break
            args.type = typed
        if not args.type:
            fail("--type is required; `ws profile taxonomy` lists the values")
    type_id = _profile_type(args.type)
    if type_id == "identity":
        identities = _identity_objects()
        wanted = _joined(args.name).strip().casefold()
        idempotent_match = bool(
            args.ensure
            and len(identities) == 1
            and wanted in {
                identities[0].title.casefold(),
                *(alias.casefold() for alias in identities[0].aliases),
            }
        )
        if identities and not idempotent_match:
            fail("profile already has an active identity object")
    ref, created = catalog.create_object(
        "profile",
        _joined(args.name),
        _create_values(args, type_id),
        ensure=args.ensure,
    )
    anatomy.rebuild_profile()
    value = {"ref": ref.ref, "kind": "profile", "type": type_id, "name": ref.title}
    if args.json:
        print(json.dumps({**value, "created": created}, indent=2))
    else:
        print(f"{'created' if created else 'exists'}: {ref.ref}")


def command_profile_list(args: argparse.Namespace) -> None:
    refs = catalog.public_stored_objects("profile")
    if args.type:
        type_id = _profile_type(args.type)
        refs = [ref for ref in refs if str((ref.data or {}).get("type", "")) == type_id]
    rows = [
        {
            "ref": ref.ref,
            "type": str((ref.data or {}).get("type", "")),
            "name": ref.title,
            "status": str((ref.data or {}).get("status", "")),
        }
        for ref in refs[: args.limit]
    ]
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            print(f"{row['ref']}\t{row['type']}\t{row['name']}")
        if not rows:
            print("none")


def command_profile_edit(args: argparse.Namespace) -> None:
    ref = catalog.resolve(_joined(args.object), "profile")
    changes: dict = {}
    if args.name is not None:
        changes["name"] = args.name
    if args.type is not None:
        type_id = _profile_type(args.type)
        if type_id == "identity" and _identity_objects(exclude=ref.id):
            fail("profile already has an active identity object")
        changes["type"] = type_id
    for field in (
        "description", "status", "subtitle", "start", "end", "year",
        "location", "headline", "qualification_status", "post_nominals",
        "date_of_birth", "orcid", "author", "venue", "doi", "isbn",
    ):
        value = getattr(args, field, None)
        if value is not None:
            changes[field] = value
    for target in (
        "aliases", "bullets", "emails", "phones", "address", "links",
    ):
        added = getattr(args, f"add_{target}", None)
        removed = getattr(args, f"remove_{target}", None)
        if added:
            changes[f"add_{target}"] = added
        if removed:
            changes[f"remove_{target}"] = removed
    edited = catalog.edit_object(
        ref, changes, args.source or "", args.observed_at or ""
    )
    anatomy.rebuild_profile()
    if args.json:
        print(json.dumps(catalog.public_object_data(edited), indent=2, ensure_ascii=False))
    else:
        print(f"updated: {edited.ref}")


def command_profile_views_rebuild(args: argparse.Namespace) -> None:
    counts = anatomy.rebuild_profile()
    if args.json:
        print(json.dumps({"root": str(CAREER), "links": counts}, indent=2))
    else:
        print(f"rebuilt: {rel_home(CAREER)}/by-*")
        for name, count in sorted(counts.items()):
            print(f"  {name}: {count} links")


def findings() -> list[dict]:
    results = profile_taxonomy.findings()
    results.extend(catalog.findings({"profile"}))
    legacy = [path for path in (CAREER / "profile", CAREER / "cv") if path.exists()]
    for path in legacy:
        results.append({
            "severity": "warning",
            "message": f"legacy profile path remains: {path}",
        })
    return results


# ---------------------------------------------------------------------------
# LaTeX rendering

_TEX_REPL = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&",
    "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "~": r"\nobreakspace{}", "^": r"\textasciicircum{}",
}


def tex(value) -> str:
    return "".join(_TEX_REPL.get(char, char) for char in str(value))


def breakable(value: str) -> str:
    value = re.sub(r"([/._:+-])", r"\1\\allowbreak{}", value)
    return re.sub(r"(\d{4})(?=\d)", r"\1\\allowbreak{}", value)


def itemize(items: list[str]) -> list[str]:
    values = [item for item in items if item]
    if not values:
        return []
    return [r"\begin{itemize}"] + [r"\item " + item for item in values] + [r"\end{itemize}"]


_MONTHS = (
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)


def display_date(value: object) -> str:
    text_value = str(value or "").strip()
    if not text_value or text_value.casefold() == "present":
        return text_value
    match = re.fullmatch(r"(\d{4})-(\d{2})(?:-(\d{2}))?", text_value)
    if not match:
        return text_value
    year, month, day = match.groups()
    month_number = int(month)
    if not 1 <= month_number <= 12:
        return text_value
    if day:
        return f"{int(day)} {_MONTHS[month_number]} {year}"
    return f"{_MONTHS[month_number]} {year}"


def date_range(data: dict) -> str:
    start = display_date(data.get("start", ""))
    end = display_date(data.get("end", ""))
    year = display_date(data.get("year", ""))
    if start and end:
        return start if start == end else f"{start}--{end}"
    if start:
        return f"{start}--"
    return end or year


def format_authors(author_field: str) -> str:
    output = []
    for name in re.split(r"\s+and\s+", author_field.strip()):
        if not name.strip():
            continue
        canonical = literature.canonical_author_name(name)
        parts = canonical.split()
        if len(parts) > 1:
            initials = " ".join(f"{part[0]}." for part in parts[:-1] if part)
            output.append(f"{initials} {parts[-1]}")
        else:
            output.append(canonical)
    return ", ".join(output)


def _bib_entry(bibtex: str) -> dict:
    get = lambda field: literature.bibtex_field(bibtex, field)
    return {
        "author": get("author"),
        "title": get("title"),
        "year": get("year"),
        "journal": get("journal") or get("booktitle"),
        "publisher": get("publisher"),
        "doi": get("doi"),
        "isbn": get("isbn"),
    }


def _plain_bib_text(value: object) -> str:
    """Normalize escaped HTML occasionally returned by citation providers."""
    return re.sub(r"<[^>]+>", "", html.unescape(str(value or "")))


def format_publication(entry: dict) -> str:
    parts = []
    if entry.get("author"):
        parts.append(tex(format_authors(_plain_bib_text(entry["author"]))))
    if entry.get("title"):
        parts.append(f"\\textit{{{tex(_plain_bib_text(entry['title']))}}}")
    venue = _plain_bib_text(entry.get("journal") or entry.get("publisher") or "")
    year = str(entry.get("year") or "")
    if year:
        venue = f"{venue} ({year})" if venue else f"({year})"
    if venue:
        parts.append(tex(venue))
    line = ", ".join(parts) + "."
    if entry.get("doi"):
        doi = str(entry["doi"]).lower()
        line += f" \\href{{https://doi.org/{doi}}}{{{breakable(tex(doi))}}}."
    elif entry.get("isbn"):
        line += f" ISBN~{breakable(tex(str(entry['isbn'])))}."
    return line


def _related(ref: catalog.ObjectRef) -> list[tuple[str, catalog.ObjectRef]]:
    from ws_lib import relations

    output = []
    for row in relations.for_object(ref.id):
        other_id = str(
            row.get("object") if row.get("subject") == ref.id else row.get("subject")
        )
        other = catalog.get(other_id)
        if other:
            output.append((str(row.get("relation", "related")), other))
    return output


def _active_profile_objects() -> list[catalog.ObjectRef]:
    return [
        ref for ref in catalog.stored_objects("profile")
        if str((ref.data or {}).get("status", "") or "active") != "merged"
    ]


def load_profile() -> dict:
    refs = _active_profile_objects()
    identities = [
        ref for ref in refs if str((ref.data or {}).get("type", "")) == "identity"
    ]
    by_type: dict[str, list[catalog.ObjectRef]] = {}
    for ref in refs:
        by_type.setdefault(str((ref.data or {}).get("type", "")), []).append(ref)
    return {
        "identity": dict(identities[0].data or {}) if identities else {},
        "identity_ref": identities[0] if identities else None,
        "objects": refs,
        "by_type": by_type,
    }


CV_SPEC_TOP_LEVEL_FIELDS = {
    "schema_version", "variant", "headline", "summary", "sections",
}
CV_SPEC_SECTION_FIELDS = {"type", "title", "items"}
CV_SPEC_ITEM_FIELDS = {
    "ref", "name", "subtitle", "description", "bullets", "start", "end",
    "year", "location", "qualification_status",
}
CV_SPEC_TEXT_OVERRIDES = CV_SPEC_ITEM_FIELDS - {"ref", "bullets"}


def _cv_spec_fail(path: Path, message: str) -> None:
    fail(f"invalid CV spec {rel_home(path)}: {message}")


def load_cv_spec(path: Path) -> dict:
    if not path.is_file():
        fail(f"CV spec not found: {rel_home(path)}")
    try:
        spec = yamlish.load_mapping(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        _cv_spec_fail(path, str(exc))
    if not spec:
        _cv_spec_fail(path, "file is empty")
    unexpected = sorted(set(spec) - CV_SPEC_TOP_LEVEL_FIELDS)
    if unexpected:
        _cv_spec_fail(path, f"unknown top-level field(s): {', '.join(unexpected)}")
    if spec.get("schema_version") != 1:
        _cv_spec_fail(path, "schema_version must be 1")
    for field in ("variant", "headline", "summary"):
        if field in spec and not isinstance(spec[field], str):
            _cv_spec_fail(path, f"{field} must be text")
    if "sections" in spec and not isinstance(spec["sections"], list):
        _cv_spec_fail(path, "sections must be a list")
    return spec


def _spec_item_ref(item: object, path: Path, section_number: int, item_number: int) -> tuple[str, dict]:
    location = f"sections[{section_number}].items[{item_number}]"
    if isinstance(item, str):
        return item, {"ref": item}
    if not isinstance(item, dict):
        _cv_spec_fail(path, f"{location} must be a profile REF or mapping")
    unexpected = sorted(set(item) - CV_SPEC_ITEM_FIELDS)
    if unexpected:
        _cv_spec_fail(path, f"{location} has unknown field(s): {', '.join(unexpected)}")
    ref_value = item.get("ref")
    if not isinstance(ref_value, str) or not ref_value.startswith("profile:"):
        _cv_spec_fail(path, f"{location}.ref must be a full profile:<key> REF")
    for field in CV_SPEC_TEXT_OVERRIDES:
        if field in item and not isinstance(item[field], str):
            _cv_spec_fail(path, f"{location}.{field} must be text")
    if "bullets" in item and not isinstance(item["bullets"], list):
        _cv_spec_fail(path, f"{location}.bullets must be a list")
    return ref_value, item


def _tailored_ref(ref: catalog.ObjectRef, item: dict) -> catalog.ObjectRef:
    data = dict(ref.data or {})
    for field in CV_SPEC_TEXT_OVERRIDES:
        if field in item:
            data[field] = item[field]
    if "bullets" in item:
        data["bullets"] = [str(value) for value in item["bullets"]]
    title = str(item.get("name", ref.title))
    if "name" in item:
        data["name"] = title
    return catalog.ObjectRef(
        id=ref.id,
        type=ref.type,
        title=title,
        path=ref.path,
        aliases=ref.aliases,
        data=data,
        key=ref.key,
    )


def apply_cv_spec(profile: dict, spec: dict, path: Path) -> dict:
    tailored = dict(profile)
    identity = dict(profile.get("identity", {}))
    if "headline" in spec:
        identity["headline"] = spec["headline"]
    if "summary" in spec:
        identity["description"] = spec["summary"]
    tailored["identity"] = identity
    if "sections" not in spec:
        return tailored

    active = {ref.ref: ref for ref in profile.get("objects", [])}
    selected: set[str] = set()
    sections = []
    for section_number, section in enumerate(spec["sections"], start=1):
        if not isinstance(section, dict):
            _cv_spec_fail(path, f"sections[{section_number}] must be a mapping")
        unexpected = sorted(set(section) - CV_SPEC_SECTION_FIELDS)
        if unexpected:
            _cv_spec_fail(path, f"sections[{section_number}] has unknown field(s): {', '.join(unexpected)}")
        type_value = section.get("type")
        if not isinstance(type_value, str):
            _cv_spec_fail(path, f"sections[{section_number}].type must be text")
        try:
            type_id = profile_taxonomy.accept_type(type_value)
        except profile_taxonomy.TaxonomyError as exc:
            _cv_spec_fail(path, f"sections[{section_number}].type: {exc}")
        if type_id == "identity":
            _cv_spec_fail(path, f"sections[{section_number}] cannot select identity; use headline and summary")
        title = section.get("title", SECTION_TITLES.get(type_id, type_id.replace("-", " ").title()))
        if not isinstance(title, str):
            _cv_spec_fail(path, f"sections[{section_number}].title must be text")
        items = section.get("items")
        if not isinstance(items, list):
            _cv_spec_fail(path, f"sections[{section_number}].items must be a list")
        refs = []
        for item_number, item in enumerate(items, start=1):
            ref_value, item_data = _spec_item_ref(item, path, section_number, item_number)
            if ref_value in selected:
                _cv_spec_fail(path, f"profile REF appears more than once: {ref_value}")
            ref = active.get(ref_value)
            if ref is None:
                _cv_spec_fail(path, f"unknown or inactive profile REF: {ref_value}")
            actual_type = str((ref.data or {}).get("type", ""))
            if actual_type != type_id:
                _cv_spec_fail(
                    path,
                    f"{ref_value} has type {actual_type}, not section type {type_id}",
                )
            refs.append(_tailored_ref(ref, item_data))
            selected.add(ref_value)
        sections.append({"type": type_id, "title": title, "refs": refs})
    tailored["sections"] = sections
    return tailored


def publication_literature_keys(profile: dict | None = None) -> list[str]:
    data = profile or load_profile()
    keys = []
    for ref in data.get("by_type", {}).get("publication", []):
        for relation, other in _related(ref):
            if other.type == "literature" and relation == "represents":
                keys.append(other.id.split(":", 1)[1])
    return list(dict.fromkeys(keys))


def _entry_sort(ref: catalog.ObjectRef) -> tuple:
    data = ref.data or {}
    date = str(data.get("end") or data.get("start") or data.get("year") or "")
    present = date.casefold() == "present"
    return (present, date, ref.title.casefold())


def _entry_lines(ref: catalog.ObjectRef) -> list[str]:
    data = ref.data or {}
    related = [other.title for _relation, other in _related(ref) if other.type != "literature"]
    education = data.get("type") == "education"
    raw_metadata = [
        str(data.get("subtitle", "") or ""),
        *related,
        str(data.get("location", "") or ""),
    ]
    if not education:
        raw_metadata.append(str(data.get("qualification_status", "") or ""))
    title_key = ref.title.casefold()
    metadata = []
    for value in raw_metadata:
        normalized = value.casefold()
        if not value or normalized in title_key:
            continue
        if any(
            normalized == existing.casefold()
            or normalized in existing.casefold()
            for existing in metadata
        ):
            continue
        metadata.append(value)
    right = date_range(data)
    heading = f"\\textbf{{{tex(ref.title)}}}"
    if right:
        heading += f"\\fillrule\\textbf{{{tex(right)}}}"
    lines = [r"\needspace{5\baselineskip}", heading + r"\par"]
    if metadata:
        lines.append(tex(" · ".join(metadata)) + r"\par")
    if education and data.get("qualification_status"):
        lines.append(
            r"{\small\itshape " + tex(data["qualification_status"]) + r"}\par"
        )
    if data.get("description") and not education:
        lines.append(tex(data["description"]) + r"\par")
    detail_lines = []
    if education:
        if data.get("description"):
            detail_lines.append(str(data["description"]))
    detail_lines += _list(data.get("bullets"))
    lines += itemize([tex(value) for value in detail_lines])
    lines += [r"\vspace{4pt}", ""]
    return lines


def _publication_lines(refs: list[catalog.ObjectRef]) -> list[str]:
    if not refs:
        return []
    lines = [r"\begin{enumerate}[leftmargin=2.2em,label={\arabic*.}]"]
    for ref in refs:
        data = ref.data or {}
        entry = None
        for relation, other in _related(ref):
            if relation == "represents" and other.type == "literature" and other.path:
                entry = _bib_entry(literature.read(other.path))
                break
        if entry is None:
            entry = {
                "author": data.get("author", ""),
                "title": ref.title,
                "year": data.get("year", ""),
                "journal": data.get("venue", ""),
                "publisher": "",
                "doi": data.get("doi", ""),
                "isbn": data.get("isbn", ""),
            }
        lines.append(r"\item " + format_publication(entry))
        if data.get("description"):
            lines.append(tex(data["description"]) + r"\par")
        lines += itemize([tex(value) for value in _list(data.get("bullets"))])
    lines.append(r"\end{enumerate}")
    return lines


def _section(title: str, body: list[str]) -> list[str]:
    if not body:
        return []
    return [r"\needspace{4\baselineskip}", f"\\section*{{{tex(title)}}}"] + body + [""]


def _render_header(identity: dict, opts: dict) -> list[str]:
    name = tex(identity.get("name", ""))
    post = tex(identity.get("post_nominals", ""))
    title = f"{{\\huge\\bfseries\\sffamily\\color{{accent}} {name}}}"
    if opts["post_nominals"] and post:
        title += f"\\, {{\\normalsize {post}}}"
    lines = [r"\begin{center}", title, r"\\[2pt]"]
    if identity.get("headline"):
        lines += [f"{{\\sffamily\\color{{accent}} {tex(identity['headline'])}}}", r"\\[5pt]"]
    contact = []
    addresses = _list(identity.get("address"))
    if addresses:
        contact.append(tex(addresses[0]))
    emails = _list(identity.get("emails"))
    if emails:
        contact.append(f"\\href{{mailto:{emails[0]}}}{{{tex(emails[0])}}}")
    contact += [tex(value) for value in _list(identity.get("phones"))[:1]]
    if identity.get("orcid"):
        orcid = str(identity["orcid"])
        contact.append(f"ORCID:~\\href{{https://orcid.org/{orcid}}}{{{tex(orcid)}}}")
    if opts["dob"] and identity.get("date_of_birth"):
        contact.append("b.~" + tex(identity["date_of_birth"]))
    if contact:
        lines += ["{\\small " + r" \textbullet{} ".join(contact) + "}", ""]
    lines.append(r"\end{center}")
    if identity.get("description"):
        lines += [r"\vspace{5pt}", tex(identity["description"]) + r"\par", ""]
    lines += itemize([tex(value) for value in _list(identity.get("bullets"))])
    return lines


PREAMBLE = r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{lmodern}
\input{glyphtounicode}\pdfgentounicode=1
\usepackage[margin=1.8cm]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{ragged2e}
\usepackage{needspace}
\usepackage{xcolor}
\definecolor{accent}{HTML}{1F4E79}
\usepackage[hidelinks]{hyperref}
\newcommand{\fillrule}{\leavevmode\nobreak\hspace{8pt}{\color{accent!45}\leaders\hrule height 2.6pt depth -2.2pt\hfill}\hspace{8pt}\nobreak}
\setlist[itemize]{leftmargin=1.2em,itemsep=1pt,topsep=2pt,parsep=0pt}
\setlist[enumerate]{leftmargin=2em,itemsep=1.5pt,topsep=2pt,parsep=0pt}
\titleformat{\section}{\large\bfseries\sffamily\color{accent}}{}{0pt}{}[{\color{accent}\titlerule[0.8pt]}]
\titlespacing*{\section}{0pt}{11pt}{4pt}
\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}
\setlength{\emergencystretch}{3em}
\pagestyle{empty}
"""


def build_cv(profile: dict, opts: dict) -> str:
    body = [r"\RaggedRight"]
    body += _render_header(profile.get("identity", {}), opts)
    if "sections" in profile:
        sections = profile["sections"]
    else:
        by_type = profile.get("by_type", {})
        sections = [
            {
                "type": type_id,
                "title": SECTION_TITLES.get(type_id, type_id.replace("-", " ").title()),
                "refs": sorted(by_type.get(type_id, []), key=_entry_sort, reverse=True),
            }
            for type_id in profile_taxonomy.type_ids()
            if type_id != "identity"
        ]
    for section in sections:
        type_id = section["type"]
        refs = section["refs"]
        if type_id == "publication":
            rendered = _publication_lines(refs)
        else:
            rendered = []
            for ref in refs:
                rendered += _entry_lines(ref)
        body += _section(section["title"], rendered)
    return PREAMBLE + "\n\\begin{document}\n" + "\n".join(body) + "\n\\end{document}\n"


VARIANTS = {"classic": build_cv}


def command_career_make_cv(args: argparse.Namespace) -> None:
    if not ITEMS.exists():
        fail("profile not initialized; run `ws profile init`")
    spec_path = Path(args.spec).expanduser() if args.spec else None
    spec = load_cv_spec(spec_path) if spec_path else {}
    variant = args.variant or spec.get("variant") or "classic"
    builder = VARIANTS.get(variant)
    if not builder:
        fail(f"unknown variant: {variant}; choose from {', '.join(VARIANTS)}")
    profile = load_profile()
    if not profile.get("identity"):
        fail("profile has no identity object; create one with `ws profile create --type identity`")
    if spec_path:
        profile = apply_cv_spec(profile, spec, spec_path)
    out_dir = Path(args.out).expanduser() if args.out else Path.cwd()
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{args.name}.tex"
    pdf_target = target.with_suffix(".pdf")
    outputs = [target] if args.no_build else [target, pdf_target]
    existing = [path for path in outputs if path.exists()]
    if existing and not args.force:
        rendered = ", ".join(rel_home(path) for path in existing)
        fail(f"exists: {rendered}; pass --force to overwrite")
    options = {
        "dob": not args.no_dob,
        "post_nominals": not args.no_post_nominals,
    }
    target.write_text(builder(profile, options), encoding="utf-8")
    source = f"selected by {rel_home(spec_path)}" if spec_path else "all active profile objects"
    print(f"wrote: {rel_home(target)} ({source})")
    if not args.no_build:
        build_pdf(target)


def build_pdf(tex_path: Path) -> Path:
    latexmk = shutil.which("latexmk")
    if not latexmk:
        fail(
            "latexmk not found; install MacTeX/TeX Live, "
            "or pass --no-build to write TeX only"
        )
    result = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-outdir=out", tex_path.name],
        cwd=tex_path.parent,
    )
    if result.returncode != 0:
        fail("latexmk build failed; see output above")
    built = tex_path.parent / "out" / f"{tex_path.stem}.pdf"
    if not built.is_file():
        fail(f"latexmk succeeded but did not create {rel_home(built)}")
    target = tex_path.with_suffix(".pdf")
    shutil.copy2(built, target)
    print(f"built: {rel_home(target)}")
    return target


def _common_profile_fields(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--description")
    parser.add_argument("--subtitle", help="secondary line, e.g. the institution or employer")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--year")
    parser.add_argument("--location")
    parser.add_argument(
        "--qualification-status",
        dest="qualification_status",
        help="education completion note, e.g. programme not completed",
    )
    parser.add_argument("--headline", help="one-line professional summary (identity objects)")
    parser.add_argument("--post-nominals", dest="post_nominals", help="letters after the name, e.g. MSc")
    parser.add_argument("--date-of-birth", dest="date_of_birth", help="date of birth (ISO); omitted from a CV with --no-dob")
    parser.add_argument("--orcid")
    parser.add_argument("--author")
    parser.add_argument("--venue")
    parser.add_argument("--doi")
    parser.add_argument("--isbn")


def _profile_type_hint() -> str:
    """The profile type vocabulary for help strings; empty when unreadable."""
    try:
        return ", ".join(profile_taxonomy.type_ids())
    except Exception:
        return ""


def attach_create_parser(sub: argparse._SubParsersAction, name: str = "create") -> argparse.ArgumentParser:
    """The profile create parser; serves `ws profile create` and `ws create profile`."""
    create = sub.add_parser(name, help="create a profile object")
    create.add_argument(
        "name", nargs="*", help="omitted on a terminal, the wizard asks for it"
    )
    types_hint = _profile_type_hint()
    create.add_argument(
        "--type",
        help=(
            f"one of: {types_hint} (extend with `ws profile add-type`); "
            "omitted on a terminal, the wizard asks for it"
            if types_hint
            else "profile type; omitted on a terminal, the wizard asks for it"
        ),
    )
    create.add_argument("--alias", action="append")
    create.add_argument("--bullet", action="append", help="achievement line for the CV; repeatable")
    create.add_argument("--email", action="append")
    create.add_argument("--phone", action="append")
    create.add_argument("--address", action="append", help="postal address; repeatable")
    create.add_argument("--link", action="append", help="profile or project URL; repeatable")
    create.add_argument("--status")
    create.add_argument("--source")
    create.add_argument("--observed-at")
    create.add_argument("--ensure", action="store_true")
    create.add_argument("--json", action="store_true")
    _common_profile_fields(create)
    create.set_defaults(func=command_profile_create)
    return create


def profile_list_arguments(listing: argparse.ArgumentParser) -> None:
    """The profile list filter set; shared by the domain parser and `ws list`."""
    listing.add_argument("--type", help="only this profile type")
    listing.add_argument("--limit", type=int, default=100, help="show at most this many rows (default 100)")
    listing.add_argument("--json", action="store_true", help="print rows as JSON")


def profile_edit_arguments(edit: argparse.ArgumentParser) -> None:
    """The profile edit flag set; shared by the domain parser and `ws edit`."""
    edit.add_argument("--name")
    types_hint = _profile_type_hint()
    edit.add_argument(
        "--type",
        help=f"one of: {types_hint} (extend with `ws profile add-type`)" if types_hint else None,
    )
    edit.add_argument("--status")
    edit.add_argument("--add-alias", dest="add_aliases", action="append")
    edit.add_argument("--remove-alias", dest="remove_aliases", action="append")
    edit.add_argument("--add-bullet", dest="add_bullets", action="append")
    edit.add_argument("--remove-bullet", dest="remove_bullets", action="append")
    edit.add_argument("--add-email", dest="add_emails", action="append")
    edit.add_argument("--remove-email", dest="remove_emails", action="append")
    edit.add_argument("--add-phone", dest="add_phones", action="append")
    edit.add_argument("--remove-phone", dest="remove_phones", action="append")
    edit.add_argument("--add-address", dest="add_address", action="append")
    edit.add_argument("--remove-address", dest="remove_address", action="append")
    edit.add_argument("--add-link", dest="add_links", action="append")
    edit.add_argument("--remove-link", dest="remove_links", action="append")
    edit.add_argument("--source")
    edit.add_argument("--observed-at")
    edit.add_argument("--json", action="store_true")
    _common_profile_fields(edit)


def add_parser(sub: argparse._SubParsersAction, command_name: str = "career") -> None:
    parser = sub.add_parser(
        command_name,
        description="Manage first-class profile objects and generate comprehensive CVs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""Structure:
  {rel_home(ITEMS)}/<profile-id>.yaml     canonical profile objects
  {rel_home(TAXONOMY)}                    allowed types and CV order
  {rel_home(APPLICATIONS)}/               deliberately unstructured
  {rel_home(CAREER)}/by-type/             disposable derived view
""",
    )
    actions = parser.add_subparsers(dest="profile_command", required=True)

    init = actions.add_parser("init", help="initialize the profile object store")
    init.set_defaults(func=command_career_init)

    taxonomy_cmd = actions.add_parser("taxonomy", help="show profile types")
    taxonomy_cmd.set_defaults(func=profile_taxonomy.command_taxonomy)
    add_type = actions.add_parser("add-type", help="extend profile types")
    add_type.add_argument("value")
    add_type.set_defaults(func=profile_taxonomy.command_add_type)

    views = actions.add_parser("views", help="manage the derived by-type view")
    views_actions = views.add_subparsers(dest="profile_views_command", required=True)
    rebuild = views_actions.add_parser("rebuild", help="rebuild the derived by-* browse views from current data")
    rebuild.add_argument("--json", action="store_true")
    rebuild.set_defaults(func=command_profile_views_rebuild)

    make_cv = actions.add_parser(
        "make-cv",
        help="generate a comprehensive or spec-tailored editable CV from profile objects",
    )
    make_cv.add_argument(
        "--spec",
        metavar="FILE",
        help="YAML file selecting and tailoring profile objects for this CV",
    )
    make_cv.add_argument(
        "--variant",
        choices=sorted(VARIANTS),
        help="CV layout to render (default: spec value or classic)",
    )
    make_cv.add_argument("--out", help="target directory; default: current directory")
    make_cv.add_argument("--name", default="cv", metavar="NAME", help="output file name without extension (default cv)")
    build_mode = make_cv.add_mutually_exclusive_group()
    build_mode.add_argument("--build", action="store_true", help=argparse.SUPPRESS)
    build_mode.add_argument(
        "--no-build",
        action="store_true",
        help="write cv.tex only instead of also compiling cv.pdf",
    )
    make_cv.add_argument("--no-dob", action="store_true", help="leave the date of birth off the CV")
    make_cv.add_argument("--no-post-nominals", action="store_true", help="leave post-nominal letters off the CV")
    make_cv.add_argument("--no-refresh-pubs", action="store_true", help=argparse.SUPPRESS)
    make_cv.add_argument("--force", action="store_true")
    make_cv.set_defaults(func=command_career_make_cv)
