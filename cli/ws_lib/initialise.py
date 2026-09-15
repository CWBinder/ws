"""Create missing workspace infrastructure without replacing personal files."""
import argparse
from pathlib import Path

from ws_lib import anatomy, config, document_taxonomy, indexing, paths
from ws_lib import profile_taxonomy, project, taxonomy


def _create(path: Path, text: str) -> bool:
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(text)
    except FileExistsError:
        return False
    print(f"created: {path}")
    return True


def command_init(_args):
    root = paths.WORKSPACE
    if root in {Path.home().resolve(), Path('/'), Path('/workspace')}:
        raise SystemExit("error: choose a dedicated workspace directory with --root DIR")
    if root == paths.SYSTEM.resolve() or paths.SYSTEM.resolve() in root.parents:
        raise SystemExit("error: keep the personal workspace outside the ws code checkout")
    files = [root / "README.md", root / "AGENTS.md", paths.PROJECT_TAXONOMY,
             paths.DOCUMENT_TAXONOMY, paths.PROFILE_TAXONOMY, paths.FOLDER_ANATOMY,
             config.CONFIG_PATH]
    # Refuse conflicting layouts before creating anything. Existing normal
    # files and directories are preserved, including a user's local instructions.
    for path in paths.scaffold_dirs():
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise SystemExit(f"error: expected a real directory: {path}")
    for path in files:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise SystemExit(f"error: expected a regular file: {path}")
    for path in paths.scaffold_dirs():
        path.mkdir(parents=True, exist_ok=True)
    if not paths.PROJECT_TAXONOMY.exists():
        taxonomy.write(paths.PROJECT_TAXONOMY, project.DEFAULT_TAXONOMY, project.PROJECT_TAXONOMY_HEADER)
    document_taxonomy.ensure()
    profile_taxonomy.ensure()
    lines = ["schema_version: 1", "", "# Personal browse settings. Missing domains use built-in defaults."]
    for domain, spec in anatomy.DEFAULTS.items():
        lines += ["", f"{domain}:", f"  rings: [{', '.join(spec['rings'])}]", f"  depth: {spec['depth']}"]
    paths.FOLDER_ANATOMY.parent.mkdir(parents=True, exist_ok=True)
    _create(paths.FOLDER_ANATOMY, "\n".join(lines) + "\n")
    _create(root / "README.md", f"""# My workspace

Personal content lives here: `{root}`.
The ws software lives separately at `{paths.SYSTEM}`.

## Start

- Run `ws --help` for an overview and `ws check` to validate the workspace.
- Follow the first example in [Getting started]({paths.SYSTEM / 'GETTING-STARTED.md'}).
- Find later workflows in the shared [usage guides]({paths.SYSTEM / 'docs/README.md'}).
- Use `ws search WORDS` to find records, then `ws show KIND:KEY` to inspect one.
- Add content deliberately. `ws add document FILE --mode copy` keeps the original.

## Layout

Projects, tasks, documents, resources, literature, contacts (`logistics/`) and
profile records each have their own store. `relations/` connects records.
`index/`, `wiki/generated/` and the `by-*` browse folders are rebuildable views.
Keep the whole workspace private unless you deliberately publish selected content.

Browse settings live in `folder-anatomy.yaml`; domain taxonomy files hold your
classification vocabulary. The defaults are enough to start.
""")
    _create(root / "AGENTS.md", f"""# Working in this workspace

Workspace root: `{root}`.
Read the generic ws operating manual at `{paths.SYSTEM / 'SKILL.md'}` when using ws.
Read shared usage guides at `{paths.SYSTEM / 'docs/README.md'}` for workflows.
Use `ws help COMMAND` for syntax and `ws describe COMMAND` for a guide and effects.
Find existing objects with `ws search`, and use their full `kind:key` references.
Use ws commands to create, ingest, classify and relate records. Read raw content
at the paths returned by `ws show`. In project folders, follow local `AGENTS.md`.
Do not put credentials in records or generated documentation.

## Local working conventions

Add instructions specific to this workspace here. Keep durable personal facts
in workspace records, and refer to them rather than copying them into this file.
""")
    config.save_workspace_root(root)
    if not paths.INDEX.exists():
        indexing.rebuild(quiet=True)
    print(f"workspace: {root}\nconfiguration: {config.CONFIG_PATH}")
    from ws_lib.cli import command_check
    command_check(argparse.Namespace(area=None, stale_after=180, json=False))
    print(f"Next: follow {paths.SYSTEM / 'GETTING-STARTED.md'}")
