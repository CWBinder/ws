import argparse
import datetime as dt
import gzip
import json
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from ws_lib import paths, yamlish

LITERATURE = paths.LITERATURE
LITERATURE_ITEMS = paths.LITERATURE_ITEMS
SYSTEM = paths.SYSTEM
CONTRACTS = paths.CONTRACTS
LIBRARY_CONTRACT_DOC = CONTRACTS / "library.md"

CONTACT_EMAIL = paths.CONTACT_EMAIL or "workspace-tools@localhost"
USER_AGENT = f"ws-literature/1.0 (mailto:{CONTACT_EMAIL})"

REFERENCES_FILENAME = "references.txt"
SEMANTIC_SCHOLAR_REFERENCES_URL = (
    "https://api.semanticscholar.org/graph/v1/paper/{paper}/references"
    "?fields=externalIds,title&limit=1000"
)
OPENALEX_WORK_URL = (
    "https://api.openalex.org/works/{paper}"
    "?select=id,referenced_works_count,referenced_works"
)
OPENALEX_WORKS_URL = "https://api.openalex.org/works"

ITEM_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$")
LITERATURE_TYPES = ["article", "book", "inproceedings", "misc", "phdthesis", "mastersthesis", "unpublished"]
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
BIB_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,", re.S)
ARXIV_ID_PATTERN = r"(?:\d{4}\.\d{4,5}|[A-Za-z-]+(?:\.[A-Za-z-]+)?/\d{7})(?:v\d+)?"
ARXIV_ID_RE = re.compile(rf"^{ARXIV_ID_PATTERN}$", re.I)
ARXIV_DOI_RE = re.compile(rf"arxiv[.:/]({ARXIV_ID_PATTERN})", re.I)
ISBN_RE = re.compile(r"^(?:\d{9}[\dX]|\d{13})$")
STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "of",
    "on",
    "the",
    "to",
    "using",
    "with",
}


def today() -> str:
    return dt.date.today().isoformat()


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def rel_home(path: Path) -> str:
    try:
        return "~/" + str(path.resolve().relative_to(Path.home()))
    except ValueError:
        return str(path)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        print()
        return default
    return value or default


def ask_choice(prompt: str, options: list[str], default: str) -> str:
    print(f"{prompt} options: {', '.join(options)}")
    return ask(prompt, default)


def literature_required_dirs() -> list[Path]:
    return [LITERATURE_ITEMS]


def ensure_literature_dirs() -> None:
    for path in literature_required_dirs():
        path.mkdir(parents=True, exist_ok=True)


def item_path(key: str) -> Path:
    if not ITEM_KEY_RE.match(key):
        fail("item key must start with a letter or number and contain only letters, numbers, dot, underscore, colon, or hyphen")
    return LITERATURE_ITEMS / key


def item_from_ref(value: str) -> Path:
    """Resolve a canonical `literature:<key>` REF to its item directory."""
    from ws_lib import catalog

    ref = catalog.resolve(value, "literature")
    if ref.path is None:
        fail(f"literature item has no canonical path: {value}")
    return ref.path.parent


def command_ref(args: argparse.Namespace) -> str:
    """Return a CLI REF; accept legacy test/internal Namespaces with `key`."""
    value = getattr(args, "ref", None)
    if value:
        return value
    key = getattr(args, "key", None)
    if key:
        return f"literature:{key}"
    fail("literature REF is required")


