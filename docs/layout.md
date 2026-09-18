# ws layout

The repository holds the shared workspace logic and tooling.

## Shared

```text
~/Projects/ws/
  AGENTS.md
  CONSTITUTION.md
  contracts/    invariants code and canonical data must obey
  docs/
  templates/
  cli/          ws + ws_lib (the command-line tool)
  packages/     brand-free tools ws installs into projects (slide_factory)
```

Shared files define the root agent orientation, contracts, templates, and commands. They should work on both Mac and server unless explicitly documented otherwise.

Managed content domains (`projects/`, `literature/`, `documents/`, `resources/`, and the
rest) live under `~/workspace`, separate from this tooling repository; each may
have its own Git boundary.

## Projects

Projects live in the flat store at `~/workspace/projects/items/` and should usually be their own Git repositories; the derived `by-*` browse trees sit beside the store at the domain root. The allowed project types and fields live with the data in `~/workspace/projects/project-taxonomy.yaml`. Git manages code, papers, docs, and configuration. Future `ws sync` rules should handle large/generated files explicitly and must not sync `.git/`.
