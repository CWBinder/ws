import argparse
import contextlib
import datetime as dt
import io
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from ws_lib import config as ws_config
from ws_lib import paths, yamlish


WORKSPACE = paths.WORKSPACE
SYSTEM = paths.SYSTEM
TEMPLATES = paths.TEMPLATES
PROJECTS = paths.PROJECTS
LITERATURE_ITEMS = paths.LITERATURE_ITEMS
CONTRACTS = paths.CONTRACTS
PROJECT_TAXONOMY = paths.PROJECT_TAXONOMY
PROJECT_SETUP_DOC = paths.PROJECT_SETUP_DOC

PROJECT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PROJECT_STATUSES = ["idea", "active", "paused", "complete", "archived"]
PROJECT_DEPENDENCY_KINDS = ["package"]
DEFAULT_TAXONOMY = {
    "type": ["research", "paper", "talk", "software", "teaching", "organizatorial", "other"],
    "fields": ["physics", "mathematics", "computer-science", "ai", "humanities"],
    "subfields": {
        "physics": [
            "quantum-information", "quantum-computing", "spin-qubits", "shuttling",
            "numerics", "quantum-chemistry", "experimental",
        ],
        "mathematics": ["tooling", "numerics"],
        "computer-science": ["tooling"],
        "ai": [],
        "humanities": [],
    },
}

PROJECT_TAXONOMY_HEADER = [
    "Edit this file directly, or use:",
    "  ws projects add-type <type>",
    "  ws projects add-field <field>   (or ws literature add-field)",
    "  ws projects add-subfield <field> <subfield>",
    "The create and add wizards also offer to add unknown values here.",
    "",
    "Projects and literature share broad fields and field-specific subfields.",
    "Objects may select several of each, but every selected subfield must",
    "belong to at least one selected field. Keywords remain free-form.",
]


def today() -> str:
    return dt.date.today().isoformat()


def requested_project_dirs(has_code: bool, has_paper: bool, has_data: bool) -> list[str]:
    return [
        folder
        for folder, enabled in (
            ("code", has_code),
            ("paper", has_paper),
            ("data", has_data),
        )
        if enabled
    ]


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


