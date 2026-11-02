# Workspace Contract

Canonical root:

```text
~/workspace/
```

Do not create or use:

```text
/workspace
```

## Empty-scaffold rule

The workspace begins with real, empty directories:

```text
projects/items/
tasks/
literature/items/
documents/items/
documents/files/
resources/items/
logistics/{people,organisations,events,communications}/
profile/{items,applications}/
relations/
index/
wiki/generated/
```

Derived `by-*` browse trees appear beside each domain's `items/` store when
views are first rebuilt; they are disposable and not part of the scaffold.
`ws rebuild dashboard` writes one derived file at the root, `dashboard.html`
([dashboard contract](dashboard.md)); it is the only generated file there.
Their shapes are declared in the canonical root file
`~/workspace/folder-anatomy.yaml` (see `folder-anatomy.md`).

The scaffold contains no records or imported content. `ws init` also writes
default taxonomies, browse settings, a local README and agent instructions,
and creates an empty search index. Its directories are not
symlinks to pre-existing content trees. Existing material remains unchanged in
`~/Projects`, `~/Documents`, `~/Literature`, and `~/Utils` until deliberately
brought into the workspace. Filesystem visibility is not workspace membership.

Do not create additional top-level folders by default.

## Initialisation

`ws init [--root DIR]` creates missing infrastructure and saves the selected
root as `workspace_root` in `~/.config/ws/config.yaml` (override: `WS_CONFIG`).
`--root` takes precedence for this command; `WS_WORKSPACE_ROOT` takes precedence
over the saved root for subsequent commands. All default domain locations derive
from that root; existing domain-specific environment overrides remain supported.

Repeated initialisation preserves personal files, taxonomies and browse settings.
An explicit new root switches the default; it never relocates old content.
Conflicting files and symlinks in required infrastructure are refused. No content
is imported, no account is authenticated, and no Git repository is created at the
workspace root. A full check runs at the end; pre-existing inconsistencies are
reported rather than silently repaired.

## Derived layers

Four layers are derived from the canonical stores and the relations: each
domain's `by-*` browse trees ([folder anatomy](folder-anatomy.md)), the search
index ([search](search.md)), `wiki/generated/` ([wiki](wiki.md)) and
`dashboard.html` ([dashboard](dashboard.md)). `ws rebuild` regenerates them in
that order; `ws rebuild TARGET` regenerates one, and `ws rebuild views DOMAIN`
one domain's trees.

- Rebuilding reads records and relations and writes only the derived layer.
  It never changes a canonical record and never invalidates the search index.
- A browse-settings error is reported before any tree is wiped, so the
  previous trees stand. Bare `ws rebuild` still regenerates the other layers,
  which do not read the browse settings, and exits non-zero.
- The earlier per-layer spellings (`ws <domain> views rebuild`,
  `ws index rebuild`, `ws wiki build`, `ws dashboard build`) remain aliases
  of the same command. They print the current spelling on stderr.

The remaining services are stateless inside the workspace:

- `check` validates existing state
- `completions` prints shell integration

## System Files

Active workspace system files live outside the managed content root:

```text
~/Projects/ws/
```

Shared root agent orientation lives in:

```text
~/Projects/ws/AGENTS.md
```

## Side-Effect Tiers

Use these meanings consistently:

```text
in/       inputs the work consumes
data/     intermediate results
out/      finished outputs
docs/     stable documentation
tmp/      disposable scratch
LOG.md    what happened, newest first
```

## Path Portability

Prefer relative paths throughout the workspace. A tracked file must not encode a host-specific absolute path when the target is inside the same project, repository, or workspace and can be addressed relative to a declared root.

Use these conventions:

- resolve project-local paths relative to the project root or the file that owns the reference
- use canonical `kind:key` REFs for cross-workspace relationships instead of
  names, aliases, internal IDs, or filesystem paths
- make scripts derive their own project or repository root rather than assuming the caller's working directory
- use `~/workspace/...` only in human-facing documentation and examples, not as a machine-specific stored path
- after moving a directory, repair or regenerate runtime metadata that still points to its former location

Absolute paths are allowed only when the target is inherently host-specific or external, such as a mounted data volume, an installed toolchain, or generated virtual-environment launch metadata that requires an absolute interpreter path. Keep such values in host-local or untracked configuration when possible, and document the exception and relocation procedure.
