# Workspace Agent Orientation

This is the source orientation file for the workspace tooling:

```text
~/Projects/ws/
```

## Using ws or contributing to it

This file orients contributors working on ws itself. To operate a user's
workspace, start with [SKILL.md](SKILL.md) and the manual (`ws help`), plus that
workspace's local instructions.

Before changing code, read [the contract index](contracts/README.md) and only
those domain/shared contracts affected by the change. Contracts specify data
ownership, invariants and extension/compatibility rules. Put workflows in docs;
keep parser help authoritative for exact syntax. Update affected templates,
validators, help/effects and guides alongside the implementation.

Useful checks are `ws check cli` for command registration and isolated tests
under `cli/tests/`. Run data-dependent tests against a temporary workspace and
configuration; do not use the person's records as fixtures. `ws check` validates
an actual workspace without repairing it.

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
- In projects, prefer the standard folders: `in/` for inputs, `data/` for intermediate results, `out/` for finished outputs, `docs/` for stable documentation, `tmp/` for disposable scratch. Add a new top-level folder only when none fits, and record it in the project's `LOG.md`.
- Before ending a working session on a project, add an entry at the top of its `LOG.md`.
- Read project-local `AGENTS.md` before modifying a project.
- Ask before destructive operations or broad reorganizations.