def write_new(path: Path, content: str) -> None:
    if path.exists():
        print(f"exists: {rel_home(path)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"created: {rel_home(path)}")


def slug_value(value: str) -> str:
    value = value.strip().lower()
    if not PROJECT_RE.match(value):
        fail("value must be lowercase kebab-case")
    return value


def project_slug(value: str | list[str]) -> str:
    raw = " ".join(value) if isinstance(value, list) else value
    raw = raw.strip()
    if not raw:
        fail("project name is required")
    candidate = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if not PROJECT_RE.match(candidate):
        fail("project name must contain at least one letter or number")
    return candidate


def project_path_slug(value: str | list[str]) -> str:
    """Slugify a subproject name that may be a nested path (`group/leaf`).

    Each `/`-separated segment is slugified independently and rejoined.
    Subprojects may sit inside plain grouping folders within their parent
    project; the top-level projects store itself is flat and refuses paths."""
    raw = " ".join(value) if isinstance(value, list) else value
    segments = [seg for seg in raw.strip().strip("/").split("/") if seg.strip()]
    if not segments:
        fail("project name is required")
    return "/".join(project_slug(seg) for seg in segments)


def project_title(slug: str, explicit_title: str | None) -> str:
    if explicit_title:
        return explicit_title
    return slug.replace("-", " ").title()


def use_projects_dir(args: argparse.Namespace) -> None:
    path = getattr(args, "projects_dir", None)
    if not path:
        return
    global PROJECTS
    PROJECTS = Path(path).expanduser()


def load_taxonomy() -> dict:
    from ws_lib import taxonomy

    return taxonomy.load(PROJECT_TAXONOMY, DEFAULT_TAXONOMY)


def add_taxonomy_value(key: str, value: str) -> None:
    from ws_lib import taxonomy

    taxonomy.add(PROJECT_TAXONOMY, DEFAULT_TAXONOMY, PROJECT_TAXONOMY_HEADER, key, value)


def subfield_map(data: dict | None = None) -> dict[str, list[str]]:
    value = (data or load_taxonomy()).get("subfields", {})
    if not isinstance(value, dict):
        return {}
    return {
        str(parent): [str(child) for child in children]
        for parent, children in value.items()
        if isinstance(children, list)
    }


def all_subfields(data: dict | None = None) -> list[str]:
    return list(dict.fromkeys(
        child
        for children in subfield_map(data).values()
        for child in children
    ))


def compatible_subfields(fields: list[str], data: dict | None = None) -> list[str]:
    mapping = subfield_map(data)
    return list(dict.fromkeys(
        child for field in fields for child in mapping.get(field, [])
    ))


def classification_problems(
    fields: list[str], subfields: list[str], data: dict | None = None
) -> list[str]:
    taxonomy_data = data or load_taxonomy()
    allowed_fields = taxonomy_data.get("fields", [])
    allowed_fields = allowed_fields if isinstance(allowed_fields, list) else []
    unknown_fields = [value for value in fields if value not in allowed_fields]
    known_subfields = all_subfields(taxonomy_data)
    unknown_subfields = [value for value in subfields if value not in known_subfields]
    compatible = set(compatible_subfields(fields, taxonomy_data))
    incompatible = [
        value for value in subfields
        if value in known_subfields and value not in compatible
    ]
    problems = []
    if unknown_fields:
        problems.append(f"unknown field(s): {', '.join(unknown_fields)}")
    if unknown_subfields:
        problems.append(f"unknown subfield(s): {', '.join(unknown_subfields)}")
    if incompatible:
        problems.append(
            "subfield(s) do not belong to a selected field: "
            + ", ".join(incompatible)
        )
    return problems


def taxonomy_problems(data: dict | None = None) -> list[str]:
    """Return structural problems in the shared field/subfield taxonomy."""
    taxonomy_data = data or load_taxonomy()
    fields = taxonomy_data.get("fields", [])
    fields = fields if isinstance(fields, list) else []
    mapping = subfield_map(taxonomy_data)
    problems: list[str] = []
    unknown_parents = [parent for parent in mapping if parent not in fields]
    if unknown_parents:
        problems.append(
            "subfield group(s) have unknown parent fields: "
            + ", ".join(unknown_parents)
        )
    duplicate_fields = sorted({value for value in fields if fields.count(value) > 1})
    if duplicate_fields:
        problems.append(f"duplicate field(s): {', '.join(duplicate_fields)}")
    for parent, children in mapping.items():
        duplicates = sorted({value for value in children if children.count(value) > 1})
        if duplicates:
            problems.append(
                f"duplicate subfield(s) under {parent}: {', '.join(duplicates)}"
            )
    return problems


def add_subfield(field: str, value: str) -> None:
    from ws_lib import taxonomy

    field_id = taxonomy.slug(field)
    fields = load_taxonomy().get("fields", [])
    if not isinstance(fields, list) or field_id not in fields:
        fail(f"unknown parent field: {field} (add it with `ws projects add-field`)")
    taxonomy.add_nested(
        PROJECT_TAXONOMY,
        DEFAULT_TAXONOMY,
        PROJECT_TAXONOMY_HEADER,
        "subfields",
        field_id,
        value,
    )


def yaml_scalar(value: str) -> str:
    if value == "":
        return '""'
    if re.match(r"^[A-Za-z0-9.][A-Za-z0-9 _./:@+-]*$", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(yaml_scalar(value) for value in values) + "]"


def yaml_project_dependencies(dependencies: list[dict[str, str]]) -> str:
    if not dependencies:
        return "project_dependencies: []"
    lines = ["project_dependencies:"]
    for dep in dependencies:
        lines.append(f"  - project: {yaml_scalar(dep['project'])}")
        lines.append(f"    kind: {dep['kind']}")
        lines.append("    install: editable")
        lines.append(f"    path: {yaml_scalar(dep.get('path') or '.')}")
    return "\n".join(lines)


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        print()
        return default
    return value or default


def match_choice(value: str, options: list[str]) -> str:
    value = value.strip()
    if not value:
        return ""
    if value in options:
        return value
    matches = [option for option in options if option.startswith(value)]
    return matches[0] if len(matches) == 1 else ""


def ask_choice(prompt: str, options: list[str], default: str, taxonomy_key: str = "") -> str:
    print(f"{prompt} options: {', '.join(options)}")
    while True:
        raw = ask(prompt, default)
        choice = match_choice(raw, options)
        if choice:
            return choice
        if taxonomy_key and raw and ask_bool(f"Add '{slug_value(raw)}' to the available {prompt.lower()}s?"):
            add_taxonomy_value(taxonomy_key, raw)
            options.append(slug_value(raw))
            return slug_value(raw)
        print(f"Invalid {prompt.lower()}: {raw}. Choose one of: {', '.join(options)}")


def ask_list(prompt: str, options: list[str], default_values: list[str], taxonomy_key: str = "") -> list[str]:
    if options:
        print(f"{prompt} options: {', '.join(options)}")
    while True:
        raw = ask(f"{prompt}, comma-separated", ", ".join(default_values))
        values = [item.strip() for item in raw.split(",") if item.strip()]
        if not options:
            return values
        normalized = []
        invalid = []
        for value in values:
            choice = match_choice(value, options)
            if choice:
                normalized.append(choice)
            elif taxonomy_key and ask_bool(f"Add '{slug_value(value)}' to the available {prompt.lower()}?"):
                add_taxonomy_value(taxonomy_key, value)
                options.append(slug_value(value))
                normalized.append(slug_value(value))
            else:
                invalid.append(value)
        if not invalid:
            return normalized
        print(f"Invalid {prompt.lower()}: {', '.join(invalid)}. Choose from: {', '.join(options)}")


def ask_bool(prompt: str, default: bool = False) -> bool:
    default_text = "y" if default else "n"
    try:
        value = input(f"{prompt} [{default_text}]: ").strip().lower()
    except EOFError:
        print()
        return default
    if not value:
        return default
    return value in {"y", "yes", "true", "1"}


def ask_bool_or_ref(prompt: str, default: bool = False) -> tuple[bool, str]:
    """Yes/no prompt where any other answer is kept as a REF and counts as yes."""
    default_text = "y" if default else "n"
    try:
        value = input(f"{prompt} [{default_text}]: ").strip()
    except EOFError:
        print()
        return default, ""
    if not value:
        return default, ""
    if value.lower() in {"y", "yes", "true", "1"}:
        return True, ""
    if value.lower() in {"n", "no", "false", "0"}:
        return False, ""
    return True, value


def setup_flags_present(args: argparse.Namespace) -> bool:
    for attr in [
        "title", "type", "status", "description", "field", "keyword",
        "depends_on", "related", "literature", "host", "use_project",
    ]:
        if getattr(args, attr, None):
            return True
    for attr in ["has_code", "has_paper", "has_data", "has_slides", "server_compute", "python", "venv"]:
        if bool(getattr(args, attr, False)):
            return True
    return False


def should_prompt_for_project_setup(args: argparse.Namespace) -> bool:
    if getattr(args, "non_interactive", False):
        return False
    if getattr(args, "interactive", False):
        return True
    return not setup_flags_present(args) and sys.stdin.isatty()


# Which optional wizard questions fit each project type. Flags stay available
# for every type; this only trims the interview. User-extended types get the
# full battery so nothing is silently skipped.
FULL_QUESTION_SET = frozenset({
    "code", "python", "venv", "deps", "paper", "data", "slides", "server",
})
TYPE_QUESTION_SETS = {
    "research": {"code", "python", "venv", "deps", "data", "server"},
    "paper": {"code", "python", "venv", "deps"},
    "talk": {"slides"},
    "software": {"code", "python", "venv", "deps"},
    "teaching": {"slides"},
    "organizatorial": set(),
    "other": set(),
}


def wizard_question_set(project_type: str) -> set[str]:
    return set(TYPE_QUESTION_SETS.get(project_type, FULL_QUESTION_SET))


def _relate_project_links(relpath: str, depends_on: list[str], related: list[str]) -> None:
    """Create depends-on / related edges for a new project. Endpoints resolve
    through the catalog (any kind), so a typo is noted and skipped rather
    than aborting a creation that already happened."""
    from ws_lib import catalog, relations

    subject = f"project:{relpath}"
    for relation, values in (("depends-on", depends_on), ("related", related)):
        for value in values:
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    target = catalog.resolve(value)
            except SystemExit:
                print(
                    f"note: {relation} target not found, edge skipped: {value}",
                    file=sys.stderr,
                )
                continue
            if target.id == subject:
                continue
            row, created = relations.create(subject, target.id, relation)
            print(
                f"{'created' if created else 'exists'}: {row['id']} "
                f"{subject} --{relation}--> {target.id}"
            )


def parse_project_dependency(value: str) -> dict[str, str]:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) < 2 or parts[0] != "project" or not parts[1]:
        fail("--use-project must be project:<key>[:package[:path]]")
    project_name = project_key_from_ref(f"project:{parts[1]}")
    kind = parts[2] if len(parts) > 2 and parts[2] else "package"
    if kind not in PROJECT_DEPENDENCY_KINDS:
        fail(
            f"--use-project kind must be: {', '.join(PROJECT_DEPENDENCY_KINDS)}"
            " — a conceptual reference is an edge: ws relate <project> to <other> as depends-on"
        )
    path = ":".join(parts[3:]) if len(parts) > 3 and any(parts[3:]) else "."
    return {"project": project_name, "kind": kind, "path": path}


def parse_project_dependencies(values: list[str] | None) -> list[dict[str, str]]:
    dependencies: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for value in values or []:
        dep = parse_project_dependency(value)
        identity = (dep["project"], dep["kind"], dep.get("path") or dep.get("command") or "")
        if identity not in seen:
            dependencies.append(dep)
            seen.add(identity)
    return dependencies


def package_dependency_path(dep: dict[str, str]) -> Path:
    return PROJECTS / dep["project"] / dep.get("path", ".")


def suggest_package_dependency_path(project_name: str) -> str:
    root = PROJECTS / project_name
    if (root / "pyproject.toml").exists():
        return "."
    candidates = [
        path.parent.relative_to(root)
        for path in root.glob("*/pyproject.toml")
        if path.parent.name not in {".venv", "venv"}
    ]
    if len(candidates) == 1:
        return str(candidates[0])
    return "."


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / ".venv" / "Scripts" / "python.exe"
    return root / ".venv" / "bin" / "python"


def editable_install_preview(dep: dict[str, str]) -> str:
    python = ".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python"
    return f"{python} -m pip install -e {rel_home(package_dependency_path(dep))}"


def print_package_dependency_preview(dep: dict[str, str]) -> None:
    target = package_dependency_path(dep)
    pyproject = target / "pyproject.toml"
    if pyproject.exists():
        print("Found Python package:")
        print(f"  {rel_home(pyproject)}")
    else:
        print("No pyproject.toml found at:")
        print(f"  {rel_home(pyproject)}")
        print("You can still record this dependency, but editable install may fail until that path is corrected.")
    steps = dependency_install_steps(dep)
    if steps:
        print("Custom install steps (declared in that project's project.yaml):")
        for step in steps:
            print(f"  {step}")
    else:
        print("Editable install command:")
        print(f"  {editable_install_preview(dep)}")


def ask_package_dependency(ref: str = "") -> dict[str, str]:
    project_name = project_key_from_ref(ref or ask("Project REF to install"))
    install_path = suggest_package_dependency_path(project_name)
    target = PROJECTS / project_name / install_path
    if not (target / "pyproject.toml").exists():
        install_path = ask("Path inside that project to install", install_path)
    dep = {"project": project_name, "kind": "package", "path": install_path or "."}
    print_package_dependency_preview(dep)
    if not ask_bool("Run this after creating the venv", True):
        dep["_install_now"] = "false"
    return dep


def ask_project_dependencies(venv_enabled: bool, existing: list[dict[str, str]]) -> tuple[bool, list[dict[str, str]]]:
    dependencies = list(existing)
    if not venv_enabled:
        return venv_enabled, dependencies
    proceed, ref = ask_bool_or_ref("Install another workspace project into this venv", False)
    while proceed:
        dependencies.append(ask_package_dependency(ref))
        proceed, ref = ask_bool_or_ref("Install another workspace project into this venv", False)
    return venv_enabled, dependencies


def create_python_project_files(root: Path, name: str) -> None:
    template = read(TEMPLATES / "pyproject.toml").replace("project-name", name)
    write_new(root / "pyproject.toml", template)


def create_venv(root: Path) -> None:
    venv_root = root / ".venv"
    if venv_root.exists():
        print(f"exists: {rel_home(venv_root)}/")
        return
    result = subprocess.run([sys.executable, "-m", "venv", str(venv_root)], cwd=root, check=False)
    if result.returncode == 0:
        print(f"created: {rel_home(venv_root)}/")
    else:
        print(f"warning: could not create virtual environment at {rel_home(venv_root)}", file=sys.stderr)


DEFAULT_INSTALL_STEPS = ["{python} -m pip install -e {path}"]


def dependency_install_steps(dep: dict[str, str]) -> list[str]:
    """Custom install recipe declared by the dependency project itself, if any."""
    meta = parse_project_yaml(PROJECTS / dep["project"] / "project.yaml")
    return meta.get("package_install", [])


def render_install_step(step: str, python: Path, dep_path: Path) -> str:
    return step.replace("{python}", shlex.quote(str(python))).replace("{path}", shlex.quote(str(dep_path)))


def install_package_project_dependencies(root: Path, dependencies: list[dict[str, str]]) -> None:
    python = venv_python(root)
    if not python.exists():
        if any(dep.get("kind") == "package" for dep in dependencies):
            print(f"warning: no virtual environment at {rel_home(root / '.venv')}; package dependencies not installed", file=sys.stderr)
        return
    for dep in dependencies:
        if dep["kind"] != "package":
            continue
        if dep.get("_install_now") == "false":
            print(f"skipped editable dependency install: {dep['project']}")
            continue
        dep_path = package_dependency_path(dep)
        if not dep_path.exists():
            print(f"warning: package dependency path does not exist: {rel_home(dep_path)}", file=sys.stderr)
            continue
        failed = False
        for step in dependency_install_steps(dep) or DEFAULT_INSTALL_STEPS:
            rendered = render_install_step(step, python, dep_path)
            print(f"running: {rendered}")
            result = subprocess.run(shlex.split(rendered), cwd=root, check=False)
            if result.returncode != 0:
                print(f"warning: install step failed for {dep['project']}: {rendered}", file=sys.stderr)
                failed = True
                break
        if not failed:
            print(f"installed editable dependency: {dep['project']} ({rel_home(dep_path)})")


# The brand-free slide_factory engine ships with ws, next to cli/.
SLIDE_GENERATOR_PATH = Path(__file__).resolve().parents[2] / "packages" / "slide_factory"


def slide_theme_paths() -> list[Path]:
    """Theme packages named under `slides.themes` in the private ws
    configuration: project REFs (`project:<key>`) or filesystem paths.
    Branding lives there, never in the ws repository."""
    configured = ws_config.get("slides.themes") or []
    if isinstance(configured, str):
        configured = [configured]
    found: list[Path] = []
    for entry in configured:
        if isinstance(entry, dict) and len(entry) == 1:  # block-list `- project:key`
            (key, value), = entry.items()
            entry = f"{key}:{value}"
        entry = str(entry).strip()
        if not entry:
            continue
        if entry.startswith("project:"):
            name = entry.split(":", 1)[1]
            path = PROJECTS / name / suggest_package_dependency_path(name)
        else:
            path = Path(entry).expanduser()
        if (path / "pyproject.toml").exists():
            found.append(path)
        else:
            print(f"warning: slide theme package not found: {entry} ({rel_home(path)}); skipped", file=sys.stderr)
    return found


def install_slide_factory(root: Path) -> None:
    """Editable-install the slide_factory engine shipped with ws, then any
    configured theme packages, into the project's venv."""
    python = venv_python(root)
    if not python.exists():
        print(f"warning: no virtual environment at {rel_home(root / '.venv')}; slide generator not installed", file=sys.stderr)
        return
    if not (SLIDE_GENERATOR_PATH / "pyproject.toml").exists():
        print(f"warning: slide generator not found at {rel_home(SLIDE_GENERATOR_PATH)}; skipped", file=sys.stderr)
        return
    for label, path in [("slide generator", SLIDE_GENERATOR_PATH)] + [("slide themes", p) for p in slide_theme_paths()]:
        rendered = f"{shlex.quote(str(python))} -m pip install -e {shlex.quote(str(path))}"
        print(f"running: {rendered}")
        result = subprocess.run(shlex.split(rendered), cwd=root, check=False)
        if result.returncode != 0:
            print(f"warning: {label} install failed: {rendered}", file=sys.stderr)
        else:
            print(f"installed {label}: {rel_home(path)}")


INSTALL_FEATURES = ("code", "paper", "data", "python", "venv", "slides")
# Mirrors the creation chain: slides need a venv, a venv means a Python
# project, and Python code lives in code/.
FEATURE_IMPLIES = {
    "python": ("code",),
    "venv": ("python",),
    "slides": ("venv",),
}
CAPABILITY_KEY_ORDER = ("has_code", "has_paper", "has_data", "has_slides", "server_compute")
RUNTIME_KEY_ORDER = ("python", "venv")


def feature_closure(features: list[str]) -> set[str]:
    resolved: set[str] = set()
    queue = list(features)
    while queue:
        feature = queue.pop()
        if feature not in resolved:
            resolved.add(feature)
            queue.extend(FEATURE_IMPLIES.get(feature, ()))
    return resolved


def _set_yaml_key(lines: list[str], key: str, value: str, order: tuple[str, ...], indent: str = "", start: int = 0, end: int | None = None) -> bool:
    """Set `<indent><key>: <value>` inside lines[start:end], preserving all
    other text. A missing key is inserted after the nearest preceding key
    from `order`, so files predating the key end up in canonical shape."""
    stop = len(lines) if end is None else end
    prefix = f"{indent}{key}:"
    rendered = f"{indent}{key}: {value}"
    for i in range(start, stop):
        if lines[i] == rendered:
            return False
        if lines[i].startswith(prefix):
            lines[i] = rendered
            return True
    anchors = tuple(reversed(order[: order.index(key)])) if key in order else ()
    for anchor in anchors:
        anchor_prefix = f"{indent}{anchor}:"
        for i in range(start, stop):
            if lines[i].startswith(anchor_prefix):
                lines.insert(i + 1, rendered)
                return True
    lines.insert(stop, rendered)
    return True


def update_project_yaml_capabilities(root: Path, top: dict[str, str], runtime: dict[str, str]) -> None:
    """Record capability keys in project.yaml while preserving all other text."""
    path = root / "project.yaml"
    lines = read(path).splitlines()
    changed = False
    for key, value in top.items():
        changed = _set_yaml_key(lines, key, value, CAPABILITY_KEY_ORDER) or changed
    if runtime:
        block = next((i for i, line in enumerate(lines) if line.startswith("runtime:")), None)
        if block is None:
            lines.extend(["", "runtime:"])
            block = len(lines) - 1
        for key, value in runtime.items():
            end = block + 1
            while end < len(lines) and lines[end].startswith("  "):
                end += 1
            changed = _set_yaml_key(lines, key, value, RUNTIME_KEY_ORDER, indent="  ", start=block + 1, end=end) or changed
    if changed:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"updated: {rel_home(path)}")


