import sys

if sys.version_info < (3, 10):
    sys.stderr.write(
        f"error: ws needs Python >= 3.10, but this is {sys.version.split()[0]} "
        f"({sys.executable})\nhint: on macOS the stock python3 is too old; "
        "run via a newer interpreter, e.g. `python3.12`\n"
    )
    raise SystemExit(1)

import argparse
import contextlib
import io
from pathlib import Path

from ws_lib import (
    anatomy,
    career,
    catalog,
    document_taxonomy,
    indexing,
    literature,
    logistics,
    paths,
    profile_taxonomy,
    project,
    resources,
    registry,
    relations,
    wiki,
)


WORKSPACE = paths.WORKSPACE
CLI = paths.CLI
SYSTEM = paths.SYSTEM
PROJECTS = paths.PROJECTS
CONTRACTS = paths.CONTRACTS
TOP_LEVEL_COMMANDS = [
    "--help",
    "init",
    "check",
    "projects",
    "tasks",
    "literature",
    "documents",
    "resources",
    "logistics",
    "profile",
    "relate",
    "unrelate",
    "show",
    "edit",
    "delete",
    "list",
    "create",
    "add",
    "relations",
    "id",
    "index",
    "search",
    "completions",
    "wiki",
    "domains",
    "help",
    "capabilities",
    "describe",
]
CREATE_COMMANDS = ["project", "subproject", "task", "resource", "profile", "agent", "subagent"]
PROJECT_COMMANDS = ["install", "taxonomy", "add-type", "add-field", "add-subfield", "check", "views"]
LITERATURE_COMMANDS = [
    "init",
    "search-arxiv",
    "taxonomy",
    "add-field",
    "add-subfield",
    "views",
    "enrich",
    "download-source",
    "download-pdf",
    "attach-pdf",
    "attach-source",
    "citations",
    "cited-by",
]
LITERATURE_ITEM_COMMANDS = [
    "enrich",
    "download-source",
    "download-pdf",
    "attach-pdf",
    "attach-source",
    "citations",
    "cited-by",
]
CAREER_COMMANDS = [
    "init", "taxonomy", "add-type", "views", "make-cv",
]
OBJECT_COMMANDS = ["ensure", "merge"]
TASK_COMMANDS = ["ensure"]
DOCUMENT_COMMANDS = ["taxonomy", "types", "views"]
RELATIONS_COMMANDS = ["edit"]
INDEX_COMMANDS = ["rebuild", "stat"]
ID_COMMANDS = ["resolve", "show"]
COMPLETION_SHELLS = ["bash", "zsh"]


