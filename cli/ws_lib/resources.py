"""Folder-backed resource objects and bundle ingestion."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from ws_lib import anatomy, catalog, indexing, paths, records


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def folder(ref: catalog.ObjectRef) -> Path:
    if ref.type != "resource" or ref.path is None:
        fail(f"expected resource:<key>, got {ref.ref}")
    return ref.path.parent


def files(ref: catalog.ObjectRef) -> list[Path]:
    root = folder(ref)
    return sorted(
        path for path in root.rglob("*")
        if path.is_file() and path != ref.path and not path.name.startswith(".")
    )


def _touch(ref: catalog.ObjectRef) -> None:
    """Record that the resource bundle itself changed."""
    if ref.path is None:
        return
    data = records.load_record(ref.path)
    data["updated_at"] = records.now()
    records.atomic_write(ref.path, data)
    indexing.invalidate()


def _copy_or_move(source: Path, destination: Path, mode: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if mode == "move":
        shutil.move(str(source), str(destination))
    elif source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def command_path(args: argparse.Namespace) -> None:
    ref = catalog.resolve(args.resource, "resource")
    value = str(folder(ref))
    if args.json:
        print(json.dumps({"ref": ref.ref, "path": value}, indent=2, sort_keys=True))
    else:
        print(value)


def command_files(args: argparse.Namespace) -> None:
    ref = catalog.resolve(args.resource, "resource")
    root = folder(ref)
    values = [str(path.relative_to(root)) for path in files(ref)]
    if args.json:
        print(json.dumps({"ref": ref.ref, "files": values}, indent=2, sort_keys=True))
    else:
        print("\n".join(values) if values else "none")


def command_add(args: argparse.Namespace) -> None:
    ref = catalog.resolve(args.resource, "resource")
    source = Path(args.path).expanduser().resolve()
    if not source.exists():
        fail(f"path does not exist: {source}")
    destination = folder(ref) / (args.name or source.name)
    if destination.name == "resource.yaml":
        fail("resource.yaml is reserved for resource metadata")
    if destination.exists():
        fail(f"resource destination exists: {destination}")
    _copy_or_move(source, destination, args.mode)
    _touch(ref)
    payload = {
        "ref": ref.ref,
        "path": str(destination.relative_to(folder(ref))),
        "mode": args.mode,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"added: {payload['path']}")


def add_arguments(add: argparse.ArgumentParser) -> None:
    """The file-into-bundle arguments for `ws add resource:<key> <path>`."""
    add.add_argument("resource", metavar="REF", help="canonical resource:<key> reference")
    add.add_argument("path", help="file or folder to place inside the resource")
    add.add_argument("--name", help="destination name inside the resource")
    add.add_argument("--mode", choices=["move", "copy"], default="move",
                     help="move (default) or copy the source into the bundle")
    add.add_argument("--json", action="store_true")
    add.set_defaults(func=command_add)


def _rel_home(path: Path) -> str:
    try:
        return "~/" + str(path.resolve().relative_to(Path.home()))
    except ValueError:
        return str(path)


def command_views_rebuild(args: argparse.Namespace) -> None:
    counts = anatomy.rebuild_resources()
    if args.json:
        print(json.dumps({"root": str(paths.RESOURCES), "links": counts}, indent=2))
    else:
        print(f"rebuilt: {_rel_home(paths.RESOURCES)}/by-*")
        for name, count in sorted(counts.items()):
            print(f"  {name}: {count} links")


def add_parser(sub: argparse._SubParsersAction) -> argparse.ArgumentParser:
    parser = catalog.add_object_parser(
        sub,
        "resources",
        "resource",
        merge=False,
        help_text="Folder-backed bundles of arbitrary supporting files.",
    )
    actions = next(
        action for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    path_cmd = actions.add_parser("path", help="print the resource folder path")
    path_cmd.add_argument("resource", metavar="REF")
    path_cmd.add_argument("--json", action="store_true")
    path_cmd.set_defaults(func=command_path)
    files_cmd = actions.add_parser("files", help="list ordinary files in the resource")
    files_cmd.add_argument("resource", metavar="REF")
    files_cmd.add_argument("--json", action="store_true")
    files_cmd.set_defaults(func=command_files)
    views = actions.add_parser("views", help="manage the derived by-* rings")
    views_actions = views.add_subparsers(dest="resources_views_command", required=True)
    rebuild = views_actions.add_parser("rebuild", help="rebuild the derived by-* browse views from current data")
    rebuild.add_argument("--json", action="store_true")
    rebuild.set_defaults(func=command_views_rebuild)
    return parser