def record_project_dependencies(root: Path, dependencies: list[dict[str, str]]) -> list[dict[str, str]]:
    """Append new package dependencies to project.yaml, preserving all other
    text. Entries already recorded (same project, kind, path) are skipped."""
    path = root / "project.yaml"
    recorded = parse_project_yaml(path).get("project_dependencies", [])
    seen = {(dep.get("project", ""), dep.get("kind", ""), dep.get("path") or ".") for dep in recorded}
    added: list[dict[str, str]] = []
    for dep in dependencies:
        identity = (dep["project"], dep["kind"], dep.get("path") or ".")
        if identity in seen:
            print(f"already recorded: {dep['project']}")
            continue
        seen.add(identity)
        added.append(dep)
    if not added:
        return []
    lines = read(path).splitlines()
    entry_lines = [line for dep in added for line in yaml_project_dependencies([dep]).splitlines()[1:]]
    key_index = next((i for i, line in enumerate(lines) if line.startswith("project_dependencies:")), None)
    if key_index is None:
        lines.extend(["", "project_dependencies:"] + entry_lines)
    elif lines[key_index].strip() == "project_dependencies: []":
        lines[key_index:key_index + 1] = ["project_dependencies:"] + entry_lines
    else:
        end = key_index + 1
        while end < len(lines) and lines[end].startswith("  "):
            end += 1
        lines[end:end] = entry_lines
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for dep in added:
        print(f"recorded dependency: {dep['project']}")
    return added


