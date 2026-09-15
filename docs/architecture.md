# Architecture

The workspace starts with an empty managed directory scaffold. The directories
exist immediately; files and first-class objects appear only when content is
deliberately created or added.

```text
~/workspace/
  projects/
    items/
  tasks/
  literature/
    items/
  documents/
    items/
    files/
  resources/
    items/
  logistics/
    people/
    organisations/
    events/
    communications/
  profile/
    items/
    applications/
  relations/
  index/
  wiki/
    generated/
```

Every directory in this initial tree is real. None is a symlink. `ws init`
adds infrastructure files and an empty search index, but no content records.

Canonical stores are flat `items/` folders (projects, literature, documents,
profile);
derived `by-*` symlink browse trees appear beside each store at the domain
root once views are rebuilt, and are always disposable. Their shapes are
declared in the canonical root file `~/workspace/folder-anatomy.yaml` and
built by one engine, `ws_lib/anatomy.py` (see `contracts/folder-anatomy.md`).

Existing unmanaged content remains outside:

```text
~/Projects/
~/Documents/
~/Literature/
~/Utils/
```

## Important split

Active installed system files remain outside the managed content root:

```text
~/Projects/ws/
  AGENTS.md
  CONSTITUTION.md
  contracts/      invariants code and canonical data must obey
  docs/
  templates/
  cli/            ws + ws_lib
```

## Future directions

- server sync — in progress (two-channel git + rsync; see `contracts/project.md` and `docs/projects-wiki-plan.md`)
- Obsidian project/workspace wiki — in place (`ws wiki build`; see `docs/visualization.md`)
- richer literature tools — v1 in place (`ws literature`)
- career / CV system — in place (`ws profile`; see `contracts/career.md`)
- phone/app overview — future
- voice control — future

## Shared object graph

Each domain owns its top-level directory. Relationships are cross-domain and
therefore have the dedicated workspace-root `relations/` service store.

The SQLite index and Obsidian Markdown are derived:

```text
relations/*.yaml                      canonical edges
index/index.sqlite                    rebuildable query index (objects + relationships)
wiki/generated/                       rebuildable Obsidian/wiki view
```

See `contracts/relations.md`.

## Documentation and executable knowledge

How-to material and normative behavior are deliberately separate:

```text
contracts/         invariants code and canonical data must obey (top level)
docs/guides/       setup and operating procedures
docs/reference/    exact paths, configuration, and command discovery
docs/concepts/     architectural reasoning
docs/policies/     human governance decisions
```

The parser plus `ws_lib/registry.py` is authoritative for available commands
and declared effects. `ws help`, `ws capabilities`, and `ws describe` read that
executable knowledge. Host-specific, non-secret connector selection comes from
`~/.config/ws/config.yaml`; credentials remain with each provider.
