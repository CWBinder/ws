# Workspace Agent Orientation

This is the source orientation file for the workspace tooling:

```text
~/Projects/ws/
```

## First Checks

Use the smallest relevant file before loading more context:

```text
contracts/README.md              contract index
contracts/workspace.md    workspace layout
contracts/project.md      project layout and metadata
contracts/library.md      literature library
contracts/career.md       CV/career system
contracts/relations.md    workspace objects, relationships, and graph
```

The main workspace command is:

```bash
ws --help
```

Useful checks:

```bash
ws check
ws projects check
ws search literature <query>
ws profile make-cv --help
```

## Main Areas

```text
~/workspace/          empty managed domain/service scaffold
~/Projects/           existing unmanaged project folders
~/Documents/          existing unmanaged documents
~/Literature/         existing unmanaged literature
~/Utils/              existing unmanaged utilities
~/Projects/ws/        shared contracts, templates, and the ws CLI
```

The scaffold directories exist from the start, but content enters
`~/workspace` only through deliberate create or add operations. Do not
restore broad symlinks to unmanaged roots. See `contracts/workspace.md`.

The top-level data-owning domains are `projects`, `tasks`,
`literature`, `documents`, `resources`, `logistics`, and `profile`. The
`relations` store holds hand-asserted edges that cannot be regenerated;
`search` and `wiki` hold derived state that can be rebuilt; everything
else is stateless.

## Skills And Commands

Workspace executable skills and command code live in:

```text
cli/
cli/ws
cli/ws_lib/
```

Add reusable automation there when it is a deterministic command or workflow.
Keep shared behavior host-neutral unless a host-specific path or tool is truly required.

Assistant-level configuration (Claude Code agents, skills, memory) lives outside the workspace under the assistant's own home (e.g. `~/.claude/`). Do not confuse assistant-level skills with workspace commands. Workspace commands should stay available through `ws`.

## Safety Rules

- Do not store secrets in tracked files.
- Do not move or sync large data unless a project rule says to do so.
- Respect Git boundaries: workspace root is not a Git repo; managed projects
  and external source folders may be separate repos.
- Prefer `out/` for generated outputs, `tmp/` for disposable scratch, `notes/` for transient kept notes, and `docs/` for stable documentation.
- Read project-local `AGENTS.md` before modifying a project.
- Ask before destructive operations or broad reorganizations.