def converge_project_installs(root: Path) -> bool:
    """(Re)materialize what project.yaml records: capability folders, Python
    scaffolding, the venv, package dependencies, and the slide generator.
    Returns False when the file records nothing installable."""
    meta = parse_project_yaml(root / "project.yaml")
    runtime = meta.get("runtime", {})
    wanted_dirs = requested_project_dirs(
        meta["has_code"] == "true", meta["has_paper"] == "true", meta["has_data"] == "true"
    )
    python_wanted = runtime.get("python") == "true"
    venv_wanted = bool(runtime.get("venv"))
    dependencies = [dep for dep in meta.get("project_dependencies", []) if dep.get("kind") == "package"]
    slides_wanted = meta["has_slides"] == "true"
    if not (wanted_dirs or python_wanted or venv_wanted or dependencies or slides_wanted):
        return False
    for folder in wanted_dirs:
        path = root / folder
        if path.exists():
            print(f"exists: {rel_home(path)}/")
        else:
            path.mkdir()
            print(f"created: {rel_home(path)}/")
    if python_wanted:
        create_python_project_files(root, root.name)
    if venv_wanted or dependencies or slides_wanted:
        create_venv(root)
    if dependencies:
        install_package_project_dependencies(root, dependencies)
    if slides_wanted:
        install_slide_factory(root)
    return True


def copy_template(src_name: str, dest: Path, replacements: dict[str, str]) -> None:
    src = TEMPLATES / src_name
    if not src.exists():
        fail(f"missing template: {rel_home(src)}")
    content = read(src)
    for key, value in replacements.items():
        content = content.replace(key, value)
    write_new(dest, content)


def write_claude_md(root: Path) -> None:
    """Create CLAUDE.md as a symlink to AGENTS.md; fall back to an @AGENTS.md import (e.g. on Windows)."""
    target = root / "CLAUDE.md"
    label = f"{rel_home(root)}/CLAUDE.md"
    if target.exists() or target.is_symlink():
        print(f"exists: {label}")
        return
    try:
        os.symlink("AGENTS.md", target)
        print(f"linked: {label} -> AGENTS.md")
    except OSError:
        target.write_text("@AGENTS.md\n", encoding="utf-8")
        print(f"created: {label} (import)")


PROJECT_SCAN_DEPTH = 6


def project_relpaths(base: Path | None = None) -> list[str]:
    """Projects under the projects store, as POSIX paths relative to it.

    The store is flat: `ws projects create` only writes directly into it, so
    projects normally sit at depth 1. Discovery stays a tolerant walk so
    hand-nested legacy projects are still found (reading is lenient, writing
    is strict): any directory holding a project.yaml is a project, and
    discovery does not descend into it (a project's own subfolders are never
    sub-projects). Noise/dependency dirs and anything past PROJECT_SCAN_DEPTH
    are skipped so a large store stays cheap."""
    root = base or PROJECTS
    if not root.exists():
        return []
    skip = {".git", ".venv", "venv", "node_modules", "__pycache__", "out", "tmp"}
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        if "project.yaml" in filenames:
            found.append(rel.as_posix())
            dirnames[:] = []
            continue
        if depth >= PROJECT_SCAN_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
    return sorted(found)


def existing_project_names() -> list[str]:
    return project_relpaths()


def normalize_ref(ref: str, known) -> Optional[str]:
    """Canonical project relpath for a reference: exact match, else unique leaf."""
    ref = ref.strip()
    if ref in known:
        return ref
    leaves = [name for name in known if name.rsplit("/", 1)[-1] == ref]
    return leaves[0] if len(leaves) == 1 else None


def find_enclosing_project(start: Optional[Path] = None) -> Optional[Path]:
    """Return the closest ancestor directory (including start) holding a project.yaml."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "project.yaml").exists():
            return candidate
    return None


def _loose_slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def resolve_dependency_name(value: str) -> str:
    """Prefer an existing project's path (exact or unique leaf); keep the slug for not-yet-created projects."""
    raw = value.strip()
    names = existing_project_names()
    canon = normalize_ref(raw, names)
    if canon:
        return canon
    wanted = _loose_slug(raw)
    matches = [name for name in names if _loose_slug(name) == wanted or _loose_slug(name.rsplit("/", 1)[-1]) == wanted]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        fail(f"ambiguous project name '{raw}': matches {', '.join(matches)}")
    return project_slug(raw)


def resolve_project_name(value: str | list[str]) -> str:
    """Map user input to an existing project's path (relative to the projects
    store). The store is flat, so identity is normally the bare folder name;
    hand-nested legacy projects keep a relative path as identity. Resolution
    order: exact path, unique leaf name, then a slug-normalized comparison on
    either the path or the leaf. Pre-existing folders may be capitalized or
    spaced, which the slug comparison absorbs."""
    raw = " ".join(value) if isinstance(value, list) else value
    raw = raw.strip().strip("/")
    if not raw:
        fail("project name is required")
    names = existing_project_names()
    if raw in names:
        return raw
    leaves = [name for name in names if name.rsplit("/", 1)[-1] == raw]
    if len(leaves) == 1:
        return leaves[0]
    if len(leaves) > 1:
        fail(f"ambiguous project name '{raw}': matches {', '.join(leaves)}")
    wanted_path = "/".join(_loose_slug(seg) for seg in raw.split("/") if seg)
    wanted = _loose_slug(raw)
    matches = sorted({
        name for name in names
        if name == wanted_path
        or _loose_slug(name) == wanted
        or _loose_slug(name.rsplit("/", 1)[-1]) == wanted
    })
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        fail(f"ambiguous project name '{raw}': matches {', '.join(matches)}")
    fail(f"project does not exist: {raw}")


def project_key_from_ref(value: str) -> str:
    from ws_lib import catalog

    return catalog.resolve(value, "project").key


def existing_literature_keys() -> list[str]:
    if not LITERATURE_ITEMS.exists():
        return []
    return sorted(
        path.name
        for path in LITERATURE_ITEMS.iterdir()
        if path.is_dir() and (path / "citation.bib").exists()
    )


