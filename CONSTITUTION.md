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
.gitignore
```

Allowed optional project folders:

```text
code/
paper/
data/
docs/
refs/
notes/
out/
tmp/
```

No other top-level project folders without explicit user instruction.

## Side-effect tiers

- `tmp/` — disposable scratch
- `notes/` — transient but kept
- `out/` — generated/regenerable outputs
- `code/`, `paper/`, `data/`, `docs/`, `refs/` — canonical project material

## Agents

Agents write narrowly and do not invent folder structures.

## AI attribution

Never add `Co-Authored-By: Claude`, `Co-Authored-By: Codex`, or any similar AI attribution to anything — commits, files, code, comments, documents, or anywhere else. Ever.

## Skills

Reusable actions belong in `~/Projects/ws/cli/`, exposed through `ws`.