def normalize_doi(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^https?://(dx\.)?doi\.org/", "", value, flags=re.I)
    value = re.sub(r"^doi:\s*", "", value, flags=re.I)
    return urllib.parse.unquote(value).strip().rstrip(".").lower()


def is_arxiv_doi(value: str) -> bool:
    return bool(ARXIV_DOI_RE.search(normalize_doi(value)))


def normalize_isbn(value: str) -> str:
    return re.sub(r"[^0-9Xx]", "", value).upper()


def bibtex_escape(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def bibtex_field(bibtex: str, field: str) -> str:
    pattern = re.compile(r"(?is)(^|[,\n])\s*" + re.escape(field) + r"\s*=")
    match = pattern.search(bibtex)
    if not match:
        return ""
    index = match.end()
    while index < len(bibtex) and bibtex[index].isspace():
        index += 1
    if index >= len(bibtex):
        return ""
    opener = bibtex[index]
    if opener == "{":
        index += 1
        start = index
        depth = 1
        while index < len(bibtex):
            if bibtex[index] == "{":
                depth += 1
            elif bibtex[index] == "}":
                depth -= 1
                if depth == 0:
                    return bibtex[start:index].strip()
            index += 1
        return bibtex[start:].strip()
    if opener == '"':
        index += 1
        start = index
        while index < len(bibtex):
            if bibtex[index] == '"' and bibtex[index - 1] != "\\":
                return bibtex[start:index].strip()
            index += 1
        return bibtex[start:].strip()
    start = index
    while index < len(bibtex) and bibtex[index] not in ",\n":
        index += 1
    return bibtex[start:index].strip()


def bibtex_key(bibtex: str) -> str:
    match = BIB_ENTRY_RE.search(bibtex)
    return match.group(1).strip() if match else ""


def bibtex_doi(bibtex: str) -> str:
    field = bibtex_field(bibtex, "doi")
    if field:
        return normalize_doi(field)
    match = DOI_RE.search(bibtex)
    return normalize_doi(match.group(0)) if match else ""


def bibtex_keywords(bibtex: str) -> list[str]:
    keywords = bibtex_field(bibtex, "keywords")
    if not keywords:
        primary_class = bibtex_field(bibtex, "primaryClass")
        return [primary_class] if primary_class else []
    return [item.strip() for item in re.split(r"[,;]", keywords) if item.strip()]


def _split_bibtex_authors(value: str) -> list[str]:
    """Split a BibTeX author list on top-level ``and`` separators."""
    authors: list[str] = []
    start = 0
    depth = 0
    index = 0
    while index < len(value):
        char = value[index]
        if char == "{":
            depth += 1
        elif char == "}" and depth:
            depth -= 1
        elif depth == 0 and value[index:index + 5].lower() == " and ":
            authors.append(value[start:index].strip())
            index += 5
            start = index
            continue
        index += 1
    authors.append(value[start:].strip())
    return [author for author in authors if author]


def canonical_author_name(value: str) -> str:
    """Return a stable display form for one common BibTeX name spelling."""
    name = re.sub(r"\s+", " ", value.strip()).strip("{} ")
    parts = [part.strip() for part in name.split(",")]
    if len(parts) == 2 and all(parts):
        name = f"{parts[1]} {parts[0]}"
    elif len(parts) == 3 and all(parts):
        name = f"{parts[2]} {parts[0]}, {parts[1]}"
    words = re.sub(r"\s+", " ", name).strip().split()
    if len(words) > 2:
        # Middle initials vary frequently between citation providers and
        # should not split one author across several derived folders. Keep
        # full middle names and surname particles such as "van" or "von".
        words = [words[0]] + [
            word for word in words[1:-1] if not re.fullmatch(r"[A-Za-z]\.?", word)
        ] + [words[-1]]
    return " ".join(words)


def bibtex_authors(bibtex: str) -> list[str]:
    """All authors in citation order, normalized for derived browse views."""
    value = bibtex_field(bibtex, "author")
    return [canonical_author_name(author) for author in _split_bibtex_authors(value)]


def _author_tokens(value: str) -> list[str]:
    plain = unicodedata.normalize("NFKD", canonical_author_name(value))
    plain = plain.encode("ascii", "ignore").decode("ascii").lower()
    return re.findall(r"[a-z0-9]+", plain)


def author_matches(author: str, selector: str) -> bool:
    """Match an author alias, tolerating omitted middle names or initials."""
    left = _author_tokens(author)
    right = _author_tokens(selector)
    if not left or not right:
        return False
    if left == right:
        return True
    first_matches = (
        left[0] == right[0]
        or (len(left[0]) == 1 and right[0].startswith(left[0]))
        or (len(right[0]) == 1 and left[0].startswith(right[0]))
    )
    return left[-1] == right[-1] and first_matches


def item_keys_by_author(selectors: list[str]) -> list[str]:
    """Return canonical item keys authored by any configured name/alias."""
    names = [name for name in selectors if str(name).strip()]
    if not names:
        return []
    keys: list[str] = []
    for bib_path in list_item_bibtex_files():
        authors = bibtex_authors(read(bib_path))
        if any(author_matches(author, name) for author in authors for name in names):
            keys.append(bib_path.parent.name)
    return keys


def write_bibliography(keys: list[str], output: Path) -> None:
    """Write canonical citations for a selected set of library item keys."""
    chunks: list[str] = []
    for key in keys:
        bib_path = item_path(key) / "citation.bib"
        if not bib_path.exists():
            fail(f"missing literature item citation: {key}")
        chunks.append(read(bib_path).strip())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "\n\n".join(chunks).rstrip() + ("\n" if chunks else ""),
        encoding="utf-8",
    )


def yaml_quote(value: str) -> str:
    if re.match(r"^[A-Za-z0-9][A-Za-z0-9 ._:/+-]*$", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def default_info_yaml(bibtex: str) -> str:
    lines = ["schema_version: 1", "keywords:"]
    keywords = bibtex_keywords(bibtex)
    if keywords:
        lines.extend(f"  - {yaml_quote(keyword)}" for keyword in keywords)
    else:
        lines.append("  []")
    lines.extend(["fields: []", "subfields: []", 'summary: ""', 'notes: ""'])
    return "\n".join(lines) + "\n"


def write_info_if_missing(root: Path, bibtex: str) -> None:
    path = root / "info.yaml"
    if not path.exists():
        path.write_text(default_info_yaml(bibtex), encoding="utf-8")


def load_taxonomy() -> dict:
    """Shared broad fields and field-specific subfields."""
    from ws_lib import project

    data = project.load_taxonomy()
    return {
        "fields": data.get("fields", []),
        "subfields": project.subfield_map(data),
    }


def add_taxonomy_value(key: str, value: str) -> None:
    if key != "fields":
        fail("use fields or add a field-specific subfield")
    from ws_lib import project

    project.add_taxonomy_value("fields", value)


def add_subfield(field: str, value: str) -> None:
    from ws_lib import project

    project.add_subfield(field, value)


def update_info_classifiers(
    root: Path,
    fields: list[str],
    subfields: list[str] | None = None,
) -> None:
    """Set classifier blocks in info.yaml while preserving all other text."""
    path = root / "info.yaml"
    if subfields is None:
        subfields = info_subfields(root)
    lines = read(path).splitlines() if path.exists() else ["schema_version: 1"]
    kept: list[str] = []
    in_classifier_block = False
    for line in lines:
        if in_classifier_block:
            if line.strip().startswith("- "):
                continue
            in_classifier_block = False
        if line.startswith("fields:") or line.startswith("subfields:"):
            in_classifier_block = True
            continue
        kept.append(line)
    block: list[str] = []
    for key, values in (("fields", fields), ("subfields", subfields)):
        if values:
            block.append(f"{key}:")
            block.extend(f"  - {yaml_quote(value)}" for value in values)
        else:
            block.append(f"{key}: []")
    insert_at = next(
        (index for index, line in enumerate(kept) if line.startswith("summary:")),
        len(kept),
    )
    new_lines = kept[:insert_at] + block + kept[insert_at:]
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def info_fields(root: Path) -> list[str]:
    path = root / "info.yaml"
    if not path.exists():
        return []
    values = yamlish.load_mapping(read(path)).get("fields")
    return [str(value) for value in values] if isinstance(values, list) else []


def info_subfields(root: Path) -> list[str]:
    path = root / "info.yaml"
    if not path.exists():
        return []
    values = yamlish.load_mapping(read(path)).get("subfields")
    return [str(value) for value in values] if isinstance(values, list) else []


def validate_requested_fields(args: argparse.Namespace) -> None:
    """Reject invalid field/subfield combinations before anything is written.

    classify_new_item runs once the item already exists, so failing there
    leaves a created-but-unclassified item behind while still exiting
    non-zero. Only the non-interactive path is checked here: on a terminal
    the wizard offers to extend the vocabulary instead."""
    fields = [
        value.strip().lower()
        for value in (getattr(args, "field", None) or [])
        if value.strip()
    ]
    subfields = [
        value.strip().lower()
        for value in (getattr(args, "subfield", None) or [])
        if value.strip()
    ]
    if (not fields and not subfields) or sys.stdin.isatty():
        return
    from ws_lib import project

    problems = project.classification_problems(fields, subfields, load_taxonomy())
    if problems:
        fail("; ".join(problems) + " (extend with `ws literature add-field` / `add-subfield`)")


def classify_new_item(root: Path, args: argparse.Namespace) -> None:
    """Apply or ask for broad fields and field-specific subfields.

    Explicit --field values are validated against the shared vocabulary and
    applied without prompting. With no flags on a terminal, the wizard asks;
    unknown answers offer a taxonomy extension. Non-interactive runs without
    flags leave the item unclassified."""
    from ws_lib import project

    taxonomy_data = load_taxonomy()
    field_options = taxonomy_data["fields"]
    fields = [
        value.strip().lower()
        for value in (getattr(args, "field", None) or [])
        if value.strip()
    ]
    subfields = [
        value.strip().lower()
        for value in (getattr(args, "subfield", None) or [])
        if value.strip()
    ]
    interactive = not fields and not subfields and sys.stdin.isatty()
    unknown = [value for value in fields if value not in field_options]
    if unknown and not sys.stdin.isatty():
        fail(
            f"unknown field(s): {', '.join(unknown)}"
            " (extend with `ws literature add-field`)"
        )
    for value in unknown:
        if ask_yes_no(f"Add '{value}' to the available fields?"):
            add_taxonomy_value("fields", value)
        else:
            fields.remove(value)
    if interactive:
        print(f"Fields options: {', '.join(field_options)}")
        raw = ask("Fields, comma-separated", "")
        for value in [part.strip().lower() for part in raw.split(",") if part.strip()]:
            if value not in field_options:
                if not ask_yes_no(f"Add '{value}' to the available fields?"):
                    continue
                add_taxonomy_value("fields", value)
            fields.append(value)
    fields = list(dict.fromkeys(fields))
    if interactive and fields:
        taxonomy_data = load_taxonomy()
        options = project.compatible_subfields(fields, taxonomy_data)
        if options:
            print(f"Subfields options: {', '.join(options)}")
            raw = ask("Subfields, comma-separated", "")
            subfields.extend(
                part.strip().lower() for part in raw.split(",") if part.strip()
            )
    subfields = list(dict.fromkeys(subfields))
    problems = project.classification_problems(fields, subfields, load_taxonomy())
    if problems:
        fail("; ".join(problems) + " (extend with `ws literature add-field` / `add-subfield`)")
    if not fields and not subfields:
        return
    update_info_classifiers(root, fields, subfields)
    print("classified: fields=" + ", ".join(fields))
    print("classified: subfields=" + (", ".join(subfields) if subfields else "none"))


def list_item_bibtex_files() -> list[Path]:
    if not LITERATURE_ITEMS.exists():
        return []
    return sorted(path for path in LITERATURE_ITEMS.glob("*/citation.bib") if path.is_file())


def classifier_findings() -> list[dict]:
    """Validate stored literature fields and their field-specific subfields."""
    from ws_lib import project

    taxonomy_data = load_taxonomy()
    rows: list[dict] = []
    for bib_path in list_item_bibtex_files():
        root = bib_path.parent
        for problem in project.classification_problems(
            info_fields(root), info_subfields(root), taxonomy_data
        ):
            rows.append({
                "severity": "error",
                "id": root.name,
                "message": problem,
            })
    return rows


def find_item_by_doi(doi: str) -> Optional[Path]:
    normalized = normalize_doi(doi)
    if not normalized:
        return None
    for bib_path in list_item_bibtex_files():
        if bibtex_doi(read(bib_path)) == normalized:
            return bib_path.parent
    if LITERATURE_ITEMS.exists():
        for bib_path in sorted(LITERATURE_ITEMS.glob("*/source/arxiv/citation.bib")):
            if bibtex_doi(read(bib_path)) == normalized:
                return bib_path.parents[2]
    return None


def find_item_by_isbn(isbn: str) -> Optional[Path]:
    normalized = normalize_isbn(isbn)
    if not normalized:
        return None
    for bib_path in list_item_bibtex_files():
        if normalize_isbn(bibtex_field(read(bib_path), "isbn")) == normalized:
            return bib_path.parent
    return None


def ascii_words(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.findall(r"[A-Za-z0-9]+", normalized)


def first_author_token(author: str) -> str:
    if not author:
        return "Item"
    first = author.split(" and ")[0].strip()
    if "," in first:
        candidate = first.split(",", 1)[0].strip()
    else:
        parts = first.split()
        candidate = parts[-1] if parts else first
    words = ascii_words(candidate)
    return words[0].capitalize() if words else "Item"


def short_title_token(title: str) -> str:
    words = [word for word in ascii_words(title) if word.lower() not in STOPWORDS]
    if not words:
        return "Reference"
    return "".join(word.capitalize() for word in words[:3])


def year_from_crossref(message: dict) -> str:
    for key in ["published-print", "published-online", "published", "issued", "created"]:
        parts = message.get(key, {}).get("date-parts")
        if parts and parts[0]:
            return str(parts[0][0])
    return today()[:4]


def crossref_author_string(message: dict) -> str:
    authors = []
    for author in message.get("author", []):
        family = author.get("family", "").strip()
        given = author.get("given", "").strip()
        literal = author.get("name", "").strip()
        if family and given:
            authors.append(f"{family}, {given}")
        elif family:
            authors.append(family)
        elif literal:
            authors.append(literal)
    return " and ".join(authors)


def item_key_from_metadata(message: dict, fallback_bibtex: str = "") -> str:
    title = (message.get("title") or [""])[0]
    author = crossref_author_string(message)
    year = year_from_crossref(message)
    if not title:
        title = bibtex_field(fallback_bibtex, "title")
    if not author:
        author = bibtex_field(fallback_bibtex, "author")
    if not year:
        year = bibtex_field(fallback_bibtex, "year") or today()[:4]
    key = first_author_token(author) + re.sub(r"\D", "", year)[:4] + short_title_token(title)
    return sanitize_item_key(key)


def sanitize_item_key(value: str) -> str:
    words = ascii_words(value)
    key = "".join(words)
    if not key:
        key = "Item" + today().replace("-", "")
    if not key[0].isalnum():
        key = "Item" + key
    return key


def unique_item_key(base: str) -> str:
    base = sanitize_item_key(base)
    candidate = base
    counter = 2
    while (LITERATURE_ITEMS / candidate).exists():
        candidate = f"{base}{counter}"
        counter += 1
    return candidate


def replace_bibtex_key(bibtex: str, key: str) -> str:
    if not BIB_ENTRY_RE.search(bibtex):
        fail("BibTeX entry is missing an entry key")
    return BIB_ENTRY_RE.sub(lambda match: match.group(0).replace(match.group(1), key, 1), bibtex, count=1)


def bibtex_has_field(bibtex: str, field: str) -> bool:
    return bool(bibtex_field(bibtex, field))


def add_bibtex_fields(bibtex: str, fields: dict[str, str]) -> str:
    missing = {key: value for key, value in fields.items() if value and not bibtex_has_field(bibtex, key)}
    if not missing:
        return bibtex
    index = bibtex.rfind("}")
    if index == -1:
        fail("BibTeX entry is missing a closing brace")
    head = bibtex[:index].rstrip()
    tail = bibtex[index:]
    if not head.endswith(","):
        head += ","
    inserted = "\n".join(f"  {key} = {{{bibtex_escape(value)}}}," for key, value in missing.items())
    return head + "\n" + inserted + "\n" + tail.lstrip()


def http_get_text(url: str, accept: str = "application/json") -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        fail(f"HTTP {exc.code} while fetching {url}")
    except urllib.error.URLError as exc:
        fail(f"could not fetch {url}: {exc.reason}")
    except (TimeoutError, socket.timeout):
        fail(f"timed out while fetching {url}")


def fetch_crossref_message(doi: str) -> dict:
    encoded = urllib.parse.quote(normalize_doi(doi), safe="/")
    url = f"https://api.crossref.org/works/{encoded}"
    try:
        data = json.loads(http_get_text(url))
    except SystemExit:
        return {}
    return data.get("message", {}) if isinstance(data, dict) else {}


def fetch_unpaywall_message(doi: str) -> dict:
    if not doi or is_arxiv_doi(doi):
        return {}
    encoded = urllib.parse.quote(normalize_doi(doi), safe="")
    url = f"https://api.unpaywall.org/v2/{encoded}?email={urllib.parse.quote(CONTACT_EMAIL)}"
    try:
        data = json.loads(http_get_text(url))
    except SystemExit:
        return {}
    return data if isinstance(data, dict) else {}


def fetch_bibtex_for_doi(doi: str) -> str:
    encoded = urllib.parse.quote(normalize_doi(doi), safe="/")
    url = f"https://doi.org/{encoded}"
    bibtex = http_get_text(url, accept="application/x-bibtex").strip()
    if not bibtex.startswith("@"):
        fail("DOI lookup did not return BibTeX")
    return bibtex + "\n"


def enrich_bibtex_with_source_keywords(bibtex: str, message: dict) -> str:
    if bibtex_has_field(bibtex, "keywords"):
        return bibtex
    subjects = [str(item).strip() for item in message.get("subject", []) if str(item).strip()]
    if not subjects:
        return bibtex
    return add_bibtex_fields(bibtex, {"keywords": ", ".join(subjects)})


def arxiv_id_from_url(value: str) -> str:
    value = re.sub(r"[?#].*$", "", value.strip())
    doi_match = ARXIV_DOI_RE.search(value)
    if doi_match:
        return doi_match.group(1)
    if ARXIV_ID_RE.match(value):
        return value
    url_match = re.search(r"arxiv\.org/(?:abs|pdf|e-print)/(.+)$", value, flags=re.I)
    if url_match:
        candidate = re.sub(r"\.pdf$", "", url_match.group(1), flags=re.I)
        if ARXIV_ID_RE.match(candidate):
            return candidate
    return value.rstrip("/").split("/")[-1]


def parse_arxiv_entries(text: str) -> list[dict[str, str]]:
    ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []
    rows: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", ns):
        id_text = entry.findtext("atom:id", default="", namespaces=ns)
        title_text = re.sub(r"\s+", " ", entry.findtext("atom:title", default="", namespaces=ns)).strip()
        summary = re.sub(r"\s+", " ", entry.findtext("atom:summary", default="", namespaces=ns)).strip()
        authors = []
        for author in entry.findall("atom:author", ns):
            name = author.findtext("atom:name", default="", namespaces=ns).strip()
            if name:
                authors.append(name)
        published = entry.findtext("atom:published", default="", namespaces=ns)
        updated = entry.findtext("atom:updated", default="", namespaces=ns)
        year = (published or updated or today())[:4]
        primary = entry.find("arxiv:primary_category", ns)
        category = primary.attrib.get("term", "") if primary is not None else ""
        categories = sorted({cat.attrib.get("term", "") for cat in entry.findall("atom:category", ns) if cat.attrib.get("term", "")})
        arxiv_id = arxiv_id_from_url(id_text)
        if not arxiv_id:
            continue
        rows.append({
            "id": arxiv_id,
            "title": title_text,
            "authors": " and ".join(authors),
            "year": year,
            "primary_class": category,
            "categories": ", ".join(categories),
            "doi": normalize_doi(entry.findtext("arxiv:doi", default="", namespaces=ns)),
            "journal_ref": re.sub(r"\s+", " ", entry.findtext("arxiv:journal_ref", default="", namespaces=ns)).strip(),
            "summary": summary,
            "published": published[:10] if published else "",
            "updated": updated[:10] if updated else "",
            "url": f"https://arxiv.org/abs/{arxiv_id}",
        })
    return rows


def parse_arxiv_feed(text: str) -> dict[str, str]:
    rows = parse_arxiv_entries(text)
    return rows[0] if rows else {}


def arxiv_api_query(params: dict[str, object], quiet: bool = False) -> dict[str, str]:
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    try:
        text = http_get_text(url, accept="application/atom+xml")
    except SystemExit:
        if not quiet:
            raise
        return {}
    return parse_arxiv_feed(text)


def arxiv_api_search(params: dict[str, object]) -> list[dict[str, str]]:
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    text = http_get_text(url, accept="application/atom+xml")
    return parse_arxiv_entries(text)


def arxiv_search_terms(field: str, value: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_.:-]+", value)
    return [f"{field}:{word}" for word in words]


def arxiv_field_query(field: str, value: str) -> str:
    terms = arxiv_search_terms(field, value)
    if not terms:
        return ""
    if len(terms) == 1:
        return terms[0]
    return "(" + " AND ".join(terms) + ")"


def arxiv_search_query(args: argparse.Namespace) -> str:
    chunks = [
        arxiv_field_query("all", " ".join(args.query or [])),
        arxiv_field_query("au", args.author or ""),
        arxiv_field_query("ti", args.title or ""),
        arxiv_field_query("abs", args.abstract or ""),
    ]
    if args.category:
        chunks.append(f"cat:{args.category}")
    chunks = [chunk for chunk in chunks if chunk]
    if not chunks:
        fail("provide search keywords or at least one arXiv search filter")
    return " AND ".join(chunks)


def published_doi_from_arxiv(match: dict[str, str]) -> str:
    doi = normalize_doi(match.get("doi", ""))
    if not doi or is_arxiv_doi(doi):
        return ""
    return doi


def arxiv_doi(arxiv_id: str) -> str:
    return normalize_doi(f"10.48550/arXiv.{arxiv_base_id(arxiv_id)}")


def item_key_from_arxiv(match: dict[str, str]) -> str:
    return sanitize_item_key(
        first_author_token(match.get("authors", ""))
        + re.sub(r"\D", "", match.get("year", ""))[:4]
        + short_title_token(match.get("title", ""))
    )


def arxiv_abstract_snippet(summary: str, limit: int = 260) -> str:
    summary = re.sub(r"\s+", " ", summary).strip()
    if len(summary) <= limit:
        return summary
    return summary[: limit - 3].rstrip() + "..."


def print_arxiv_results(rows: list[dict[str, str]], start: int = 0) -> None:
    for index, row in enumerate(rows, start=start + 1):
        category = row.get("primary_class") or row.get("categories") or "uncategorized"
        year = row.get("year") or "unknown-year"
        print(f"{index}. {row['id']} [{category}] {year}")
        print(f"   {row.get('title') or '(untitled)'}")
        if row.get("authors"):
            print(f"   Authors: {row['authors']}")
        if row.get("doi"):
            print(f"   DOI: {row['doi']}")
        if row.get("journal_ref"):
            print(f"   Journal: {row['journal_ref']}")
        print(f"   URL: {row.get('url') or 'https://arxiv.org/abs/' + row['id']}")
        if row.get("summary"):
            print(f"   Abstract: {arxiv_abstract_snippet(row['summary'])}")


def search_arxiv(doi: str = "", title: str = "") -> dict[str, str]:
    if doi:
        arxiv_id = arxiv_id_from_url(doi)
        if ARXIV_ID_RE.match(arxiv_id):
            match = arxiv_api_query({"id_list": arxiv_id, "start": 0, "max_results": 1}, quiet=True)
            if match:
                return match
        match = arxiv_api_query({"search_query": f"doi:{doi}", "start": 0, "max_results": 1}, quiet=True)
        if match:
            return match
    if title:
        compact_title = re.sub(r"\s+", " ", title).strip()
        return arxiv_api_query({"search_query": f'ti:"{compact_title}"', "start": 0, "max_results": 1}, quiet=True)
    return {}


def arxiv_base_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id, flags=re.I)


def arxiv_match_from_bibtex(bibtex: str) -> dict[str, str]:
    arxiv_id = bibtex_field(bibtex, "eprint")
    if not arxiv_id:
        arxiv_id = arxiv_id_from_url(bibtex_doi(bibtex))
    if not ARXIV_ID_RE.match(arxiv_id):
        arxiv_id = arxiv_id_from_url(bibtex_field(bibtex, "url"))
    if not ARXIV_ID_RE.match(arxiv_id):
        return {}
    return {
        "id": arxiv_id,
        "title": bibtex_field(bibtex, "title"),
        "authors": bibtex_field(bibtex, "author"),
        "year": bibtex_field(bibtex, "year") or today()[:4],
        "primary_class": bibtex_field(bibtex, "primaryClass"),
        "url": bibtex_field(bibtex, "url") or f"https://arxiv.org/abs/{arxiv_id}",
    }


def arxiv_source_dir(root: Path) -> Path:
    return root / "source" / "arxiv"


def arxiv_source_bib_path(root: Path) -> Path:
    return arxiv_source_dir(root) / "citation.bib"


def arxiv_bibtex(entry_key: str, match: dict[str, str], fallback_bibtex: str = "") -> str:
    arxiv_id = match["id"]
    fields = [
        ("title", match.get("title") or bibtex_field(fallback_bibtex, "title")),
        ("author", match.get("authors") or bibtex_field(fallback_bibtex, "author")),
        ("year", match.get("year") or bibtex_field(fallback_bibtex, "year")),
        ("eprint", arxiv_id),
        ("archivePrefix", "arXiv"),
        ("primaryClass", match.get("primary_class", "")),
        ("doi", f"10.48550/arXiv.{arxiv_base_id(arxiv_id)}"),
        ("url", match["url"]),
    ]
    lines = [f"@misc{{{sanitize_item_key(entry_key)},"]
    lines.extend(f"  {name} = {{{bibtex_escape(value)}}}," for name, value in fields if value)
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_arxiv_source_bib(root: Path, item_key: str, match: dict[str, str], fallback_bibtex: str = "") -> Path:
    arxiv_dir = arxiv_source_dir(root)
    arxiv_dir.mkdir(parents=True, exist_ok=True)
    path = arxiv_source_bib_path(root)
    path.write_text(arxiv_bibtex(f"{item_key}Arxiv", match, fallback_bibtex), encoding="utf-8")
    return path


def resolve_arxiv_match(root: Path, bibtex: str) -> dict[str, str]:
    existing_arxiv_bib = arxiv_source_bib_path(root)
    if existing_arxiv_bib.exists():
        local_match = arxiv_match_from_bibtex(read(existing_arxiv_bib))
        if local_match:
            refreshed = arxiv_api_query({"id_list": arxiv_base_id(local_match["id"]), "start": 0, "max_results": 1})
            return refreshed or local_match
    doi = bibtex_doi(bibtex)
    title = bibtex_field(bibtex, "title")
    match = search_arxiv(doi=doi, title=title)
    return match or arxiv_match_from_bibtex(bibtex)


def download_url(url: str, dest: Path, force: bool = False, accept: str = "application/octet-stream") -> None:
    if dest.exists() and not force:
        fail(f"destination exists: {rel_home(dest)}; pass --force to overwrite")
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with dest.open("wb") as handle:
                shutil.copyfileobj(response, handle)
    except urllib.error.HTTPError as exc:
        fail(f"HTTP {exc.code} while downloading {url}")
    except urllib.error.URLError as exc:
        fail(f"could not download {url}: {exc.reason}")


def unpaywall_pdf_url(message: dict) -> str:
    locations = []
    best = message.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    locations.extend(location for location in message.get("oa_locations", []) if isinstance(location, dict))
    for location in locations:
        url = location.get("url_for_pdf") or ""
        if url:
            return str(url)
    for location in locations:
        url = str(location.get("url") or "")
        if url.lower().split("?", 1)[0].endswith(".pdf"):
            return url
    return ""


def crossref_pdf_url(message: dict) -> str:
    for link in message.get("link", []):
        if not isinstance(link, dict):
            continue
        content_type = str(link.get("content-type") or "").lower()
        url = str(link.get("URL") or "")
        if url and "application/pdf" in content_type:
            return url
    return ""


def arxiv_pdf_url(match: dict[str, str]) -> str:
    return f"https://arxiv.org/pdf/{match['id']}"


def try_download_pdf_url(url: str, dest: Path, force: bool = False) -> str:
    tmp = dest.with_name(dest.name + ".tmp")
    if tmp.exists():
        tmp.unlink()
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.1",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            with tmp.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        if tmp.read_bytes()[:5] != b"%PDF-":
            tmp.unlink(missing_ok=True)
            return f"downloaded file is not a PDF: {url}"
        if dest.exists() and not force:
            tmp.unlink(missing_ok=True)
            return f"destination exists: {rel_home(dest)}; pass --force to overwrite"
        tmp.replace(dest)
        return ""
    except urllib.error.HTTPError as exc:
        tmp.unlink(missing_ok=True)
        return f"HTTP {exc.code} while downloading {url}"
    except urllib.error.URLError as exc:
        tmp.unlink(missing_ok=True)
        return f"could not download {url}: {exc.reason}"
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        return f"could not write PDF: {exc}"


def download_pdf_url(url: str, dest: Path, force: bool = False) -> None:
    error = try_download_pdf_url(url, dest, force=force)
    if error:
        fail(error)


def path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def safe_tar_members(archive: tarfile.TarFile, dest: Path) -> list[tarfile.TarInfo]:
    members = []
    for member in archive.getmembers():
        target = dest / member.name
        if not path_within(target, dest):
            fail(f"unsafe path in arXiv source archive: {member.name}")
        if member.issym() or member.islnk():
            continue
        members.append(member)
    return members


def extract_arxiv_source(raw_path: Path, dest: Path, force: bool = False) -> str:
    if dest.exists() and any(dest.iterdir()) and not force:
        fail(f"destination exists: {rel_home(dest)}; pass --force to overwrite")
    if dest.exists() and force:
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(raw_path, "r:*") as archive:
            archive.extractall(dest, members=safe_tar_members(archive, dest), filter="data")
        return "tar"
    except tarfile.TarError:
        pass
    try:
        with gzip.open(raw_path, "rb") as source:
            data = source.read()
    except OSError:
        data = raw_path.read_bytes()
        if data.startswith(b"%PDF-"):
            raw_name = "source.pdf"
            raw_kind = "pdf"
        elif b"\\documentclass" in data or b"\\begin{document}" in data:
            raw_name = "source.tex"
            raw_kind = "raw-tex"
        else:
            raw_name = "source.raw"
            raw_kind = "raw"
        (dest / raw_name).write_bytes(data)
        return raw_kind
    (dest / "source.tex").write_bytes(data)
    return "gzip"


def parse_identifier(value: str) -> str:
    """Normalize one cited-work identifier to a canonical token.

    Accepts DOIs (bare, `doi:`, or doi.org URLs), arXiv ids (bare, `arXiv:`,
    arXiv DOIs, or arxiv.org URLs), and `isbn:` values. Returns `doi:...`,
    `arxiv:...`, `isbn:...`, or "" when the value is not a usable identifier.
    """
    raw = value.strip().rstrip(",;")
    if not raw:
        return ""
    lowered = raw.lower()
    if lowered.startswith("isbn"):
        isbn = normalize_isbn(re.sub(r"^isbn[:\s]*", "", raw, flags=re.I))
        return f"isbn:{isbn}" if ISBN_RE.match(isbn) else ""
    candidate = arxiv_id_from_url(raw)
    if ARXIV_ID_RE.match(candidate) and ("arxiv" in lowered or ARXIV_ID_RE.match(raw)):
        return f"arxiv:{arxiv_base_id(candidate).lower()}"
    doi = normalize_doi(raw)
    if doi.startswith("10.") and "/" in doi and " " not in doi:
        return f"doi:{doi}"
    return ""


def identifier_aliases(token: str) -> set[str]:
    """Expand one token with its equivalent forms, so a cited arXiv id
    matches a held arXiv DOI and vice versa."""
    aliases = {token}
    kind, _, value = token.partition(":")
    if kind == "arxiv":
        aliases.add(f"doi:{arxiv_doi(value)}")
    elif kind == "doi" and is_arxiv_doi(value):
        arxiv = arxiv_id_from_url(value)
        if ARXIV_ID_RE.match(arxiv):
            aliases.add(f"arxiv:{arxiv_base_id(arxiv).lower()}")
    return aliases


def item_identifier_tokens(root: Path) -> set[str]:
    """All identifier tokens (with aliases) that name one library item."""
    tokens: set[str] = set()
    for bib_path in [root / "citation.bib", arxiv_source_bib_path(root)]:
        if not bib_path.exists():
            continue
        bibtex = read(bib_path)
        doi = bibtex_doi(bibtex)
        if doi:
            tokens |= identifier_aliases(f"doi:{doi}")
        match = arxiv_match_from_bibtex(bibtex)
        if match:
            tokens |= identifier_aliases(f"arxiv:{arxiv_base_id(match['id']).lower()}")
        isbn = normalize_isbn(bibtex_field(bibtex, "isbn"))
        if ISBN_RE.match(isbn):
            tokens.add(f"isbn:{isbn}")
    return tokens


def references_path(root: Path) -> Path:
    return root / REFERENCES_FILENAME


def read_references(root: Path) -> list[tuple[str, str]]:
    """Parse references.txt into ordered unique (token, note) pairs.

    Lines may hold identifiers in any form parse_identifier accepts, with
    optional `# note` comments. Missing file means no known references."""
    path = references_path(root)
    if not path.exists():
        return []
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    for line in read(path).splitlines():
        text, _, comment = line.partition("#")
        token = parse_identifier(text)
        if token and token not in seen:
            seen.add(token)
            entries.append((token, comment.strip()))
    return entries


def write_references(root: Path, entries: list[tuple[str, str]], header: str) -> None:
    lines = [f"# {header}"]
    for token, note in entries:
        lines.append(f"{token}  # {note}" if note else token)
    references_path(root).write_text("\n".join(lines) + "\n", encoding="utf-8")


def library_identifier_index() -> dict[str, str]:
    """token -> ItemKey for every identifier a library item answers to."""
    index: dict[str, str] = {}
    for bib_path in list_item_bibtex_files():
        for token in item_identifier_tokens(bib_path.parent):
            index.setdefault(token, bib_path.parent.name)
    return index


def semantic_scholar_paper_id(root: Path) -> str:
    bib_path = root / "citation.bib"
    bibtex = read(bib_path) if bib_path.exists() else ""
    doi = bibtex_doi(bibtex)
    if doi and not is_arxiv_doi(doi):
        return f"DOI:{doi}"
    match = arxiv_match_from_bibtex(bibtex)
    if match:
        return f"arXiv:{arxiv_base_id(match['id'])}"
    if doi:
        return f"DOI:{doi}"
    fail(f"item {root.name} has neither a DOI nor an arXiv id in citation.bib")
    return ""


def _semantic_scholar_references(root: Path) -> tuple[list[tuple[str, str]], int]:
    """Fetch the item's reference list from Semantic Scholar.

    Returns (entries, skipped): (token, title) pairs for cited works with a
    usable identifier, and the count of cited works without one."""
    paper = semantic_scholar_paper_id(root)
    url = SEMANTIC_SCHOLAR_REFERENCES_URL.format(
        paper=urllib.parse.quote(paper, safe=":/")
    )
    payload = json.loads(http_get_text(url))
    entries: list[tuple[str, str]] = []
    skipped = 0
    for row in payload.get("data") or []:
        cited = row.get("citedPaper") or {}
        external = cited.get("externalIds") or {}
        token = parse_identifier(str(external.get("DOI") or ""))
        if not token:
            arxiv = str(external.get("ArXiv") or "")
            if ARXIV_ID_RE.match(arxiv):
                token = f"arxiv:{arxiv_base_id(arxiv).lower()}"
        if not token:
            skipped += 1
            continue
        title = re.sub(r"\s+", " ", str(cited.get("title") or "")).strip()
        entries.append((token, title))
    return entries, skipped


def _openalex_identifier(root: Path) -> str:
    bib_path = root / "citation.bib"
    bibtex = read(bib_path) if bib_path.exists() else ""
    doi = bibtex_doi(bibtex)
    return f"doi:{doi}" if doi else ""


def _openalex_token(work: dict) -> str:
    token = parse_identifier(str(work.get("doi") or ""))
    if token:
        return token
    for location in work.get("locations") or []:
        if not isinstance(location, dict):
            continue
        for field in ("landing_page_url", "pdf_url"):
            token = parse_identifier(str(location.get(field) or ""))
            if token:
                return token
    return ""


def _openalex_references(root: Path) -> tuple[list[tuple[str, str]], int]:
    paper = _openalex_identifier(root)
    if not paper:
        return [], 0
    url = OPENALEX_WORK_URL.format(
        paper=urllib.parse.quote(paper, safe=":")
    )
    payload = json.loads(http_get_text(url))
    referenced = [
        str(value).rstrip("/").rsplit("/", 1)[-1]
        for value in payload.get("referenced_works") or []
        if str(value).strip()
    ]
    works: dict[str, dict] = {}
    for start in range(0, len(referenced), 100):
        chunk = referenced[start:start + 100]
        query = urllib.parse.urlencode({
            "filter": "openalex:" + "|".join(chunk),
            "per-page": 100,
            "select": "id,doi,display_name,locations",
        })
        batch = json.loads(http_get_text(f"{OPENALEX_WORKS_URL}?{query}"))
        for work in batch.get("results") or []:
            work_id = str(work.get("id") or "").rstrip("/").rsplit("/", 1)[-1]
            if work_id:
                works[work_id] = work
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    skipped = 0
    for work_id in referenced:
        work = works.get(work_id, {})
        token = _openalex_token(work)
        if not token:
            skipped += 1
            continue
        if token in seen:
            continue
        seen.add(token)
        title = re.sub(
            r"\s+", " ", str(work.get("display_name") or "")
        ).strip()
        entries.append((token, title))
    return entries, skipped


def fetch_references(root: Path) -> tuple[list[tuple[str, str]], int, str]:
    """Fetch cited-work identifiers, falling back when one graph is empty."""
    entries, skipped = _semantic_scholar_references(root)
    if entries:
        return entries, skipped, "Semantic Scholar"
    openalex_entries, openalex_skipped = _openalex_references(root)
    if openalex_entries or openalex_skipped:
        return openalex_entries, openalex_skipped, "OpenAlex"
    return entries, skipped, "Semantic Scholar and OpenAlex"


def command_literature_help(args: argparse.Namespace) -> None:
    args.parser.print_help()


def command_literature_init(_args: argparse.Namespace) -> None:
    for path in literature_required_dirs():
        existed = path.exists()
        path.mkdir(parents=True, exist_ok=True)
        print(f"{'ok' if existed else 'created'}: {rel_home(path)}")


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        value = input(f"{prompt} {suffix}: ").strip().lower()
    except EOFError:
        print()
        return False
    if not value:
        return default
    return value in {"y", "yes", "true", "1"}




def command_literature_add_doi(args: argparse.Namespace) -> None:
    ensure_literature_dirs()
    doi = normalize_doi(args.doi)
    if not doi:
        fail("DOI is required")
    existing = find_item_by_doi(doi)
    if existing:
        fail(f"DOI already exists in {rel_home(existing)}")

    message = {} if is_arxiv_doi(doi) else fetch_crossref_message(doi)
    bibtex = fetch_bibtex_for_doi(doi)
    base_key = args.key or item_key_from_metadata(message, bibtex) or bibtex_key(bibtex)
    key = sanitize_item_key(base_key)
    if args.key and (LITERATURE_ITEMS / key).exists():
        fail(f"item already exists: {key}")
    key = key if args.key else unique_item_key(key)
    root = item_path(key)
    root.mkdir(parents=True, exist_ok=False)

    bibtex = replace_bibtex_key(bibtex, key)
    bibtex = enrich_bibtex_with_source_keywords(bibtex, message)
    (root / "citation.bib").write_text(bibtex.rstrip() + "\n", encoding="utf-8")
    write_info_if_missing(root, bibtex)
    print(f"created: literature:{key}")
    print(f"folder: {rel_home(root)}")
    print(f"citation: {rel_home(root / 'citation.bib')}")


def command_literature_search_arxiv(args: argparse.Namespace) -> None:
    if args.max_results < 1:
        fail("--max must be at least 1")
    if args.start < 0:
        fail("--start must be zero or greater")
    query = arxiv_search_query(args)
    rows = arxiv_api_search({
        "search_query": query,
        "start": args.start,
        "max_results": args.max_results,
        "sortBy": args.sort,
        "sortOrder": "descending",
    })
    if not rows:
        print("no arXiv results")
        return
    print_arxiv_results(rows, start=args.start)
    from ws_lib import project

    enclosing = project.find_enclosing_project()
    if enclosing is not None and sys.stdin.isatty():
        print(f"note: items added from this folder can be recorded in project '{enclosing.name}'")


def command_literature_add_arxiv(args: argparse.Namespace) -> None:
    ensure_literature_dirs()
    full = bool(getattr(args, "full", False))
    prefer_published = bool(args.prefer_published or full)
    download_pdf = bool(args.pdf or full)
    download_source = bool(args.source or full)
    arxiv_id = arxiv_id_from_url(args.arxiv_id)
    if not ARXIV_ID_RE.match(arxiv_id):
        fail("arXiv ID must look like 2502.06654, 2502.06654v1, or hep-th/9901001")
    base_id = arxiv_base_id(arxiv_id)
    arxiv_item_doi = arxiv_doi(base_id)
    existing = find_item_by_doi(arxiv_item_doi)
    if existing:
        fail(f"arXiv record already exists in {rel_home(existing)}")

    match = arxiv_api_query({"id_list": base_id, "start": 0, "max_results": 1})
    if not match:
        fail("no arXiv match found")
    published_doi = published_doi_from_arxiv(match)
    if published_doi:
        existing = find_item_by_doi(published_doi)
        if existing:
            fail(f"published DOI already exists in {rel_home(existing)}")

    base_key = args.key or item_key_from_arxiv(match)
    key = sanitize_item_key(base_key)
    if args.key and (LITERATURE_ITEMS / key).exists():
        fail(f"item already exists: {key}")
    key = key if args.key else unique_item_key(key)

    use_published = bool(prefer_published and published_doi)
    if use_published:
        message = fetch_crossref_message(published_doi)
        bibtex = replace_bibtex_key(fetch_bibtex_for_doi(published_doi), key)
        bibtex = enrich_bibtex_with_source_keywords(bibtex, message)
    else:
        bibtex = arxiv_bibtex(key, match)

    root = item_path(key)
    if root.exists():
        fail(f"item already exists: {key}")
    root.mkdir(parents=True)
    (root / "citation.bib").write_text(bibtex.rstrip() + "\n", encoding="utf-8")
    write_info_if_missing(root, bibtex)
    arxiv_path = write_arxiv_source_bib(root, key, match, bibtex)

    print(f"created: literature:{key}")
    print(f"folder: {rel_home(root)}")
    print(f"citation: {rel_home(root / 'citation.bib')}")
    print(f"arxiv source citation: {rel_home(arxiv_path)}")
    print(f"arxiv latest: {match['id']}")
    if published_doi:
        print(f"published DOI: {published_doi}" + (" (main citation)" if use_published else ""))
    elif prefer_published:
        print("published DOI: not provided by arXiv metadata; main citation is arXiv")


    if download_pdf:
        command_literature_download_pdf(argparse.Namespace(
            key=key,
            open_or_arxiv=True,
            arxiv=False,
            url=None,
            name=None,
            force=args.force,
        ))
    if download_source:
        command_literature_download_source(argparse.Namespace(
            key=key,
            arxiv=True,
            force=args.force,
            no_extract=args.no_extract,
        ))


def command_literature_add_isbn(args: argparse.Namespace) -> None:
    ensure_literature_dirs()
    isbn = normalize_isbn(args.isbn)
    if not ISBN_RE.match(isbn):
        fail("ISBN must be a valid ISBN-10 or ISBN-13")
    existing = find_item_by_isbn(isbn)
    if existing:
        fail(f"ISBN already exists in {rel_home(existing)}")

    title = args.title or ask("Title")
    author = args.author or ask("Authors, BibTeX format")
    year = args.year or ask("Year", today()[:4])
    publisher = args.publisher or ask("Publisher, optional")
    url = args.url or ask("URL, optional")
    if not title or not author or not year:
        fail("ISBN entries require title, authors, and year")

    key = sanitize_item_key(args.key) if args.key else unique_item_key(first_author_token(author) + year + short_title_token(title))
    root = item_path(key)
    if root.exists():
        fail(f"item already exists: {key}")
    root.mkdir(parents=True)

    fields = [
        ("title", title),
        ("author", author),
        ("year", year),
        ("isbn", isbn),
        ("publisher", publisher),
        ("url", url),
    ]
    lines = [f"@book{{{key},"]
    lines.extend(f"  {name} = {{{bibtex_escape(value)}}}," for name, value in fields if value)
    lines.append("}")
    bibtex = "\n".join(lines) + "\n"
    (root / "citation.bib").write_text(bibtex, encoding="utf-8")
    write_info_if_missing(root, bibtex)
    print(f"created: literature:{key}")
    print(f"folder: {rel_home(root)}")
    print(f"citation: {rel_home(root / 'citation.bib')}")


def command_literature_add_manual(args: argparse.Namespace) -> None:
    ensure_literature_dirs()
    interactive = not all([args.type, args.title, args.author, args.year])
    if interactive:
        print("BibTeX type options: " + ", ".join(LITERATURE_TYPES))
    entry_type = args.type or ask_choice("BibTeX type", LITERATURE_TYPES, "article")
    title = args.title or ask("Title")
    author = args.author or ask("Authors, BibTeX format")
    year = args.year or ask("Year", today()[:4])
    doi = normalize_doi(args.doi or (ask("DOI, optional") if interactive else ""))
    isbn = normalize_isbn(args.isbn or (ask("ISBN, optional") if interactive else ""))
    arxiv = args.arxiv or (ask("arXiv ID, optional") if interactive else "")
    publisher = args.publisher or (ask("Publisher, optional") if interactive else "")
    # An @article without a journal is malformed BibTeX, so ask for it when the
    # entry type needs one. Volume/number/pages stay flag-only to keep the
    # wizard short; they are optional in every entry type.
    journal = getattr(args, "journal", "") or ""
    if not journal and interactive and entry_type in {"article", "inproceedings"}:
        label = "Journal" if entry_type == "article" else "Booktitle"
        journal = ask(f"{label}, optional")
    volume = getattr(args, "volume", "") or ""
    number = getattr(args, "number", "") or ""
    pages = getattr(args, "pages", "") or ""
    url = args.url or (ask("URL, optional") if interactive else "")
    keywords = list(args.keyword or [])
    if not keywords and interactive:
        raw_keywords = ask("Keywords from paper/source, comma-separated, optional")
        keywords = [item.strip() for item in raw_keywords.split(",") if item.strip()]

    if entry_type not in LITERATURE_TYPES:
        fail(f"type must be one of: {', '.join(LITERATURE_TYPES)}")
    if not title or not author or not year:
        fail("manual entries require title, authors, and year")
    if doi and find_item_by_doi(doi):
        fail(f"DOI already exists in {rel_home(find_item_by_doi(doi))}")
    if isbn:
        if not ISBN_RE.match(isbn):
            fail("ISBN must be a valid ISBN-10 or ISBN-13")
        if find_item_by_isbn(isbn):
            fail(f"ISBN already exists in {rel_home(find_item_by_isbn(isbn))}")
    arxiv_match = search_arxiv(doi=arxiv) if arxiv else {}
    if arxiv and not arxiv_match:
        fail("no arXiv match found for --arxiv")

    key = sanitize_item_key(args.key) if args.key else unique_item_key(first_author_token(author) + year + short_title_token(title))
    root = item_path(key)
    if root.exists():
        fail(f"item already exists: {key}")
    root.mkdir(parents=True)

    fields = [
        ("title", title),
        ("author", author),
    ]
    if journal:
        fields.append(("booktitle" if entry_type == "inproceedings" else "journal", journal))
    for name, value in (("volume", volume), ("number", number), ("pages", pages)):
        if value:
            fields.append((name, value))
    fields.append(("year", year))
    if doi:
        fields.append(("doi", doi))
    if isbn:
        fields.append(("isbn", isbn))
    if publisher:
        fields.append(("publisher", publisher))
    if url:
        fields.append(("url", url))
    if keywords:
        fields.append(("keywords", ", ".join(keywords)))

    lines = [f"@{entry_type}{{{key},"]
    lines.extend(f"  {name} = {{{bibtex_escape(value)}}}," for name, value in fields if value)
    lines.append("}")
    bibtex = "\n".join(lines) + "\n"
    (root / "citation.bib").write_text(bibtex, encoding="utf-8")
    write_info_if_missing(root, bibtex)
    if arxiv_match:
        arxiv_path = write_arxiv_source_bib(root, key, arxiv_match, bibtex)
        print(f"arxiv source citation: {rel_home(arxiv_path)}")
        print(f"arxiv latest: {arxiv_match['id']}")
    print(f"created: literature:{key}")
    print(f"folder: {rel_home(root)}")
    print(f"citation: {rel_home(root / 'citation.bib')}")


def command_literature_show(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    bib_path = root / "citation.bib"
    if not bib_path.exists():
        fail(f"missing citation: {rel_home(bib_path)}")
    bibtex = read(bib_path)
    key = bibtex_key(bibtex) or root.name
    print(f"ref: literature:{root.name}")
    if key != root.name:
        print(f"bibtex key: {key}")
    print(f"folder: {rel_home(root)}")
    for field in ["title", "author", "year", "doi", "isbn", "publisher", "url", "eprint", "archivePrefix", "keywords"]:
        value = bibtex_field(bibtex, field)
        if value:
            clean_value = re.sub(r"\s+", " ", value)
            print(f"{field}: {clean_value}")
    print("fields: " + (", ".join(info_fields(root)) or "none"))
    print("subfields: " + (", ".join(info_subfields(root)) or "none"))
    pdfs = sorted(path.name for path in root.glob("*.pdf"))
    source = root / "source"
    source_state = "yes" if source.exists() and any(source.iterdir()) else ("empty" if source.exists() else "no")
    arxiv_bib = arxiv_source_bib_path(root)
    arxiv_state = "no"
    if arxiv_bib.exists():
        arxiv_source_bib = read(arxiv_bib)
        arxiv_state = bibtex_field(arxiv_source_bib, "eprint") or "yes"
    arxiv_dir = arxiv_source_dir(root)
    arxiv_package = "yes" if (arxiv_dir / "source.tar").exists() else "no"
    arxiv_files = "yes" if (arxiv_dir / "files").exists() and any((arxiv_dir / "files").iterdir()) else "no"
    print("pdf: " + (", ".join(pdfs) if pdfs else "no"))
    print(f"source: {source_state}")
    print(f"arxiv source: {arxiv_state}")
    print(f"arxiv package: {arxiv_package}")
    print(f"arxiv files: {arxiv_files}")
    print(f"info: {'yes' if (root / 'info.yaml').exists() else 'no'}")
    print(f"summary: {'yes' if (root / 'summary.md').exists() else 'no'}")
    print(f"notes: {'yes' if (root / 'notes.md').exists() else 'no'}")


def command_literature_enrich(args: argparse.Namespace) -> None:
    if not args.arxiv:
        fail("currently supported enrichment: --arxiv")
    root = item_from_ref(command_ref(args))
    bib_path = root / "citation.bib"
    if not bib_path.exists():
        fail(f"missing citation: {rel_home(bib_path)}")
    bibtex = read(bib_path)
    doi = bibtex_doi(bibtex)
    title = bibtex_field(bibtex, "title")
    if args.arxiv_id:
        arxiv_id = arxiv_id_from_url(args.arxiv_id)
        if not ARXIV_ID_RE.match(arxiv_id):
            fail("--arxiv-id must look like 2502.06654 or 2502.06654v1")
        match = arxiv_api_query({"id_list": arxiv_base_id(arxiv_id), "start": 0, "max_results": 1})
    else:
        match = search_arxiv(doi=doi, title=title)
    if not match:
        fail("no arXiv match found")
    arxiv_path = write_arxiv_source_bib(root, root.name, match, bibtex)
    print(f"wrote: {rel_home(arxiv_path)}")
    print(f"main citation unchanged: {rel_home(bib_path)}")
    print(f"arxiv latest: {match['id']}")
    print(f"source URL: https://arxiv.org/e-print/{match['id']}")


def command_literature_download_source(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    bib_path = root / "citation.bib"
    if not bib_path.exists():
        fail(f"missing citation: {rel_home(bib_path)}")
    bibtex = read(bib_path)
    match = resolve_arxiv_match(root, bibtex)
    if not match:
        fail("no arXiv match found")
    arxiv_path = write_arxiv_source_bib(root, root.name, match, bibtex)
    raw_path = arxiv_source_dir(root) / "source.tar"
    files_path = arxiv_source_dir(root) / "files"
    source_url = f"https://arxiv.org/e-print/{match['id']}"
    download_url(source_url, raw_path, force=args.force)
    print(f"wrote: {rel_home(arxiv_path)}")
    print(f"downloaded: {rel_home(raw_path)}")
    print(f"arxiv latest: {match['id']}")
    if args.no_extract:
        print("extract: skipped")
        return
    extracted_as = extract_arxiv_source(raw_path, files_path, force=args.force)
    print(f"extracted: {rel_home(files_path)} ({extracted_as})")


def command_literature_download_pdf(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    bib_path = root / "citation.bib"
    if not bib_path.exists():
        fail(f"missing citation: {rel_home(bib_path)}")
    dest_name = args.name or "paper.pdf"
    if not dest_name.endswith(".pdf"):
        fail("PDF destination name must end with .pdf")
    dest = root / dest_name
    if dest.exists() and not args.force:
        fail(f"destination exists: {rel_home(dest)}; pass --force to overwrite")
    bibtex = read(bib_path)

    candidates: list[tuple[str, str]] = []
    open_or_arxiv = args.open_or_arxiv or (not args.url and not args.arxiv)
    if args.url:
        candidates.append(("direct URL", args.url))
    elif args.arxiv:
        match = resolve_arxiv_match(root, bibtex)
        if not match:
            fail("no arXiv match found")
        write_arxiv_source_bib(root, root.name, match, bibtex)
        candidates.append(("arXiv", arxiv_pdf_url(match)))
    elif open_or_arxiv:
        doi = bibtex_doi(bibtex)
        if doi and not is_arxiv_doi(doi):
            open_url = unpaywall_pdf_url(fetch_unpaywall_message(doi))
            if open_url:
                candidates.append(("open access", open_url))
            crossref_url = crossref_pdf_url(fetch_crossref_message(doi))
            if crossref_url and crossref_url not in {url for _label, url in candidates}:
                candidates.append(("Crossref PDF", crossref_url))
        match = resolve_arxiv_match(root, bibtex)
        if match:
            write_arxiv_source_bib(root, root.name, match, bibtex)
            candidates.append(("arXiv fallback", arxiv_pdf_url(match)))
    if not candidates:
        fail("no open-access PDF or arXiv PDF found")

    errors = []
    for source_label, source_url in candidates:
        error = try_download_pdf_url(source_url, dest, force=args.force)
        if not error:
            print(f"downloaded: {rel_home(dest)}")
            print(f"source: {source_label}")
            print(f"url: {source_url}")
            return
        errors.append(f"{source_label}: {error}")
    fail("no usable PDF found; " + " | ".join(errors))


def command_literature_attach_pdf(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    if not (root / "citation.bib").exists():
        fail(f"missing item: {command_ref(args)}")
    src = Path(args.path).expanduser()
    if not src.is_file():
        fail(f"PDF file not found: {src}")
    dest_name = args.name or "paper.pdf"
    if not dest_name.endswith(".pdf"):
        fail("PDF destination name must end with .pdf")
    dest = root / dest_name
    if dest.exists() and not args.force:
        fail(f"destination exists: {rel_home(dest)}; pass --force to overwrite")
    shutil.copy2(src, dest)
    print(f"attached: {rel_home(dest)}")


def command_literature_attach_source(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    if not (root / "citation.bib").exists():
        fail(f"missing item: {command_ref(args)}")
    src = Path(args.path).expanduser()
    if not src.exists():
        fail(f"source path not found: {src}")
    source_root = root / "source"
    source_root.mkdir(exist_ok=True)
    dest = source_root / src.name
    if src.is_dir():
        if dest.exists() and not args.force:
            fail(f"destination exists: {rel_home(dest)}; pass --force to merge")
        shutil.copytree(src, dest, dirs_exist_ok=args.force)
    else:
        if dest.exists() and not args.force:
            fail(f"destination exists: {rel_home(dest)}; pass --force to overwrite")
        shutil.copy2(src, dest)
    print(f"attached: {rel_home(dest)}")


def command_literature_edit(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    if not (root / "citation.bib").exists():
        fail(f"missing item: {command_ref(args)}")
    additions = [value.strip().lower() for value in args.add_field if value.strip()]
    removals = [value.strip().lower() for value in args.remove_field if value.strip()]
    subfield_additions = [
        value.strip().lower()
        for value in getattr(args, "add_subfield", [])
        if value.strip()
    ]
    subfield_removals = [
        value.strip().lower()
        for value in getattr(args, "remove_subfield", [])
        if value.strip()
    ]
    if not additions and not removals and not subfield_additions and not subfield_removals:
        fail("nothing to edit; use field/subfield add/remove options")
    fields = [value for value in info_fields(root) if value not in set(removals)]
    for value in additions:
        if value not in fields:
            fields.append(value)
    subfields = [
        value for value in info_subfields(root)
        if value not in set(subfield_removals)
    ]
    for value in subfield_additions:
        if value not in subfields:
            subfields.append(value)
    from ws_lib import project

    problems = project.classification_problems(fields, subfields, load_taxonomy())
    if problems:
        fail("; ".join(problems) + " (extend with `ws literature add-field` / `add-subfield`)")
    update_info_classifiers(root, fields, subfields)
    print(f"updated: {rel_home(root / 'info.yaml')}")
    print("fields: " + (", ".join(fields) if fields else "none"))
    print("subfields: " + (", ".join(subfields) if subfields else "none"))
    print("views: run `ws literature views rebuild` to refresh by-* folders")


def command_literature_citations(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    if not (root / "citation.bib").exists():
        fail(f"unknown literature item: {command_ref(args)}")
    if args.fetch:
        entries, skipped, provider = fetch_references(root)
        if not entries:
            fail(
                f"{provider} returned no cited works with a DOI or arXiv ID; "
                f"{rel_home(references_path(root))} was left unchanged"
            )
        header = (
            f"cited works of {root.name}, from {provider} on {today()};"
            f" {len(entries)} identifiers, {skipped} cited works without one"
        )
        write_references(root, entries, header)
        note = f" ({skipped} cited works had no usable identifier)" if skipped else ""
        print(f"wrote {rel_home(references_path(root))}: {len(entries)} identifiers{note}")
        print(f"source: {provider}")
    if not references_path(root).exists():
        fail(
            f"missing {rel_home(references_path(root))} — fetch it with"
            f" `ws literature citations literature:{root.name} --fetch`"
            " or write one identifier per line yourself"
        )
    entries = read_references(root)
    if args.in_library:
        index = library_identifier_index()
        seen_keys: set[str] = set()
        for token, _ in entries:
            for alias in identifier_aliases(token):
                key = index.get(alias, "")
                if key and key != root.name and key not in seen_keys:
                    seen_keys.add(key)
                    print(f"literature:{key}  ({token})")
                    break
        if not seen_keys:
            print("no cited works are in the library", file=sys.stderr)
        return
    for token, note in entries:
        print(f"{token}  # {note}" if note else token)


def command_literature_cited_by(args: argparse.Namespace) -> None:
    root = item_from_ref(command_ref(args))
    if not (root / "citation.bib").exists():
        fail(f"unknown literature item: {command_ref(args)}")
    targets = item_identifier_tokens(root)
    if not targets:
        fail(f"item {command_ref(args)} has no DOI, arXiv id, or ISBN to match against")
    found = False
    for bib_path in list_item_bibtex_files():
        other = bib_path.parent
        if other.name == root.name:
            continue
        for token, _ in read_references(other):
            if identifier_aliases(token) & targets:
                print(f"literature:{other.name}")
                found = True
                break
    if not found:
        print("no library item cites this one", file=sys.stderr)


def command_literature_add(args: argparse.Namespace) -> None:
    validate_requested_fields(args)
    source = (args.source_value or "").strip()
    kind = args.kind
    before = {path.parent.name for path in list_item_bibtex_files()}
    if not source and kind == "auto" and not args.title and sys.stdin.isatty():
        source = ask("DOI, arXiv ID, ISBN, or URL (empty for manual entry)").strip()
    if kind == "auto":
        normalized = normalize_doi(source)
        if normalized and DOI_RE.match(normalized):
            kind = "doi"
        elif source and ARXIV_ID_RE.match(arxiv_id_from_url(source)):
            kind = "arxiv"
        elif ISBN_RE.match(normalize_isbn(source)):
            kind = "isbn"
        elif not source and (args.title or sys.stdin.isatty()):
            kind = "manual"
        else:
            fail("could not identify source; use --kind doi|arxiv|isbn|manual")
    if kind == "doi":
        args.doi = source
        command_literature_add_doi(args)
    elif kind == "arxiv":
        args.arxiv_id = source
        command_literature_add_arxiv(args)
    elif kind == "isbn":
        args.isbn = source
        command_literature_add_isbn(args)
    else:
        args.type = args.entry_type
        args.doi = args.doi or ""
        args.isbn = args.isbn or ""
        args.arxiv = args.arxiv or ""
        command_literature_add_manual(args)
    created = sorted({path.parent.name for path in list_item_bibtex_files()} - before)
    if created:
        classify_new_item(item_path(created[0]), args)


def command_literature_add_field(args: argparse.Namespace) -> None:
    add_taxonomy_value("fields", args.value)


def command_literature_add_subfield(args: argparse.Namespace) -> None:
    add_subfield(args.field, args.value)


def command_literature_taxonomy(_args: argparse.Namespace) -> None:
    data = load_taxonomy()
    print(f"taxonomy: {rel_home(paths.PROJECT_TAXONOMY)} (shared workspace-wide)")
    print("fields: " + ", ".join(data["fields"]))
    print("subfields:")
    for field in data["fields"]:
        values = data["subfields"].get(field, [])
        print(f"  {field}: {', '.join(values) if values else '-'}")


def command_literature_views_rebuild(args: argparse.Namespace) -> None:
    from ws_lib import anatomy

    counts = anatomy.rebuild_literature()
    if getattr(args, "json", False):
        print(json.dumps({"root": str(LITERATURE), "links": counts}))
        return
    print(f"rebuilt: {rel_home(LITERATURE)}/by-*")
    for name in sorted(counts):
        print(f"  {name}: {counts[name]} links")


def _shared_vocabulary_hints() -> tuple[str, str]:
    """Field and subfield vocabularies for help strings; empty when unreadable."""
    try:
        from ws_lib import project

        taxonomy = project.load_taxonomy()
        return ", ".join(taxonomy["fields"]), ", ".join(project.all_subfields(taxonomy))
    except Exception:
        return "", ""


def attach_add_parser(sub: argparse._SubParsersAction, name: str = "add") -> argparse.ArgumentParser:
    """The literature ingest parser; serves `ws literature add` and `ws add literature`."""
    lit_add = sub.add_parser(
        name,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="add a paper or book: DOI, arXiv ID/URL, or ISBN; asks when run bare",
        epilog="""Behavior:
  Detects the identifier kind automatically; --kind overrides.
  Run bare on a terminal, it asks for the identifier; empty means manual entry.
  Creates one canonical item under items/<ItemKey>/.
  arXiv adds always write source/arxiv/citation.bib for the arXiv record.
  With --prefer-published, uses the journal DOI BibTeX as the main citation.
  --full is shorthand for --prefer-published --pdf --source.
  Relations are separate: link afterwards with `ws relate literature:<key> ...`.
""",
    )
    fields_hint, subfields_hint = _shared_vocabulary_hints()
    lit_add.add_argument("source_value", nargs="?", help="DOI, arXiv ID/URL, or ISBN")
    lit_add.add_argument(
        "--kind",
        choices=["auto", "doi", "arxiv", "isbn", "manual"],
        default="auto",
        metavar="KIND",
        help="one of: auto, doi, arxiv, isbn, manual; defaults to auto-detection",
    )
    lit_add.add_argument("--key", metavar="ITEMKEY", help="item key to store under; derived from the citation when omitted")
    lit_add.add_argument(
        "--field",
        action="append",
        help=(
            f"repeatable; one of: {fields_hint} (extend with `ws literature add-field`)"
            if fields_hint
            else "repeatable field classifier from the shared workspace vocabulary"
        ),
    )
    lit_add.add_argument(
        "--subfield",
        action="append",
        help=(
            f"repeatable; one of: {subfields_hint}; must belong to a selected field"
            if subfields_hint
            else "repeatable controlled subfield; must belong to a selected field"
        ),
    )
    lit_add.add_argument("--full", action="store_true", help="shorthand for --prefer-published --pdf --source")
    lit_add.add_argument("--prefer-published", action="store_true", help="use the published DOI as the main citation, keeping the arXiv one alongside")
    lit_add.add_argument("--pdf", action="store_true", help="also download the PDF")
    lit_add.add_argument("--source", action="store_true", dest="source")
    lit_add.add_argument("--force", action="store_true")
    lit_add.add_argument("--no-extract", action="store_true", help="download the source package without extracting it")
    lit_add.add_argument(
        "--entry-type",
        choices=LITERATURE_TYPES,
        default="article",
        metavar="TYPE",
        help=f"one of: {', '.join(LITERATURE_TYPES)}; defaults to article",
    )
    lit_add.add_argument("--title")
    lit_add.add_argument("--author")
    lit_add.add_argument("--year")
    lit_add.add_argument("--doi")
    lit_add.add_argument("--isbn")
    lit_add.add_argument("--publisher")
    lit_add.add_argument(
        "--journal",
        help="journal name for a manual @article (booktitle for @inproceedings)",
    )
    lit_add.add_argument("--volume")
    lit_add.add_argument("--number", help="issue number")
    lit_add.add_argument("--pages", help='page range, e.g. "601--642"')
    lit_add.add_argument("--url")
    lit_add.add_argument("--arxiv")
    lit_add.add_argument("--keyword", action="append")
    lit_add.set_defaults(func=command_literature_add)
    return lit_add


def literature_edit_arguments(edit: argparse.ArgumentParser) -> None:
    """The literature edit flag set; shared by the domain parser and `ws edit`."""
    fields_hint, subfields_hint = _shared_vocabulary_hints()
    edit.add_argument(
        "--add-field",
        action="append",
        default=[],
        help=(
            f"repeatable; one of: {fields_hint}"
            if fields_hint
            else "add a field from the shared vocabulary; repeatable"
        ),
    )
    edit.add_argument(
        "--add-subfield",
        action="append",
        default=[],
        help=(
            f"repeatable; one of: {subfields_hint}"
            if subfields_hint
            else "add a controlled subfield; repeatable"
        ),
    )
    edit.add_argument(
        "--remove-subfield",
        action="append",
        default=[],
        help="remove a subfield; repeatable",
    )
    edit.add_argument(
        "--remove-field",
        action="append",
        default=[],
        help="remove a field; repeatable",
    )


def add_parser(sub: argparse._SubParsersAction) -> None:
    literature = sub.add_parser(
        "literature",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Manage the canonical workspace literature library.",
        epilog=f"""Library structure:
  {rel_home(LITERATURE_ITEMS)}/<ItemKey>/citation.bib
  {rel_home(LITERATURE)}/by-author/<author>/<ItemKey>
  {rel_home(LITERATURE)}/by-field/<field>/<subfield-or-unclassified>/<ItemKey>
  {rel_home(LITERATURE)}/by-year/<year>/<ItemKey>

Principles:
  citation.bib is the required citation source of truth.
  PDF, source, summary.md, and notes.md are optional item-local files.
  by-* folders are disposable views; fields and subfields are editable classifiers.
  Search accepts metadata; actions on an existing item require literature:<ItemKey>.

Contract:
  {rel_home(LIBRARY_CONTRACT_DOC)}
""",
    )
    literature.set_defaults(func=command_literature_help, parser=literature)
    lit_sub = literature.add_subparsers(dest="literature_command")

    lit_init = lit_sub.add_parser(
        "init",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="create missing literature folders without changing existing files",
        description="Create the base literature folders.",
        epilog="""Behavior:
  Existing folders are reported as ok and left unchanged.
  Missing folders are created.
  No files are deleted, emptied, overwritten, renamed, or reorganized.
""",
    )
    lit_init.set_defaults(func=command_literature_init)

    lit_search_arxiv = lit_sub.add_parser(
        "search-arxiv",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="search arXiv metadata by keywords and filters",
        epilog="""Examples:
  ws literature search-arxiv spin qubit --author Loss --category quant-ph
  ws literature search-arxiv --title "quantum chemistry" --abstract variational --max 5
""",
    )
    lit_search_arxiv.add_argument("query", nargs="*", help="general keyword terms searched with arXiv all:")
    lit_search_arxiv.add_argument("--author", help="author keyword filter")
    lit_search_arxiv.add_argument("--title", help="title keyword filter")
    lit_search_arxiv.add_argument("--abstract", help="abstract keyword filter")
    lit_search_arxiv.add_argument("--category", help="arXiv category such as quant-ph, cs.AI, or physics.chem-ph")
    lit_search_arxiv.add_argument("--max", dest="max_results", type=int, default=10, help="maximum results to print; default: 10")
    lit_search_arxiv.add_argument("--start", type=int, default=0, help="zero-based result offset; default: 0")
    lit_search_arxiv.add_argument("--sort", choices=["relevance", "lastUpdatedDate", "submittedDate"], default="relevance",
                                  help="result order (default relevance)")
    lit_search_arxiv.set_defaults(func=command_literature_search_arxiv)

    lit_enrich = lit_sub.add_parser("enrich", help="add source-backed citation facts when found")
    lit_enrich.add_argument("ref", metavar="REF", help="canonical literature:<key> reference")
    lit_enrich.add_argument("--arxiv", action="store_true", help="search arXiv and write source/arxiv/citation.bib without changing the main citation")
    lit_enrich.add_argument("--arxiv-id", help="known arXiv ID or URL to use instead of DOI/title search")
    lit_enrich.set_defaults(func=command_literature_enrich)

    lit_download_source = lit_sub.add_parser("download-source", help="download the latest arXiv source files for one item")
    lit_download_source.add_argument("ref", metavar="REF", help="canonical literature:<key> reference")
    lit_download_source.add_argument("--arxiv", action="store_true", help=argparse.SUPPRESS)
    lit_download_source.add_argument("--force", action="store_true", help="overwrite an existing source package or extracted files")
    lit_download_source.add_argument("--no-extract", action="store_true", help="download the source package without extracting it")
    lit_download_source.set_defaults(func=command_literature_download_source)

    lit_download_pdf = lit_sub.add_parser(
        "download-pdf",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="download a PDF for one item",
        description="Download paper.pdf for one item.",
        epilog="""Default behavior:
  Try an open-access PDF for the main DOI.
  If no open-access PDF is found, use the latest arXiv PDF when available.

Modes:
  --open-or-arxiv  explicit default behavior
  --arxiv          force latest arXiv PDF
  --url URL        attach from a known direct PDF URL
""",
    )
    lit_download_pdf.add_argument("ref", metavar="REF", help="canonical literature:<key> reference")
    pdf_mode = lit_download_pdf.add_mutually_exclusive_group()
    pdf_mode.add_argument("--open-or-arxiv", action="store_true", help="try open-access DOI PDF, then latest arXiv PDF")
    pdf_mode.add_argument("--arxiv", action="store_true", help="download the latest arXiv PDF")
    pdf_mode.add_argument("--url", help="direct PDF URL")
    lit_download_pdf.add_argument("--name", help="destination PDF filename; defaults to paper.pdf")
    lit_download_pdf.add_argument("--force", action="store_true", help="overwrite an existing destination file")
    lit_download_pdf.set_defaults(func=command_literature_download_pdf)

    lit_attach_pdf = lit_sub.add_parser("attach-pdf", help="copy a PDF into an item folder")
    lit_attach_pdf.add_argument("ref", metavar="REF", help="canonical literature:<key> reference")
    lit_attach_pdf.add_argument("path")
    lit_attach_pdf.add_argument("--name", help="destination PDF filename; defaults to paper.pdf")
    lit_attach_pdf.add_argument("--force", action="store_true", help="overwrite an existing destination file")
    lit_attach_pdf.set_defaults(func=command_literature_attach_pdf)

    lit_attach_source = lit_sub.add_parser("attach-source", help="copy TeX/arXiv source into an item source folder")
    lit_attach_source.add_argument("ref", metavar="REF", help="canonical literature:<key> reference")
    lit_attach_source.add_argument("path")
    lit_attach_source.add_argument("--force", action="store_true", help="overwrite files or merge into an existing source directory")
    lit_attach_source.set_defaults(func=command_literature_attach_source)

    lit_taxonomy = lit_sub.add_parser(
        "taxonomy",
        help="show the allowed classifier values",
    )
    lit_taxonomy.set_defaults(func=command_literature_taxonomy)

    lit_add_field = lit_sub.add_parser(
        "add-field",
        help="add a field to the shared workspace vocabulary",
    )
    lit_add_field.add_argument("value")
    lit_add_field.set_defaults(func=command_literature_add_field)

    lit_add_subfield = lit_sub.add_parser(
        "add-subfield",
        help="add a field-specific subfield to the shared taxonomy",
    )
    lit_add_subfield.add_argument("field")
    lit_add_subfield.add_argument("value")
    lit_add_subfield.set_defaults(func=command_literature_add_subfield)

    lit_views = lit_sub.add_parser(
        "views",
        help="manage derived by-author, by-field, and by-year views",
    )
    views_actions = lit_views.add_subparsers(
        dest="literature_views_command",
        required=True,
    )
    views_rebuild = views_actions.add_parser("rebuild", help="rebuild the derived by-* browse views from current data")
    views_rebuild.add_argument("--json", action="store_true")
    views_rebuild.set_defaults(func=command_literature_views_rebuild)

    lit_citations = lit_sub.add_parser(
        "citations",
        help="list the works one item cites, from its references.txt",
    )
    lit_citations.add_argument("ref", metavar="REF", help="canonical literature:<key> reference")
    lit_citations.add_argument(
        "--in-library",
        action="store_true",
        help="print only cited works held in the library, as canonical REFs",
    )
    lit_citations.add_argument(
        "--fetch",
        action="store_true",
        help="fetch references from Semantic Scholar, falling back to OpenAlex",
    )
    lit_citations.set_defaults(func=command_literature_citations)

    lit_cited_by = lit_sub.add_parser(
        "cited-by",
        help="list library items whose references include this item",
    )
    lit_cited_by.add_argument("ref", metavar="REF", help="canonical literature:<key> reference")
    lit_cited_by.set_defaults(func=command_literature_cited_by)