def git_ignored(root: Path, path: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-q", str(rel)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def scan_project(root: Path) -> tuple[list[Path], list[Path], list[tuple[Path, int]]]:
    """Walk a project repo, pruning ignored dirs so findings are not-ignored by construction."""
    nested_repos: list[Path] = []
    agent_dirs: list[Path] = []
    large_files: list[tuple[Path, int]] = []
    limit = 5 * 1024 * 1024
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        if dp != root and ".git" in dirnames:
            nested_repos.append(dp)
            dirnames[:] = []
            continue
        kept: list[str] = []
        for name in dirnames:
            if dp == root and name == ".git":
                continue
            full = dp / name
            if git_ignored(root, full):
                continue
            if name in (".claude", ".codex"):
                agent_dirs.append(full)
                continue
            kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            fp = dp / name
            try:
                size = fp.stat().st_size
            except OSError:
                continue
            if size > limit and not git_ignored(root, fp):
                large_files.append((fp, size))
    return nested_repos, agent_dirs, large_files


def validate_claude_md(root: Path) -> Optional[str]:
    claude = root / "CLAUDE.md"
    agents = root / "AGENTS.md"
    if not claude.exists() and not claude.is_symlink():
        return "missing CLAUDE.md"
    if claude.is_symlink():
        target = os.readlink(claude)
        if claude.resolve(strict=False) == agents.resolve(strict=False):
            return None
        return f"CLAUDE.md symlink points to {target}, expected AGENTS.md"
    try:
        content = read(claude)
    except OSError as exc:
        return f"cannot read CLAUDE.md: {exc}"
    if any(line.strip() == "@AGENTS.md" for line in content.splitlines()):
        return None
    return "CLAUDE.md is not a symlink to AGENTS.md or an @AGENTS.md import"


def _yaml_text(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _normalize_mapping(data: dict) -> dict:
    return {key: value if isinstance(value, (list, dict)) else _yaml_text(value) for key, value in data.items()}


def parse_project_yaml(path: Path) -> dict:
    meta: dict = {
        "created": "",
        "title": "",
        "type": "",
        "status": "",
        "fields": [],
        "subfields": [],
        "keywords": [],
        "depends_on": [],
        "related": [],
        "related_literature": [],
        "has_code": "",
        "has_paper": "",
        "has_data": "",
        "has_slides": "",
        "server_compute": "",
        "runtime": {},
        "project_dependencies": [],
        "package_install": [],
        "hosts": [],
        "sync": None,
    }
    if not path.exists():
        return meta
    data = yamlish.load_mapping(read(path))
    scalar_keys = {"created", "title", "type", "status", "has_code", "has_paper", "has_data", "has_slides", "server_compute"}
    list_keys = {"fields", "subfields", "keywords", "depends_on", "related", "related_literature", "hosts"}
    for key in scalar_keys:
        value = data.get(key)
        if value is not None and not isinstance(value, (list, dict)):
            meta[key] = _yaml_text(value)
    for key in list_keys:
        value = data.get(key)
        if isinstance(value, list):
            meta[key] = [_yaml_text(item) for item in value]
        elif isinstance(value, str) and value:
            meta[key] = [value]
    runtime = data.get("runtime")
    if isinstance(runtime, dict):
        meta["runtime"] = _normalize_mapping(runtime)
    dependencies = data.get("project_dependencies")
    if isinstance(dependencies, list):
        meta["project_dependencies"] = [_normalize_mapping(dep) for dep in dependencies if isinstance(dep, dict)]
    steps = data.get("package_install")
    if isinstance(steps, list):
        meta["package_install"] = [_yaml_text(step) for step in steps]
    sync = data.get("sync")
    if isinstance(sync, dict):
        meta["sync"] = _normalize_mapping(sync)
    return meta


def command_project_taxonomy(_args: argparse.Namespace) -> None:
    taxonomy = load_taxonomy()
    print(f"taxonomy: {rel_home(PROJECT_TAXONOMY)}")
    print("type: " + ", ".join(taxonomy["type"]))
    print("fields: " + ", ".join(taxonomy["fields"]))
    print("subfields:")
    for field in taxonomy["fields"]:
        values = subfield_map(taxonomy).get(field, [])
        print(f"  {field}: {', '.join(values) if values else '-'}")


def command_add_project_type(args: argparse.Namespace) -> None:
    add_taxonomy_value("type", args.value)


def command_add_project_field(args: argparse.Namespace) -> None:
    add_taxonomy_value("fields", args.value)


def command_add_project_subfield(args: argparse.Namespace) -> None:
    add_subfield(args.field, args.value)


def command_project_list(args: argparse.Namespace) -> None:
    use_projects_dir(args)
    projects = existing_project_names()
    wanted_type = getattr(args, "type", None)
    wanted_status = getattr(args, "status", None)
    wanted_fields = getattr(args, "field", None) or []
    wanted_subfields = getattr(args, "subfield", None) or []
    wanted_keywords = getattr(args, "keyword", None) or []
    if wanted_type or wanted_status or wanted_fields or wanted_subfields or wanted_keywords:
        kept = []
        for name in projects:
            meta = parse_project_yaml(PROJECTS / name / "project.yaml")
            if wanted_type and str(meta.get("type", "")) != wanted_type:
                continue
            if wanted_status and str(meta.get("status", "")) != wanted_status:
                continue
            if any(field not in meta.get("fields", []) for field in wanted_fields):
                continue
            if any(value not in meta.get("subfields", []) for value in wanted_subfields):
                continue
            if any(keyword not in meta.get("keywords", []) for keyword in wanted_keywords):
                continue
            kept.append(name)
        projects = kept
    if not projects:
        print("no projects")
        return
    for name in projects:
        print(f"project:{name}")


def command_project_views_rebuild(args: argparse.Namespace) -> None:
    use_projects_dir(args)
    from ws_lib import anatomy

    counts = anatomy.rebuild_projects()
    print(f"views: {rel_home(anatomy.PROJECTS_DOMAIN)}/by-*")
    for name in sorted(counts):
        print(f"{name}: {counts[name]}")


def _print_list(label: str, values: list[str]) -> None:
    print(f"{label}: {', '.join(values) if values else '-'}")


def command_project_show(args: argparse.Namespace) -> None:
    use_projects_dir(args)
    value = getattr(args, "ref", None)
    if value:
        name = project_key_from_ref(value)
    else:  # compatibility for internal/test Namespaces
        name = resolve_project_name(args.name)
    root = PROJECTS / name
    meta = parse_project_yaml(root / "project.yaml")
    print(f"ref: project:{name}")
    print(f"folder: {rel_home(root)}")
    print(f"title: {meta.get('title', '')}")
    print(f"type: {meta.get('type', '')}")
    print(f"status: {meta.get('status', '')}")
    _print_list("fields", meta.get("fields", []))
    _print_list("subfields", meta.get("subfields", []))
    _print_list("keywords", meta.get("keywords", []))
    _print_list("depends_on", meta.get("depends_on", []))
    _print_list("related", meta.get("related", []))
    _print_list("related_literature", meta.get("related_literature", []))
    _print_list("hosts", meta.get("hosts", []))
    runtime = meta.get("runtime") or {}
    if runtime:
        print(f"python: {runtime.get('python') or '-'}")
        print(f"venv: {runtime.get('venv') or '-'}")
    dependencies = meta.get("project_dependencies") or []
    print("project_dependencies:")
    if dependencies:
        for dep in dependencies:
            detail = dep.get("path") or dep.get("command") or ""
            read_value = dep.get("read")
            if not detail and isinstance(read_value, list):
                detail = ", ".join(read_value)
            elif not detail and read_value:
                detail = str(read_value)
            suffix = f" ({detail})" if detail else ""
            print(f"  {dep.get('project', '')}: {dep.get('kind', '')}{suffix}")
    else:
        print("  -")
    subs = subproject_names(root)
    print("subprojects:")
    for sub_name in subs:
        print(f"  {sub_name}")
    if not subs:
        print("  -")


SUBPROJECT_DIRS = ["code", "data", "results"]

# Folders never scanned for subprojects: a project's standard content folders
# plus dependency/noise dirs. A grouping folder must not use one of these names.
SUBPROJECT_SCAN_SKIP = {"code", "paper", "data", "docs", "refs", "notes", "results", "out", "tmp", "node_modules", "__pycache__"}

SUBPROJECT_GITIGNORE = """.DS_Store
__pycache__/
*.pyc

# Outputs and heavy data: created locally, not tracked
results/
data/**
!data/**/
!data/**/.gitkeep
!data/**/*.md
out/
tmp/
"""


def subproject_names(project_root: Path) -> list[str]:
    """Subprojects of a project (folders holding subproject.yaml), as POSIX
    paths relative to the project root. Subprojects may sit inside plain
    grouping folders; discovery prunes the standard content folders (code/,
    data/, ...) and never descends into a subproject (they don't nest)."""
    if not project_root.exists():
        return []
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(project_root):
        current = Path(dirpath)
        if current != project_root and "subproject.yaml" in filenames:
            found.append(current.relative_to(project_root).as_posix())
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in SUBPROJECT_SCAN_SKIP and not d.startswith(".")]
    return sorted(found)


def command_project_sub(args: argparse.Namespace) -> None:
    """Create a subproject: a project co-located inside another project to
    borrow its .venv (and thus its installed code) — a concept justified by
    coding projects. It carries a subproject.yaml, not a project.yaml, so
    discovery keeps the enclosing project as the parent and `ws projects
    install` sets up the parent's environment; identity-wise it is a project
    (`project:<parent>/<path>`) and fully relatable. It versions itself: its
    own git repository, ignored by the parent's. Subprojects may sit inside
    plain grouping folders within the project, but never inside another
    subproject."""
    use_projects_dir(args)
    if getattr(args, "project_ref", None):
        parent_name = project_key_from_ref(args.project_ref)
        parent_root = PROJECTS / parent_name
        dest = parent_root
    elif getattr(args, "project", None):  # compatibility for internal/test Namespaces
        parent_name = resolve_project_name(args.project)
        parent_root = PROJECTS / parent_name
        dest = parent_root
    else:
        enclosing = find_enclosing_project()
        if enclosing is None:
            fail("not inside a project; run from inside one or pass --project <project>")
        parent_root = enclosing
        parent_name = parent_root.resolve().relative_to(PROJECTS.resolve()).as_posix()
        dest = Path.cwd()
    root = dest / project_path_slug(args.name)
    rel_parts = root.resolve().relative_to(parent_root.resolve()).parts
    probe = parent_root.resolve()
    for part in rel_parts[:-1]:
        if part in SUBPROJECT_SCAN_SKIP or part.startswith("."):
            fail(f"`{part}/` is a content folder, not a grouping folder; a subproject there would be invisible to `ws projects show`")
        probe = probe / part
        if (probe / "subproject.yaml").exists():
            fail(f"{rel_home(probe)} is a subproject; subprojects don't nest -- create it from the project root or a plain grouping folder")
    name = rel_parts[-1]
    if root.exists():
        fail(f"already exists: {rel_home(root)}")
    venv_rel = "/".join([".."] * len(rel_parts)) + "/.venv"
    description = args.description or "One paragraph."
    root.mkdir(parents=True)
    for folder in SUBPROJECT_DIRS:
        (root / folder).mkdir()
        print(f"created: {rel_home(root / folder)}/")
    write_new(root / "code" / ".gitkeep", "")
    write_new(root / "data" / ".gitkeep", "")
    write_new(
        root / "subproject.yaml",
        f"schema_version: 1\nname: {name}\ntype: subproject\nparent: {parent_name}\n"
        f"created: {today()}\nvenv: {venv_rel}\ndescription: >\n  {description}\n",
    )
    write_new(root / ".gitignore", SUBPROJECT_GITIGNORE)
    write_new(
        root / "README.md",
        f"# {project_title(name, None)}\n\n"
        f"Subproject of `{parent_name}`. Shares the parent's environment "
        f"(`{venv_rel}`); it has no `.venv` of its own. Versioned by its own "
        f"git repository, ignored by the parent's.\n",
    )
    # The subproject versions itself: its own repository, ignored by the
    # parent's so the parent's history stays free of it.
    if not (root / ".git").exists():
        subprocess.run(["git", "init"], cwd=root, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"initialized git: {rel_home(root)}")
    ignore_line = "/".join(rel_parts) + "/"
    parent_ignore = parent_root / ".gitignore"
    existing_ignore = read(parent_ignore) if parent_ignore.exists() else ""
    if ignore_line not in existing_ignore.splitlines():
        with parent_ignore.open("a", encoding="utf-8") as handle:
            if existing_ignore and not existing_ignore.endswith("\n"):
                handle.write("\n")
            handle.write(f"{ignore_line}\n")
        print(f"ignored by parent: {ignore_line}")
    print(f"subproject ready: {rel_home(root)}")
    print(f"uses the parent env — run `{venv_rel}/bin/python ...` (or `source {venv_rel}/bin/activate`) from {rel_home(root)}")


def command_new_project(args: argparse.Namespace) -> None:
    from ws_lib import catalog

    use_projects_dir(args)
    taxonomy = load_taxonomy()
    project_types = taxonomy["type"]
    allowed_fields = taxonomy["fields"]
    proj_root = PROJECTS.resolve()
    # The store is flat: every project is created directly in the store,
    # regardless of the current directory. Grouping lives in the by-* views.
    create_parent = proj_root
    if not getattr(args, "projects_dir", None):
        cwd = Path.cwd().resolve()
        if cwd == proj_root or proj_root in cwd.parents:
            enclosing = find_enclosing_project(cwd)
            if enclosing is not None:
                fail(
                    f"already inside project '{enclosing.relative_to(proj_root).as_posix()}'; "
                    "run from elsewhere or pass --in"
                )
    raw_name = getattr(args, "name", None) or []
    if isinstance(raw_name, str):
        raw_name = [raw_name]
    if not raw_name:
        may_prompt = bool(getattr(args, "interactive", False)) or (
            not getattr(args, "non_interactive", False) and sys.stdin.isatty()
        )
        if not may_prompt:
            fail("project name is required")
        while not raw_name:
            typed = ask("Name (folder name; words are slugified)")
            if typed.strip():
                raw_name = [typed]
            elif not sys.stdin.isatty():
                fail("project name is required")
    if "/" in " ".join(raw_name):
        fail(
            "the projects store is flat; grouping folders are retired -- "
            "express grouping with fields/keywords and browse the by-* views"
        )
    relpath = (create_parent / project_slug(raw_name)).relative_to(proj_root).as_posix()
    name = relpath.rsplit("/", 1)[-1]
    title = project_title(name, args.title)
    project_type = args.type or project_types[0]
    status = args.status or "active"
    description = args.description or "One paragraph."
    fields = args.field or []
    subfields = getattr(args, "subfield", None) or []
    keywords = args.keyword or []
    project_dependencies = parse_project_dependencies(getattr(args, "use_project", None))
    hosts = args.host or [paths.HOST]
    python_enabled = bool(getattr(args, "python", False))
    venv_enabled = bool(getattr(args, "venv", False))
    if venv_enabled:
        python_enabled = True
    has_code = bool(args.has_code or python_enabled)
    has_paper = bool(args.has_paper)
    has_data = bool(args.has_data)
    has_slides = bool(getattr(args, "has_slides", False))
    server_compute = bool(args.server_compute)

    if should_prompt_for_project_setup(args):
        title = ask("Title", title)
        project_type = ask_choice("Type", project_types, project_type, taxonomy_key="type")
        description = ask("Description", description)
        fields = ask_list("Fields", allowed_fields, fields, taxonomy_key="fields")
        available_subfields = compatible_subfields(fields, load_taxonomy())
        if available_subfields:
            subfields = ask_list("Subfields", available_subfields, subfields)
        keywords = ask_list("Keywords", [], keywords)
        questions = wizard_question_set(project_type)
        if project_type == "paper":
            has_paper = True
        if "code" in questions:
            has_code = ask_bool("Has code", has_code)
        if "python" in questions:
            python_enabled = ask_bool("Python project", python_enabled or has_code)
        if "venv" in questions:
            venv_enabled = ask_bool("Create Python virtual environment", venv_enabled or python_enabled)
        if python_enabled or venv_enabled:
            has_code = True
        if "deps" in questions:
            venv_enabled, project_dependencies = ask_project_dependencies(venv_enabled, project_dependencies)
        if "paper" in questions:
            has_paper = ask_bool("Has paper", has_paper)
        if "data" in questions:
            has_data = ask_bool("Has data", has_data)
        if "slides" in questions:
            has_slides = ask_bool(
                "Has slides (install slide generator into venv)",
                has_slides or project_type == "talk",
            )
        if "server" in questions:
            server_compute = ask_bool("Needs server compute", server_compute)

    if has_slides:
        venv_enabled = True
    if venv_enabled:
        python_enabled = True
    if python_enabled:
        has_code = True

    if project_type not in project_types:
        fail(f"type must be one of: {', '.join(project_types)}")
    if status not in PROJECT_STATUSES:
        fail(f"status must be one of: {', '.join(PROJECT_STATUSES)}")
    classification_errors = classification_problems(fields, subfields, taxonomy)
    if classification_errors:
        fail(
            "; ".join(classification_errors)
            + f". Extend with `ws projects add-field` / `add-subfield`, or edit {rel_home(PROJECT_TAXONOMY)}"
        )
    known_projects = set(existing_project_names()) - {relpath}
    for dep in project_dependencies:
        if normalize_ref(dep["project"], known_projects) is None:
            print(f"warning: project dependency is not an existing project: {dep['project']}", file=sys.stderr)
    primary_host = hosts[0]
    root = PROJECTS / relpath
    root.mkdir(parents=True, exist_ok=True)
    for folder in requested_project_dirs(has_code, has_paper, has_data):
        path = root / folder
        if path.exists():
            print(f"exists: {rel_home(path)}/")
        else:
            path.mkdir()
            print(f"created: {rel_home(path)}/")
    replacements = {
        "<ws-root>": str(SYSTEM),
        "<project-name>": name,
        "<Project Title>": title,
        "YYYY-MM-DD": today(),
    }
    project_yaml = f"""schema_version: 1
name: {name}
title: {yaml_scalar(title)}
type: {project_type}
status: {status}
created: {today()}
description: >
  {description}

fields: {yaml_list(fields)}
subfields: {yaml_list(subfields)}
keywords: {yaml_list(keywords)}

has_code: {str(has_code).lower()}
has_paper: {str(has_paper).lower()}
has_data: {str(has_data).lower()}
has_slides: {str(has_slides).lower()}
server_compute: {str(server_compute).lower()}

runtime:
  python: {str(python_enabled).lower()}
  venv: {yaml_scalar(".venv" if venv_enabled else "")}

{yaml_project_dependencies(project_dependencies)}

hosts: {yaml_list(hosts)}

sync:
  primary_host: {yaml_scalar(primary_host)}
  remotes: []
  git: []
  data: []
"""
    write_new(root / "project.yaml", project_yaml)
    readme = f"""# {title}

## Purpose

{description}

## Current State

- Status: `{status}`
- Type: `{project_type}`

## Important Files

- `project.yaml` - machine-readable project metadata and routing hints
- `AGENTS.md` - project-wide instructions for agents and humans
- `README.md` - human-readable overview

## Next Steps

- Replace this section with the first concrete project tasks.
"""
    write_new(root / "README.md", readme)
    copy_template("AGENTS.md", root / "AGENTS.md", replacements)
    write_claude_md(root)
    copy_template("gitignore", root / ".gitignore", replacements)
    if python_enabled:
        create_python_project_files(root, name)
    if venv_enabled:
        create_venv(root)
        install_package_project_dependencies(root, project_dependencies)
        if has_slides:
            install_slide_factory(root)
    if not (root / ".git").exists():
        subprocess.run(["git", "init"], cwd=root, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"initialized git: {rel_home(root)}")
    dependency_projects = [f"project:{dep['project']}" for dep in project_dependencies]
    if dependency_projects:
        # Derived from --use-project installs, not a user-asserted relation.
        _relate_project_links(relpath, dependency_projects, [])
    print(f"created: project:{name}")
    print(f"project ready: {rel_home(root)}")


def command_project_install(args: argparse.Namespace) -> None:
    use_projects_dir(args)
    tokens = list(getattr(args, "tokens", None) or [])
    ref = getattr(args, "ref", None)
    if ref is None and tokens and tokens[0] not in INSTALL_FEATURES:
        # A leading token is the project only when it clearly names one;
        # anything else is reported as a bad capability, not a bad REF.
        if ":" in tokens[0] or tokens[0] in set(existing_project_names()):
            ref = tokens.pop(0)
    invalid = [token for token in tokens if token not in INSTALL_FEATURES]
    if invalid:
        fail(
            f"unknown install feature: {', '.join(invalid)}. Choose from: {', '.join(INSTALL_FEATURES)}"
            " (to name the project, put it first as project:<key>)"
        )
    new_dependencies = parse_project_dependencies(getattr(args, "use_project", None))
    if ref:
        name = project_key_from_ref(ref)
        root = PROJECTS / name
    elif getattr(args, "name", None):  # compatibility for internal/test Namespaces
        name = resolve_project_name(args.name)
        root = PROJECTS / name
    else:
        enclosing = find_enclosing_project()
        if enclosing is None:
            fail("not inside a project; pass a project REF")
        root = enclosing
    if not (root / "project.yaml").exists():
        fail(f"no project.yaml at {rel_home(root)}")
    features = feature_closure(tokens) if tokens else set()
    if new_dependencies:
        # Package dependencies install into the venv, so asking for one
        # asserts the venv chain the same way the wizard does.
        features |= feature_closure(["venv"])
    if features:
        top = {f"has_{feature}": "true" for feature in features if feature in {"code", "paper", "data", "slides"}}
        runtime_updates: dict[str, str] = {}
        if "python" in features:
            runtime_updates["python"] = "true"
        if "venv" in features:
            runtime_updates["venv"] = yaml_scalar(".venv")
        update_project_yaml_capabilities(root, top, runtime_updates)
    if new_dependencies:
        added = record_project_dependencies(root, new_dependencies)
        if added:
            try:
                relpath = str(root.resolve().relative_to(PROJECTS.resolve()))
            except ValueError:
                relpath = root.name
            # Same invariant as creation: a recorded install dependency also
            # carries its depends-on edge — one statement, stated once.
            _relate_project_links(relpath, [f"project:{dep['project']}" for dep in added], [])
    if not converge_project_installs(root):
        print("nothing recorded to install")


def command_project_check(_args: argparse.Namespace) -> None:
    use_projects_dir(_args)
    taxonomy_data = load_taxonomy()
    problems = 0
    taxonomy_findings = taxonomy_problems(taxonomy_data)
    if taxonomy_findings:
        print("project-taxonomy:")
        for message in taxonomy_findings:
            print(f"  problem: {message}")
            problems += 1
    projects = existing_project_names()
    if not projects:
        print("no projects")
        if problems:
            raise SystemExit(1)
        return
    known = set(projects)
    known_literature = set(existing_literature_keys())
    for name in projects:
        root = PROJECTS / name
        findings: list[tuple[str, str]] = []
        for required in ["project.yaml", "README.md", "AGENTS.md", ".gitignore"]:
            if not (root / required).exists():
                findings.append(("problem", f"missing {required}"))
        claude_problem = validate_claude_md(root)
        if claude_problem:
            findings.append(("problem", claude_problem))
        has_git = (root / ".git").exists()
        if not has_git:
            findings.append(("problem", "no git repository (run git init)"))
        meta = parse_project_yaml(root / "project.yaml")
        for problem in classification_problems(
            meta.get("fields", []), meta.get("subfields", []), taxonomy_data
        ):
            findings.append(("problem", problem))
        for dep in meta["depends_on"]:
            canon = normalize_ref(dep, known)
            if canon is None or canon == name:
                findings.append(("problem", f"depends_on references unknown project: {dep}"))
        for rel in meta["related"]:
            if normalize_ref(rel, known) is None:
                findings.append(("note", f"related entry is not a project: {rel} (ok if paper/dataset/external)"))
        for key in meta["related_literature"]:
            if key not in known_literature:
                findings.append(("problem", f"related_literature references unknown item: {key}"))
        runtime = meta.get("runtime") or {}
        if str(runtime.get("venv", "")).strip() and not (root / str(runtime["venv"])).exists():
            findings.append(("note", f"runtime.venv is recorded but missing locally: {runtime['venv']}"))
        for dep in meta.get("project_dependencies", []):
            dep_project = dep.get("project", "")
            kind = dep.get("kind", "")
            canon = normalize_ref(dep_project, known)
            if canon is None:
                findings.append(("problem", f"project_dependencies references unknown project: {dep_project}"))
                continue
            if kind not in PROJECT_DEPENDENCY_KINDS:
                findings.append(("problem", f"project_dependencies has unknown kind for {dep_project}: {kind}"))
                continue
            if kind in {"package", "source", "data"}:
                dep_path = PROJECTS / canon / str(dep.get("path") or ("data" if kind == "data" else "."))
                if not dep_path.exists():
                    findings.append(("problem", f"project dependency path missing: {dep_project}:{kind}:{dep_path.relative_to(PROJECTS / canon)}"))
        sync = meta["sync"]
        if sync is None:
            findings.append(("note", "no sync block"))
        else:
            if not sync.get("primary_host"):
                findings.append(("problem", "sync.primary_host is missing or empty"))
            for key in ["remotes", "git", "data"]:
                if key not in sync:
                    findings.append(("problem", f"sync.{key} is missing"))
        if has_git:
            nested, agent_dirs, large = scan_project(root)
            for repo in nested:
                findings.append(("problem", f"nested git repo not ignored: {repo.relative_to(root)} (add to .gitignore or use a submodule)"))
            for agent_dir in agent_dirs:
                findings.append(("problem", f"agent session not ignored: {agent_dir.relative_to(root)}"))
            for fp, size in large:
                findings.append(("problem", f"large file not ignored: {fp.relative_to(root)} ({size / (1024 * 1024):.1f} MB)"))
        if not findings:
            print(f"ok: {name}")
            continue
        print(f"{name}:")
        for level, message in findings:
            print(f"  {level}: {message}")
            if level == "problem":
                problems += 1
    if problems:
        raise SystemExit(1)


def command_project_help(args: argparse.Namespace) -> None:
    args.parser.print_help()


def add_taxonomy_value_parser(sub: argparse._SubParsersAction, name: str, func, help_text: str) -> None:
    parser = sub.add_parser(name, help=help_text)
    parser.add_argument("value")
    parser.set_defaults(func=func)


def add_projects_dir_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--in",
        dest="projects_dir",
        metavar="DIR",
        help="folder that contains project folders; default: WS_PROJECTS_DIR, WS_WORKSPACE_ROOT/projects, or ~/workspace/projects",
    )