def fail(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def rel_home(path: Path) -> str:
    try:
        return "~/" + str(path.expanduser().relative_to(Path.home()))
    except ValueError:
        try:
            return "~/" + str(path.resolve().relative_to(Path.home()))
        except ValueError:
            return str(path)


def command_help(_args: argparse.Namespace) -> None:
    # One overview text for bare `ws`, `ws --help`, and bare `ws help`.
    registry.print_overview()


def workspace_scaffold_dirs() -> list[Path]:
    return paths.scaffold_dirs()


def required_dirs() -> list[Path]:
    return [
        *workspace_scaffold_dirs(),
        SYSTEM / "docs",
        SYSTEM / "templates",
        CLI,
    ]


def workspace_findings() -> list[dict]:
    findings: list[dict] = []
    for path in required_dirs():
        if not path.exists():
            findings.append({"severity": "error", "message": f"missing: {rel_home(path)}"})
    for path in [
        SYSTEM / "AGENTS.md",
        CONTRACTS / "README.md",
        CONTRACTS / "objects.md",
        CONTRACTS / "workspace.md",
        CONTRACTS / "project.md",
        CONTRACTS / "projects.md",
        CONTRACTS / "statuses.md",
        CONTRACTS / "library.md",
        CONTRACTS / "career.md",
        CONTRACTS / "relations.md",
        CONTRACTS / "cli.md",
        CONTRACTS / "tasks.md",
        CONTRACTS / "documents.md",
        CONTRACTS / "resources.md",
        CONTRACTS / "literature.md",
        CONTRACTS / "logistics.md",
        CONTRACTS / "profile.md",
        CONTRACTS / "search.md",
        CONTRACTS / "check.md",
        CONTRACTS / "wiki.md",
        CONTRACTS / "folder-anatomy.md",
        project.PROJECT_TAXONOMY,
    ]:
        if not path.exists():
            findings.append({"severity": "error", "message": f"missing: {rel_home(path)}"})
    if Path("/workspace").exists():
        findings.append({"severity": "error", "message": "unexpected: /workspace exists"})
    return findings


def project_findings() -> list[dict]:
    output = io.StringIO()
    failed = False
    try:
        with contextlib.redirect_stdout(output):
            project.command_project_check(argparse.Namespace(projects_dir=None))
    except SystemExit:
        failed = True
    results: list[dict] = []
    current = ""
    for line in output.getvalue().splitlines():
        if line and not line.startswith(" ") and line.endswith(":"):
            current = line[:-1]
            continue
        stripped = line.strip()
        if stripped.startswith("problem:"):
            results.append({
                "severity": "error",
                "id": current,
                "message": stripped.removeprefix("problem:").strip(),
            })
        elif stripped.startswith("note:"):
            results.append({
                "severity": "warning",
                "id": current,
                "message": stripped.removeprefix("note:").strip(),
            })
    if failed and not any(row["severity"] == "error" for row in results):
        results.append({"severity": "error", "message": "project check failed"})
    return results


def command_check(args: argparse.Namespace) -> None:
    area = getattr(args, "area", None)
    stale_after = getattr(args, "stale_after", 180)
    results: dict[str, list[dict]] = {}
    if area in (None, "workspace"):
        results["workspace"] = workspace_findings()
    if area in (None, "projects"):
        results["projects"] = project_findings()
    if area in (None, "catalog"):
        results["catalog"] = catalog.findings(stale_after=stale_after)
    if area == "tasks":
        results["tasks"] = catalog.findings({"task"}, stale_after=stale_after)
    if area == "documents":
        results["documents"] = catalog.findings({"document"}, stale_after=stale_after)
    if area == "resources":
        results["resources"] = catalog.findings({"resource"}, stale_after=stale_after)
    if area in (None, "documents"):
        results["document-taxonomy"] = document_taxonomy.findings()
    if area == "logistics":
        results["logistics"] = catalog.findings(
            {"person", "organisation", "event"},
            stale_after=stale_after,
        )
    if area in (None, "literature"):
        rows = literature.classifier_findings()
        if literature.LITERATURE.exists():
            for bib in literature.list_item_bibtex_files():
                if not bib.read_text(encoding="utf-8").strip():
                    rows.append({"severity": "error", "id": bib.parent.name, "message": "empty citation.bib"})
        results["literature"] = rows
    if area in (None, "profile"):
        results["profile"] = career.findings() if career.CAREER.exists() else []
    if area in (None, "relations"):
        results["relations"] = relations.findings()
    if area in (None, "anatomy"):
        results["anatomy"] = anatomy.findings()
    if area in (None, "index"):
        results["index"] = indexing.findings()
    if area in (None, "cli"):
        results["cli"] = registry.cli_findings(build_parser()) + registry.completion_findings(
            {"bash": bash_completion_script(), "zsh": zsh_completion_script()}
        )
    failed = any(
        finding.get("severity") == "error"
        for findings in results.values()
        for finding in findings
    )
    if getattr(args, "json", False):
        import json
        print(json.dumps({"ok": not failed, "checks": results}, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for name, findings in results.items():
            if not findings:
                print(f"ok: {name}")
                continue
            for finding in findings:
                print(f"{finding.get('severity', 'error')}: {name}: {finding.get('id', '')} {finding['message']}".rstrip())
    if failed:
        raise SystemExit(1)


def list_literature_item_keys() -> list[str]:
    items = literature.LITERATURE_ITEMS
    if not items.exists():
        return []
    return sorted(path.name for path in items.iterdir() if path.is_dir() and (path / "citation.bib").exists())


def completion_values(kind: str) -> list[str]:
    taxonomy = project.load_taxonomy()
    values = {
        "commands": TOP_LEVEL_COMMANDS,
        "completion-shells": COMPLETION_SHELLS,
        "projects": [f"project:{name}" for name in project.existing_project_names()],
        "project-types": taxonomy["type"],
        "project-statuses": project.PROJECT_STATUSES,
        "project-fields": taxonomy["fields"],
        "project-subfields": project.all_subfields(taxonomy),
        "create-commands": CREATE_COMMANDS,
        "project-commands": PROJECT_COMMANDS,
        "literature-commands": LITERATURE_COMMANDS,
        "literature-item-keys": [f"literature:{key}" for key in list_literature_item_keys()],
        "literature-types": literature.LITERATURE_TYPES,
        "arxiv-sort-orders": ["relevance", "lastUpdatedDate", "submittedDate"],
        "career-commands": CAREER_COMMANDS,
        "career-variants": sorted(career.VARIANTS),
        "profile-types": profile_taxonomy.type_ids(),
        "profile-objects": [obj.ref for obj in catalog.public_stored_objects("profile")],
        "resource-objects": [obj.ref for obj in catalog.public_stored_objects("resource")],
        "document-objects": [obj.ref for obj in catalog.public_stored_objects("document")],
        "object-commands": OBJECT_COMMANDS,
        "task-commands": TASK_COMMANDS,
        "document-commands": DOCUMENT_COMMANDS,
        "document-types": document_taxonomy.type_ids(),
        "relations-commands": RELATIONS_COMMANDS,
        "index-commands": INDEX_COMMANDS,
        "id-commands": ID_COMMANDS,
        "object-refs": [obj.ref for obj in catalog.all_objects()],
    }
    return values.get(kind, [])


def command_complete(args: argparse.Namespace) -> None:
    for value in completion_values(args.kind):
        print(value)


def command_complete_path(args: argparse.Namespace) -> None:
    path = [word for word in args.path if not word.startswith("-")]
    parser = registry.resolve_parser(args.root_parser, path)
    if parser is None:
        return
    for name in sorted(registry._subcommands(parser)):
        candidate = tuple(path) + (name,)
        if name.startswith("__") or registry.is_compatibility_path(candidate):
            continue
        print(name)


def command_complete_flags(args: argparse.Namespace) -> None:
    """Option strings for a command path, read from the parser itself.

    Completion never hand-maintains flag lists: a removed flag disappears
    from the shell the moment it leaves the parser."""
    # Trailing flags the user already typed are not part of the command path.
    path = [word for word in args.path if not word.startswith("-")]
    # `ws edit document:<key> --<TAB>`: the REF names the kind, whose flags
    # live on a parser built at dispatch time rather than in the tree.
    if len(path) == 2 and path[0] == "edit" and ":" in path[1]:
        kind = path[1].split(":", 1)[0]
        flags = argparse.ArgumentParser(add_help=False)
        try:
            if kind == "literature":
                literature.literature_edit_arguments(flags)
            elif kind == "profile":
                career.profile_edit_arguments(flags)
            elif kind in catalog.SPECS:
                catalog._edit_arguments(flags, kind)
            else:
                return
        except Exception:
            return
        parser = flags
    else:
        while path and registry.resolve_parser(args.root_parser, path) is None:
            path = path[:-1]
        parser = registry.resolve_parser(args.root_parser, path)
    if parser is None:
        return
    for option in sorted(
        {
            option
            for action in parser._actions
            if action.help != argparse.SUPPRESS
            for option in action.option_strings
            if option not in {"-h", "--help"}
        }
    ):
        print(option)


def bash_completion_script() -> str:
    return r'''# ws bash completion
_ws_complete_from() {
  local values
  values="$(ws __complete "$1" 2>/dev/null)"
  COMPREPLY=( $(compgen -W "$values" -- "$cur") )
}

_ws_completion() {
  local cur prev command subcommand
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  command="${COMP_WORDS[1]}"
  subcommand="${COMP_WORDS[2]}"

  # Values for flags that take a controlled vocabulary.
  case "$prev" in
    --variant) _ws_complete_from career-variants; return ;;
    --field|--add-field|--remove-field) _ws_complete_from project-fields; return ;;
    --subfield|--add-subfield|--remove-subfield) _ws_complete_from project-subfields; return ;;
    --project|--use-project) _ws_complete_from projects; return ;;
    --status) _ws_complete_from project-statuses; return ;;
    --sort) _ws_complete_from arxiv-sort-orders; return ;;
    --entry-type|--kind) _ws_complete_from literature-types; return ;;
    --type)
      case "$subcommand" in
        profile|profiles) _ws_complete_from profile-types ;;
        document|documents) _ws_complete_from document-types ;;
        document:*) _ws_complete_from document-types ;;
        profile:*) _ws_complete_from profile-types ;;
        *) _ws_complete_from project-types ;;
      esac
      return
      ;;
  esac

  if [[ "$COMP_CWORD" -eq 1 ]]; then
    _ws_complete_from commands
    return
  fi

  # Flags come from the parser, never from a hand-kept list here.
  if [[ "$cur" == --* ]]; then
    local flag_values
    flag_values="$(ws __complete-flags "${COMP_WORDS[@]:1:COMP_CWORD-1}" 2>/dev/null)"
    if [[ -n "$flag_values" ]]; then
      COMPREPLY=( $(compgen -W "$flag_values" -- "$cur") )
      return
    fi
  fi

  # Subcommands and kind words come from the parser too.
  local path_values
  path_values="$(ws __complete-path "${COMP_WORDS[@]:1:COMP_CWORD-1}" 2>/dev/null)"
  if [[ -n "$path_values" ]]; then
    COMPREPLY=( $(compgen -W "$path_values" -- "$cur") )
    return
  fi

  # Operands: the REF verbs take any object, the specialists take their kind.
  case "$command" in
    show|edit|delete|relate|unrelate) _ws_complete_from object-refs; return ;;
    completions)
      if [[ "$COMP_CWORD" -eq 2 ]]; then _ws_complete_from completion-shells; fi
      return
      ;;
    add)
      if [[ "$subcommand" == "resource" || "$subcommand" == "resources" ]]; then
        if [[ "$COMP_CWORD" -eq 3 ]]; then _ws_complete_from resource-objects; fi
      fi
      return
      ;;
    create)
      if [[ "$subcommand" == "agent" || "$subcommand" == "subagent" ]] && [[ "$COMP_CWORD" -eq 3 ]]; then
        _ws_complete_from agent-roles
      fi
      return
      ;;
    literature)
      if [[ "$COMP_CWORD" -eq 3 ]]; then _ws_complete_from literature-item-keys; fi
      return
      ;;
    projects)
      if [[ "$subcommand" == "install" ]]; then
        local features="code paper data python venv slides"
        if [[ "$COMP_CWORD" -eq 3 ]]; then
          local values
          values="$(ws __complete projects 2>/dev/null)"
          COMPREPLY=( $(compgen -W "$values $features" -- "$cur") )
        else
          COMPREPLY=( $(compgen -W "$features" -- "$cur") )
        fi
        return
      fi
      if [[ "$COMP_CWORD" -eq 3 ]]; then _ws_complete_from projects; fi
      return
      ;;
    resources)
      if [[ "$COMP_CWORD" -eq 3 ]]; then _ws_complete_from resource-objects; fi
      return
      ;;
    agents)
      if [[ "$COMP_CWORD" -eq 3 ]]; then
        case "$subcommand" in
          add-skill|show-skill|create-skill) _ws_complete_from agent-skills ;;
          list) _ws_complete_words "roles skills" ;;
          *) _ws_complete_from agent-roles ;;
        esac
      fi
      return
      ;;
  esac
}

complete -F _ws_completion ws
'''


def zsh_completion_script() -> str:
    return r'''#compdef ws
# ws zsh completion
_ws_values() {
  ws __complete "$1" 2>/dev/null
}

_ws_compadd_kind() {
  local -a values
  values=("${(@f)$(_ws_values $1)}")
  (( ${#values[@]} )) && compadd -- "${values[@]}"
}

_ws() {
  local cur prev command subcommand
  cur="${words[CURRENT]}"
  prev="${words[CURRENT-1]}"
  command="${words[2]}"
  subcommand="${words[3]}"

  # Values for flags that take a controlled vocabulary.
  case "$prev" in
    --variant) _ws_compadd_kind career-variants; return ;;
    --field|--add-field|--remove-field) _ws_compadd_kind project-fields; return ;;
    --subfield|--add-subfield|--remove-subfield) _ws_compadd_kind project-subfields; return ;;
    --project|--use-project) _ws_compadd_kind projects; return ;;
    --status) _ws_compadd_kind project-statuses; return ;;
    --sort) _ws_compadd_kind arxiv-sort-orders; return ;;
    --entry-type|--kind) _ws_compadd_kind literature-types; return ;;
    --type)
      case "$subcommand" in
        profile|profiles) _ws_compadd_kind profile-types ;;
        document|documents) _ws_compadd_kind document-types ;;
        document:*) _ws_compadd_kind document-types ;;
        profile:*) _ws_compadd_kind profile-types ;;
        *) _ws_compadd_kind project-types ;;
      esac
      return
      ;;
  esac

  if (( CURRENT == 2 )); then
    _ws_compadd_kind commands
    return
  fi

  # Flags come from the parser, never from a hand-kept list here.
  if [[ "$cur" == --* ]]; then
    local -a flag_values
    flag_values=("${(@f)$(ws __complete-flags ${words[2,CURRENT-1]} 2>/dev/null)}")
    if (( ${#flag_values[@]} )); then
      compadd -- "${flag_values[@]}"
      return
    fi
  fi

  # Subcommands and kind words come from the parser too.
  local -a path_values
  path_values=("${(@f)$(ws __complete-path ${words[2,CURRENT-1]} 2>/dev/null)}")
  if (( ${#path_values[@]} )); then
    compadd -- "${path_values[@]}"
    return
  fi

  # Operands: the REF verbs take any object, the specialists take their kind.
  case "$command" in
    show|edit|delete|relate|unrelate) _ws_compadd_kind object-refs; return ;;
    completions)
      if (( CURRENT == 3 )); then _ws_compadd_kind completion-shells; fi
      return
      ;;
    add)
      if [[ "$subcommand" == "resource" || "$subcommand" == "resources" ]]; then
        if (( CURRENT == 4 )); then _ws_compadd_kind resource-objects; fi
      fi
      return
      ;;
    create)
      if [[ "$subcommand" == "agent" || "$subcommand" == "subagent" ]] && (( CURRENT == 4 )); then
        _ws_compadd_kind agent-roles
      fi
      return
      ;;
    literature)
      if (( CURRENT == 4 )); then _ws_compadd_kind literature-item-keys; fi
      return
      ;;
    projects)
      if [[ "$subcommand" == "install" ]]; then
        if (( CURRENT == 4 )); then _ws_compadd_kind projects; fi
        compadd -- code paper data python venv slides
        return
      fi
      if (( CURRENT == 4 )); then _ws_compadd_kind projects; fi
      return
      ;;
    resources)
      if (( CURRENT == 4 )); then _ws_compadd_kind resource-objects; fi
      return
      ;;
    agents)
      if (( CURRENT == 4 )); then
        case "$subcommand" in
          add-skill|show-skill|create-skill) _ws_compadd_kind agent-skills ;;
          list) compadd -- roles skills ;;
          *) _ws_compadd_kind agent-roles ;;
        esac
      fi
      return
      ;;
  esac
}

compdef _ws ws
'''


def command_completions(args: argparse.Namespace) -> None:
    if args.shell == "bash":
        print(bash_completion_script(), end="")
        return
    if args.shell == "zsh":
        print(zsh_completion_script(), end="")
        return
    fail(f"shell must be one of: {', '.join(COMPLETION_SHELLS)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ws", add_help=False)
    parser.add_argument("--help", action="store_true")
    parser.add_argument(
        "--receipt",
        action="store_true",
        help="print a structured success receipt after the command",
    )
    sub = parser.add_subparsers(dest="command")

    from ws_lib import initialise
    init = sub.add_parser(
        "init", help="initialise a workspace with defaults",
        description="Create missing workspace infrastructure, preserve existing files, and save the workspace location.",
    )
    init.add_argument("--root", metavar="DIR", help="workspace directory; defaults to WS_WORKSPACE_ROOT, saved configuration, or ~/workspace")
    init.set_defaults(func=initialise.command_init)

    check = sub.add_parser(
        "check",
        help="validate the workspace against the contracts",
        description="Validate workspace state against the contracts, area by area.",
    )
    check.add_argument(
        "area",
        nargs="?",
        choices=[
            "workspace",
            "projects",
            "tasks",
            "literature",
            "documents",
            "resources",
            "logistics",
            "profile",
            "catalog",
            "relations",
            "anatomy",
            "index",
            "cli",
        ],
        metavar="AREA",
        help="one area (workspace, projects, tasks, literature, "
        "documents, resources, logistics, profile, catalog, relations, "
        "anatomy, index, cli); bare `ws check` runs everything",
    )
    check.add_argument("--stale-after", type=int, default=180,
                       help="days before a derived view counts as stale")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=command_check)

    # Canonical domains: only each kind's specialists live here. The generic
    # verbs exist exactly once, verb-first.
    project.add_parser(sub, "projects")
    catalog.add_object_parser(sub, "tasks", "task", merge=False)
    literature.add_parser(sub)
    catalog.add_document_parser(sub)
    resources.add_parser(sub)
    logistics.add_parser(sub)
    career.add_parser(sub, "profile")

    # Universal verbs: REF verbs read the kind from the REF; list, search,
    # create, and add take it as their first word.
    catalog.add_show_parser(sub)
    catalog.add_edit_parser(sub)
    catalog.add_delete_parser(sub)
    catalog.add_list_parser(sub)
    catalog.add_add_parser(sub)
    create_sub = project.add_create_parser(sub)
    catalog.extend_create_parser(create_sub)
    career.attach_create_parser(create_sub, name="profile")

    # Global namespaces: maintenance commands.
    relations.add_parsers(sub)
    indexing.add_parsers(sub)
    wiki.add_parser(sub)

    # Stable low-level identity and graph utilities.
    catalog.add_id_parser(sub)

    completions = sub.add_parser("completions", help="print shell completion script for bash or zsh")
    completions.add_argument("shell", choices=COMPLETION_SHELLS)
    completions.set_defaults(func=command_completions)

    complete = sub.add_parser("__complete", help=argparse.SUPPRESS)
    complete.add_argument("kind")
    complete.set_defaults(func=command_complete)

    # REMAINDER: the shell passes the words typed so far verbatim, flags included.
    complete_path = sub.add_parser("__complete-path", help=argparse.SUPPRESS)
    complete_path.add_argument("path", nargs=argparse.REMAINDER)
    complete_path.set_defaults(func=command_complete_path, root_parser=parser)

    complete_flags = sub.add_parser("__complete-flags", help=argparse.SUPPRESS)
    complete_flags.add_argument("path", nargs=argparse.REMAINDER)
    complete_flags.set_defaults(func=command_complete_flags, root_parser=parser)

    registry.add_parsers(sub, parser)
    registry.finalize_help(parser)
    registry.install_flag_position_hints(parser)
    registry.bind_command_paths(parser)
    return parser


def main() -> None:
    parser = build_parser()
    argv = catalog.expand_add_target(sys.argv[1:])
    registry.enforce_flags_last(parser, argv)
    args = parser.parse_args(argv)
    if args.help or not args.command:
        command_help(args)
        return
    try:
        args.func(args)
    except (KeyboardInterrupt, EOFError):
        print("\ncancelled", file=sys.stderr)
        raise SystemExit(130)
    command_path = getattr(args, "_ws_command_path", args.command)
    # Effects are keyed by the kind's home spelling; hoisted paths
    # (`add person`, `create task`) canonicalize onto it.
    canonical_path = " ".join(registry.canonical_command_path(command_path.split()))
    effect = registry.EFFECTS.get(canonical_path, registry.EFFECTS.get(command_path.split()[0]))
    if (
        effect
        and effect.writes
        and canonical_path not in {"index rebuild", "init"}
        # Agents are tooling configuration, not objects: their writes never
        # change the search corpus, so they do not invalidate the index.
        and not canonical_path.startswith("agents ")
        and not getattr(args, "dry_run", False)
    ):
        # Older adapter domains do not all own the search service directly;
        # this central boundary keeps their successful mutations honest.
        indexing.invalidate()
    if args.receipt:
        registry.print_receipt(command_path)


if __name__ == "__main__":
    main()
