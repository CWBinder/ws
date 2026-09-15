import os
import platform
import sys
from pathlib import Path

from ws_lib import config


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name)
    if not value:
        return None
    return Path(value).expanduser()


AUTHOR = os.environ.get("WS_AUTHOR", "")
CONTACT_EMAIL = os.environ.get("WS_CONTACT_EMAIL", "")


CODE_CLI = Path(__file__).resolve().parents[1]

CLI = _env_path("WS_CLI_ROOT") or CODE_CLI
SYSTEM = _env_path("WS_SYSTEM_ROOT") or (
    CLI.parent if (CLI.parent / "SKILL.md").is_file()
    else Path(sys.prefix) / "share" / "ws"
)
_configured_root = config.get("workspace_root")
if _configured_root is not None and (
    not isinstance(_configured_root, str) or not _configured_root.strip()
):
    raise SystemExit(f"error: workspace_root must be a non-empty path in {config.CONFIG_PATH}")
WORKSPACE = (
    _env_path("WS_WORKSPACE_ROOT")
    or (Path(_configured_root).expanduser() if _configured_root else None)
    or Path.home() / "workspace"
).resolve()

# The projects domain root holds the flat items/ store, the derived by-*
# browse trees, and the taxonomy. WS_PROJECTS_DIR points at the store
# (canonical project folders); the domain root is its parent unless
# WS_PROJECTS_DOMAIN overrides it explicitly.
_PROJECTS_STORE = _env_path("WS_PROJECTS_DIR")
PROJECTS_DOMAIN = (
    _env_path("WS_PROJECTS_DOMAIN")
    or (_PROJECTS_STORE.parent if _PROJECTS_STORE else WORKSPACE / "projects")
)
PROJECTS = _PROJECTS_STORE or PROJECTS_DOMAIN / "items"

TEMPLATES = SYSTEM / "templates"

HOST = os.environ.get("WS_HOST") or platform.node().split(".")[0].lower() or "local"
CONTRACTS = SYSTEM / "contracts"
PROJECT_TAXONOMY = (
    _env_path("WS_PROJECT_TAXONOMY")
    or PROJECTS_DOMAIN / "project-taxonomy.yaml"
)
PROJECT_SETUP_DOC = SYSTEM / "docs" / "project-setup.md"

_LEGACY_LIBRARY = _env_path("WS_LIBRARY_DIR")
LITERATURE = (
    _env_path("WS_LITERATURE_DIR")
    or (_LEGACY_LIBRARY / "literature" if _LEGACY_LIBRARY else WORKSPACE / "literature")
)
# Compatibility alias for older callers. Literature is now a top-level domain.
LIBRARY = _LEGACY_LIBRARY or LITERATURE
LITERATURE_ITEMS = _env_path("WS_LITERATURE_ITEMS_DIR") or LITERATURE / "items"
KNOWLEDGEBASE = (
    _env_path("WS_WIKI_DIR")
    or _env_path("WS_KNOWLEDGEBASE_DIR")
    or WORKSPACE / "wiki"
)

CAREER = (
    _env_path("WS_PROFILE_DIR")
    or _env_path("WS_CAREER_DIR")
    or WORKSPACE / "profile"
)
PROFILE_ITEMS = _env_path("WS_PROFILE_ITEMS_DIR") or CAREER / "items"
PROFILE_APPLICATIONS = (
    _env_path("WS_PROFILE_APPLICATIONS_DIR") or CAREER / "applications"
)
PROFILE_TAXONOMY = (
    _env_path("WS_PROFILE_TAXONOMY") or CAREER / "profile-taxonomy.yaml"
)

UTILS = _env_path("WS_UTILS_DIR") or Path.home() / "Utils"

# Canonical domains map one-to-one to top-level workspace directories.
# DATA remains as a compatibility override for relocating the structured domain
# roots together; individual WS_*_DIR variables take precedence.
DATA = _env_path("WS_DATA_DIR") or WORKSPACE
LOGISTICS = _env_path("WS_LOGISTICS_DIR") or DATA / "logistics"
PEOPLE = _env_path("WS_PEOPLE_DIR") or LOGISTICS / "people"
ORGANISATIONS = _env_path("WS_ORGANISATIONS_DIR") or LOGISTICS / "organisations"
EVENTS = _env_path("WS_EVENTS_DIR") or LOGISTICS / "events"
COMMUNICATIONS = _env_path("WS_COMMUNICATIONS_DIR") or LOGISTICS / "communications"
TASKS = _env_path("WS_TASKS_DIR") or DATA / "tasks"
DOCUMENTS = _env_path("WS_DOCUMENTS_DIR") or DATA / "documents"
DOCUMENT_FILES = _env_path("WS_DOCUMENT_FILES_DIR") or DOCUMENTS / "files"
DOCUMENT_OBJECTS = _env_path("WS_DOCUMENT_OBJECTS_DIR") or DOCUMENTS / "items"
DOCUMENT_TAXONOMY = (
    _env_path("WS_DOCUMENT_TAXONOMY")
    or DOCUMENTS / "document-taxonomy.yaml"
)
RESOURCES = _env_path("WS_RESOURCES_DIR") or DATA / "resources"
RESOURCE_ITEMS = _env_path("WS_RESOURCE_ITEMS_DIR") or RESOURCES / "items"
# Relations are a cross-domain canonical store, so they live at the workspace
# root rather than under any one content domain. LEGACY_RELATIONS exists only
# to support the explicit `ws relations migrate` command.
LEGACY_RELATIONS = (
    _env_path("WS_LEGACY_RELATIONS_DIR")
    or WORKSPACE / "documents" / "Workspace" / "relations"
)
RELATIONS = _env_path("WS_RELATIONS_DIR") or WORKSPACE / "relations"

# Derived and rebuildable.  It intentionally does not live beside canonical
# object or relationship YAML.
INDEX_DIR = _env_path("WS_INDEX_DIR") or _env_path("WS_SEARCH_DIR") or WORKSPACE / "index"
INDEX = _env_path("WS_INDEX_PATH") or INDEX_DIR / "index.sqlite"

# Canonical, hand-edited description of the derived by-* browse trees.
FOLDER_ANATOMY = _env_path("WS_FOLDER_ANATOMY") or WORKSPACE / "folder-anatomy.yaml"


def update_projects_dir(path: str | Path | None) -> Path:
    return Path(path).expanduser() if path else PROJECTS


def scaffold_dirs() -> list[Path]:
    return [
        WORKSPACE, PROJECTS, LITERATURE, LITERATURE_ITEMS, DOCUMENTS,
        DOCUMENT_FILES, DOCUMENT_OBJECTS, RESOURCES, RESOURCE_ITEMS, TASKS,
        LOGISTICS, PEOPLE, ORGANISATIONS, EVENTS, COMMUNICATIONS, CAREER,
        PROFILE_ITEMS, PROFILE_APPLICATIONS, RELATIONS, INDEX_DIR,
        KNOWLEDGEBASE, KNOWLEDGEBASE / "generated",
    ]