def add_new_project_parser(sub: argparse._SubParsersAction, name: str, command_label: str, help_text: str | None = None) -> None:
    taxonomy = load_taxonomy()
    project_types = taxonomy["type"]
    fields = taxonomy["fields"]
    subfields = all_subfields(taxonomy)

    new_project = sub.add_parser(
        name,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help=help_text,
        description="Create a minimal project scaffold in a chosen projects folder.",
        epilog=f"""Examples:
  {command_label} test project             bare name: the setup wizard asks the rest
  {command_label} code-tool --type software --python --venv
  {command_label} tax-paper --type paper --has-paper --non-interactive
  ws projects add-type dataset      extend the type/field/subfield vocabulary

Generated files:
  project.yaml  machine-readable metadata and routing
  README.md     human-readable overview
  AGENTS.md     project-wide agent instructions
  CLAUDE.md     symlink to AGENTS.md for Claude Code
  .gitignore    local ignore rules

Generated folders when requested:
  code/   --has-code
  paper/  --has-paper
  data/   --has-data

Default setup mode:
  bare project names open the interactive setup wizard in a terminal
  any explicit setup flag skips the wizard
  --non-interactive forces the minimal/default scaffold

Other allowed project folders are created only when first needed.

Project destination (first match wins):
  --in DIR           create under DIR
  current folder     when run inside the projects tree, create here (nested);
                     refused inside an existing project
  WS_PROJECTS_DIR    the projects root otherwise
  WS_WORKSPACE_ROOT  fallback parent is $WS_WORKSPACE_ROOT/projects
  otherwise          ~/workspace/projects

More detail:
  taxonomy: {rel_home(PROJECT_TAXONOMY)}
  template: {rel_home(TEMPLATES / "project.yaml")}
  contract: {rel_home(CONTRACTS / "project.md")}
  setup guide: {rel_home(PROJECT_SETUP_DOC)}
""",
    )
    new_project.add_argument("name", nargs="*", help="project name; words are slugified, e.g. `test project` -> `test-project`; omitted on a terminal, the wizard asks for it")
    add_projects_dir_arg(new_project)
    new_project.add_argument("--title", help="human-readable title; defaults to title-cased project name")
    new_project.add_argument(
        "--type", choices=project_types, metavar="TYPE",
        help=f"one of: {', '.join(project_types)}; defaults to {project_types[0]} (extend with `ws projects add-type`)",
    )
    new_project.add_argument(
        "--status", choices=PROJECT_STATUSES, metavar="STATUS",
        help=f"one of: {', '.join(PROJECT_STATUSES)}; defaults to active",
    )
    new_project.add_argument("--description", help="one-paragraph purpose written into project.yaml and README.md")
    new_project.add_argument(
        "--field", choices=fields, action="append", metavar="FIELD",
        help=f"repeatable; one of: {', '.join(fields)}; defaults to {fields[0]} (extend with `ws projects add-field`)",
    )
    new_project.add_argument(
        "--subfield", choices=subfields, action="append", metavar="SUBFIELD",
        help=f"repeatable; one of: {', '.join(subfields)}; must belong to a selected field",
    )
    new_project.add_argument("--keyword", action="append", help="repeatable free-form content keyword")
    new_project.add_argument(
        "--use-project",
        action="append",
        metavar="REF[:package[:PATH]]",
        help="repeatable; pip-install another workspace project (editable) into this "
        "project's own .venv and record its depends-on edge, e.g. project:solver",
    )
    new_project.add_argument("--host", action="append", help="repeatable host name; defaults to the current host")
    new_project.add_argument("--has-code", action="store_true", help="mark that the project is expected to contain code")
    new_project.add_argument("--has-paper", action="store_true", help="mark that the project is expected to contain a paper/manuscript")
    new_project.add_argument("--has-data", action="store_true", help="mark that the project is expected to contain data")
    new_project.add_argument("--has-slides", action="store_true", help="install the slide_factory deck generator into the venv; implies --venv")
    new_project.add_argument("--server-compute", action="store_true", help="mark that the project expects server/HPC compute")
    new_project.add_argument("--python", action="store_true", help="set up Python project metadata and imply --has-code")
    new_project.add_argument("--venv", action="store_true", help="create .venv with python -m venv; implies --python")
    new_project.add_argument("--interactive", action="store_true", help="prompt for common metadata fields before creating files")
    new_project.add_argument("--non-interactive", action="store_true", help="never prompt; use defaults for omitted setup choices")
    new_project.set_defaults(func=command_new_project)


