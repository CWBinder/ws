# Workspace Constitution

Every human or agent working in this workspace follows these rules.

## Core root

The canonical managed root is:

```text
~/workspace
```

It begins as an empty scaffold of real directories — none is a symlink.
Content enters the workspace only through deliberate `ws` create or add
operations. Filesystem visibility is not workspace membership.

The data-owning domains are `projects/`, `tasks/`, `resources/`,
`literature/`, `documents/`, `logistics/`, and `profile/`. Persistent service
state lives in `relations/`, `index/`, and `wiki/`; everything under
`index/` and `wiki/generated/` is derived and rebuildable.

Do not create additional top-level folders by default.

Do not create or use `/workspace`.

## Unmanaged roots

Pre-existing content stays where it is:

```text
~/Projects/
~/Documents/
~/Literature/
~/Utils/
```

These roots are unmanaged: `ws` does not own, move, or restructure them.
Material comes under management by deliberately adding it into
`~/workspace`. Do not restore broad symlinks from the workspace to unmanaged
roots.

## System split

The machinery — contracts, templates, and the `ws` CLI — lives outside the
managed content root:

```text
~/Projects/ws/
```

## Project contract

Detailed project file contracts are defined in:

```text
~/Projects/ws/contracts/README.md
```

Every project under `~/workspace/projects/items/` has:

```text
project.yaml
README.md
AGENTS.md
CLAUDE.md
LOG.md
.gitignore
in/
out/
```

and, with their capabilities, `code/`, `data/`, `paper/` and `slides/`.
`docs/`, `refs/` and `tmp/` are conventional folders, created when first
needed. These standard folders are the minimum, not a limit: other top-level
folders are allowed.

## Side-effect tiers

- `tmp/` — disposable scratch
- `data/` — intermediate results
- `out/` — finished outputs
- `in/`, `code/`, `paper/`, `slides/`, `docs/`, `refs/`, `LOG.md` — canonical
  project material

## Agents

Agents write narrowly. They put material in the standard folder that fits,
add a new top-level folder only when none does, and record it with the reason
in the project's `LOG.md`. Before ending a working session on a project they
add a `LOG.md` entry.

## AI attribution

Never add `Co-Authored-By: Claude`, `Co-Authored-By: Codex`, or any similar AI attribution to anything — commits, files, code, comments, documents, or anywhere else. Ever.

## Skills

Reusable actions belong in `~/Projects/ws/cli/`, exposed through `ws`.