def project_list_arguments(listing: argparse.ArgumentParser) -> None:
    """The project list filter set; shared by the domain parser and `ws list`."""
    listing.add_argument("--type")
    listing.add_argument("--status")
    listing.add_argument("--field", action="append")
    listing.add_argument("--subfield", action="append")
    listing.add_argument("--keyword", action="append")
    add_projects_dir_arg(listing)


def add_parser(sub: argparse._SubParsersAction, command_name: str = "projects") -> None:
    """The projects domain home: install, check, taxonomy, and views.
    Projects are minted with `ws create project` and read with
    `ws show project:<key>` / `ws list projects`."""
    project_cmd = sub.add_parser(
        command_name,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Project specialists: installs, checks, taxonomy, views.",
        epilog="""Primary project commands:
  ws projects install [<name>]
  ws projects taxonomy
  ws projects add-type <type>
  ws projects add-field <field>
  ws projects add-subfield <field> <subfield>
  ws projects check

Projects are minted with `ws create project` and read with
`ws show project:<key>` and `ws list projects`.
""",
    )
    project_cmd.set_defaults(func=command_project_help, parser=project_cmd)
    project_sub = project_cmd.add_subparsers(dest="project_command")
    project_check = project_sub.add_parser("check", help="check projects for git, sync, and cross-reference problems")
    add_projects_dir_arg(project_check)
    project_check.set_defaults(func=command_project_check)
    project_install = project_sub.add_parser(
        "install",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="make the project match project.yaml; add capabilities and dependencies after creation",
        description="Make the working tree match what project.yaml records, extending the record first when asked. "
        "Nothing is settable only at creation.",
        epilog="""Capabilities and what they materialize:
  code, paper, data  the matching folder, recorded as has_<capability>: true
  python             pyproject.toml, recorded as runtime.python (implies code)
  venv               .venv, recorded as runtime.venv (implies python)
  slides             the slide_factory deck generator shipped with ws, plus any
                     theme packages from `slides.themes` in the ws
                     configuration, editable-installed into .venv (implies venv)

Examples:
  ws projects install                (re)run everything recorded: folders,
                                     pyproject.toml, .venv, package
                                     dependencies, the slide generator —
                                     also heals a rebuilt .venv
  ws projects install slides         add deck building to this project
  ws projects install project:my-talk slides    the same, from anywhere
  ws projects install --use-project project:solver
                                     record + install an editable package
                                     dependency and its depends-on edge

Capabilities extend the record and never unset it; removal is a hand edit.""",
    )
    project_install.add_argument(
        "tokens",
        nargs="*",
        metavar="TOKEN",
        help="optional project:<key> first (defaults to the enclosing project), "
        "then capabilities to record and install: code, paper, data, python, venv, slides",
    )
    project_install.add_argument(
        "--use-project",
        action="append",
        metavar="REF[:package[:PATH]]",
        help="repeatable; record another workspace project as an editable install into this "
        "project's own .venv, create its depends-on edge, and install it, e.g. project:solver",
    )
    add_projects_dir_arg(project_install)
    project_install.set_defaults(func=command_project_install)
    project_views_cmd = project_sub.add_parser("views", help="derived symlink browse views over projects")
    project_views_actions = project_views_cmd.add_subparsers(dest="views_command", required=True)
    project_views_rebuild = project_views_actions.add_parser(
        "rebuild", help="wipe and regenerate views/ from classifiers and organisation edges"
    )
    add_projects_dir_arg(project_views_rebuild)
    project_views_rebuild.set_defaults(func=command_project_views_rebuild)
    project_sub.add_parser("taxonomy", help="show allowed project types, fields, and subfields").set_defaults(func=command_project_taxonomy)
    add_taxonomy_value_parser(project_sub, "add-type", command_add_project_type, "add an allowed project type")
    add_taxonomy_value_parser(project_sub, "add-field", command_add_project_field, "add an allowed project field")
    add_subfield_parser = project_sub.add_parser(
        "add-subfield", help="add a field-specific subfield"
    )
    add_subfield_parser.add_argument("field")
    add_subfield_parser.add_argument("value")
    add_subfield_parser.set_defaults(func=command_add_project_subfield)


def add_create_parser(sub: argparse._SubParsersAction) -> argparse._SubParsersAction:
    create_cmd = sub.add_parser(
        "create",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Mint a new object; the kind is the first word.",
        epilog="""Create mints something new; `ws add` ingests something that already exists.
  ws create project <name>     full project: project.yaml, own .venv, own git
  ws create subproject <name>  working area inside a project; borrows the parent's .venv
  ws create task <title>
  ws create resource <name>
  ws create profile <name> --type <type>

Ingestion (document, person, organisation, event, literature) lives under
`ws add`. Agent roles are not objects: `ws agents create <role>`; the former
`ws create agent|subagent` spellings remain compatibility shortcuts.
""",
    )
    create_cmd.set_defaults(func=command_project_help, parser=create_cmd)
    create_sub = create_cmd.add_subparsers(dest="create_command")
    add_new_project_parser(create_sub, "project", "ws create project", "create a project")
    subproject_cmd = create_sub.add_parser("subproject", help="create a subproject inside a project (shares the parent's .venv)")
    subproject_cmd.add_argument("name", nargs="+", help="subproject name; words are slugified; may be a path into a grouping folder, e.g. `shuttling/corner`")
    subproject_cmd.add_argument("--project", dest="project_ref", metavar="REF", help="parent project REF; defaults to the enclosing project (run inside a grouping folder to create the subproject there)")
    subproject_cmd.add_argument("--description", help="one-paragraph purpose")
    add_projects_dir_arg(subproject_cmd)
    subproject_cmd.set_defaults(func=command_project_sub)
    return create_sub
