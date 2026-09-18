# Project Contract

Usage: [Project setup](../docs/project-setup.md) and
[installing capabilities](../docs/project-install.md).

The projects domain root holds the flat canonical store, the derived browse
trees, and the taxonomy:

```text
<projects-domain>/
  items/<project>/            flat canonical store: one folder per project
  by-type/  by-field/  by-status/  by-organisation/  by-event/   derived views
  project-taxonomy.yaml
```

`ws create project` resolves the projects store in this order:

```text
--in DIR
WS_PROJECTS_DIR
<resolved-workspace-root>/projects/items
```

The workspace root resolves from environment, saved configuration, then the
default; see [configuration](../docs/reference/configuration.md).

`WS_PROJECTS_DIR` points at the store; the domain root is its parent unless
`WS_PROJECTS_DOMAIN` overrides it.

Project names are stored as lowercase kebab-case. The CLI accepts separate name
words and normalizes them, so `ws create project test project` creates
`test-project/`.

**The store is flat.** A project's identity is its folder name, which must be
unique across the store. `ws create project` refuses path names — grouping
folders are retired; grouping is expressed through `fields`, `keywords`, and
relation edges, and browsed through the derived `by-*` views, where
reorganising is free and never changes identity. Discovery stays tolerant of
hand-nested legacy projects (their identity is the relative path), but
nothing creates new ones.

## Subprojects

A subproject is a project co-located *inside* another project to borrow its
virtual environment — a concept justified by coding projects: the paper about
a simulation toolkit lives beside the code it runs, shares the toolkit's
`.venv`, but keeps its own history. Created with `ws create subproject`,
it carries a `subproject.yaml`, **not** a `project.yaml`, which keeps the
structural relationship: discovery keeps the enclosing project as the parent
(so the subproject never appears in `ws list projects`, and `ws projects
install` run from inside it sets up the *parent's* environment). It has its
own `code/`, `data/`, and `results/` and **its own git repository, ignored by
the parent's** (`create-subproject` runs `git init` and appends the
subproject's path to the parent's `.gitignore`), but no `.venv` of its own
(`subproject.yaml` records the parent's, e.g. `venv: ../../.venv`).

Identity-wise a subproject *is* a project: the catalog projects it as
`project:<parent-relpath>/<sub-relpath>`, so it resolves, relates to any other
object, and appears in relationship renderings. Sub-ness is structure and
environment-sharing, never identity. `ws show project:<parent>` lists a
project's subprojects.

Subprojects may sit inside plain grouping folders within the project — folders
that exist only to name a family of subprojects. Run `ws create subproject` from
inside the grouping folder, or give a path name (`ws create subproject
shuttling/corner`); missing grouping folders are created. The recorded `venv:`
path adjusts to the depth. Subprojects never nest inside one another, and the
standard content folders (`code/`, `data/`, `docs/`, ...) cannot serve as
grouping folders — both are refused.

## Required Files

```text
project.yaml
README.md
AGENTS.md
CLAUDE.md
.gitignore
```

`CLAUDE.md` is a symlink to `AGENTS.md` (on Windows, an `@AGENTS.md` import instead), so Claude Code reads the same instructions. Both files must convey the same project instructions.

## Allowed Optional Top-Level Folders

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

`ws create project` creates `code/`, `paper/`, and `data/` only when their corresponding `--has-code`, `--has-paper`, or `--has-data` flag is supplied. Other allowed folders are created when first needed. The default scaffold contains no empty optional folders.

This keeps project creation minimal and modular. Git does not track empty directories, and `out/` and `tmp/` are intentionally ignored.

No other top-level project folders by default.

## `project.yaml`

Machine-readable project identity and routing metadata.

Required keys:

```yaml
schema_version: 1
name: <lowercase-kebab-name>
title: <human title>
type: paper
status: active
created: YYYY-MM-DD
description: >
  One paragraph.
fields: [physics]
subfields: [spin-qubits, shuttling]
keywords: []
has_code: false
has_paper: false
has_data: false
has_slides: false
server_compute: false
runtime:
  python: false
  venv: ""
project_dependencies: []
hosts: [mac]
sync:
  primary_host: mac
  remotes: []
  git: []
  data: []
```

Allowed `type` values are configured in:

```text
~/workspace/projects/project-taxonomy.yaml
```

Default `type` values ("what kind of undertaking is this?"):

```text
research
paper
talk
software
teaching
organizatorial
other
```

Allowed `fields` and `subfields` are also configured in
`~/workspace/projects/project-taxonomy.yaml`; both are shared with literature:

```yaml
fields: [physics, mathematics, computer-science, ai, humanities]
subfields:
  physics: [quantum-information, quantum-computing, spin-qubits, shuttling,
            numerics, quantum-chemistry, experimental]
  mathematics: [tooling, numerics]
```

`fields` are broad disciplines. `subfields` are narrower controlled values,
and every selected subfield must belong to at least one selected field. Both
classifiers may be multi-valued. The hierarchy stops at these two levels;
`keywords` remain free-form descriptors such as `raman`, `qudit`, or
`reweighting`.

Conceptual project links are canonical edges in the relations service, not
YAML fields: `ws relate project:<key> to <other-kind>:<key> as depends-on`
(or `related`). Relations are created exclusively with `ws relate` —
project creation takes no relation flags and asks no relation questions.
The one exception is derived, not asserted: recording a `--use-project`
install dependency also records its depends-on edge. `depends_on` and
`related` lists in project.yaml are read-only legacy: still validated by
`ws projects check`, no longer written. A depends-on edge does not imply
installing the other project's environment — that is what
`project_dependencies` is for.

`project_dependencies` records install recipes — how another project is set
up into this one at build time. The only `kind` is `package`: install the
other project as an editable Python package into this project's own `.venv`.
The former non-installing kinds (`knowledge`, `source`, `data`, `tool`) are
retired: a reference that installs nothing is a pure connection, which is an
edge's job. Legacy entries with those kinds remain readable and are ignored
by `ws projects install`.

Example:

```yaml
project_dependencies:
  - project: potential-generator-toolkit
    kind: package
    install: editable
    path: .
```

Recording an install dependency also creates the conceptual `depends-on`
edge for it — one statement about the world, stated once.

Every project owns its own virtual environment. Do not reuse another project's `.venv`; install local package dependencies into the current project's `.venv` instead.

The interactive creation wizard must explain an editable dependency install
into the new project's own venv and show the command before execution.

### Custom install steps (`package_install`)

A project whose build needs more than a plain editable install declares its own
recipe in its `project.yaml`:

```yaml
package_install:
  - "{python} -m pip install scikit-build-core pybind11 ninja cmake"
  - "{python} -m pip install -e {path} --no-build-isolation"
```

When a consumer installs that project as a `package` dependency, these steps run
in order instead of the default `pip install -e` — `{python}` is the consumer's
venv interpreter and `{path}` is the dependency's installable path. A failing
step aborts that dependency's install with a warning. The recipe lives with the
project that needs it, so consumers stay generic.

### Capability materialization

Install records requested capabilities and their prerequisites, then materializes
recorded state. The chain is slides → venv → python → code. Replaying existing
state is supported; install never unsets capabilities. Every project owns its
venv except a structural subproject, which shares its parent's.

Package dependency additions use the creation grammar and write their install
entry and `depends-on` edge. Duplicate entries are skipped. Unresolvable
references fail before writes. The enclosing project is the default target,
including when invoked within a subproject.

`has_slides: true` means the project builds decks with the `slide_factory`
generator: creation and `ws projects install` editable-install it from
`packages/slide_factory/` in the ws checkout into the project's `.venv`, then
editable-install every theme package listed under `slides.themes` in the
private ws configuration (project REFs or paths; a missing entry warns and is
skipped). The shipped package is brand-free: layouts, drawing helpers and one
neutral theme. Logos, organisation names and branded themes belong in theme
packages outside this repository and are discovered through the
`slide_factory.themes` entry-point group. Build scripts import `slide_factory`
(`from slide_factory import Deck`); the layouts and the theme-package recipe
are documented in `packages/slide_factory/README.md`.

A tool ships under `packages/` only if it is generic and brand-free, small,
materialised into projects rather than run as a service, and needs no
credentials.

Literature links are canonical `references` edges in the relations service, created exclusively with `ws relate project:<key> to literature:<ItemKey> as references`. Use them for structurally important project literature, not every citation in a manuscript. A `related_literature` list in project.yaml is read-only legacy: still validated by `ws projects check`, no longer written. Bibliographic details remain in the literature domain; narrative project detail remains in the project README.

Allowed `status` values are defined in `statuses.md`.

## `README.md`

Human-readable project overview.

Should contain:

- purpose
- current state
- important files or folders
- how to run/build/read the project, if applicable

## `AGENTS.md`

Project-wide instructions.

Should contain:

- read-first list
- allowed folders
- project-specific safety rules
- testing/build/review expectations

Project `AGENTS.md` should not accumulate session-specific state or durable agent memory.

## Git Boundary and Sync

Each project is its own git repository (`git init` at the project root). The
workspace `~/workspace` is **not** a git repository; only stores that
deliberately initialize Git are tracked.

Tracked (lightweight, editable):

```text
project.yaml
README.md
AGENTS.md
CLAUDE.md        (symlink to AGENTS.md)
docs/            (stable docs)
notes/           (kept working notes)
refs/            (small local references)
```

Never tracked:

```text
data/**          (heavy data; see allowlist below)
out/             (regenerable outputs)
tmp/             (scratch)
.claude/ .codex/ (agent sessions)
nested repos     (see below)
```

`data/` keeps only a manifest layer in git, via this `.gitignore` pattern:

```gitignore
data/**
!data/
!data/README.md
!data/**/*.md
!data/**/.gitkeep
```

Tiny curated data files go in `refs/` or `docs/`, or are force-added explicitly.

### Nested repositories

A project may contain its own sub-repositories — for example `paper/` cloned from Overleaf, or `code/` hosted on GitHub. The parent repo must **ignore** those paths (add `/paper/`, `/code/` to the project `.gitignore`) so they are never embedded as gitlinks. Each sub-repo manages its own history and remote independently. Use git submodules only when deliberate version pinning is wanted.

### Sync model

`ws sync` (planned) uses two channels and never conflates them:

- **git channel** — repos sync via `git push`/`pull` to their remotes (the parent repo and each nested repo independently). Never rsync `.git/`.
- **rsync channel** — gitignored heavy data (`data/`, `out/`) syncs via rsync with `--exclude .git`.

This is declared in `project.yaml`:

```yaml
sync:
  primary_host: mac
  remotes: []
  git: []
  data: []
```

`ws projects check` warns on tracked or working-tree files larger than 5 MB, so
heavy data cannot silently enter git.

## Templates

Use:

```text
~/Projects/ws/templates/project.yaml
~/Projects/ws/templates/AGENTS.md
~/Projects/ws/templates/gitignore
```

## Browse Views

Views are relative symlinks into the canonical store. They never change project
identity, and collisions receive numeric suffixes. Taxonomy values and relations
supply facets; shape, defaults and rebuilding follow
[folder anatomy](folder-anatomy.md).

## Extension and compatibility rules

- New project capabilities must declare prerequisite metadata and support both
  creation and subsequent materialization. Preserve per-project environments
  and the structural subproject exception.
- New package recipe features must preserve interpreter/path ownership and
  failure reporting. Do not reinterpret conceptual edges as install recipes.
- Preserve flat project identity and reads of legacy nested projects and
  retired non-installing dependency kinds. Do not resume writing legacy
  relationship lists into project metadata.
- Changes to required scaffold files, metadata or identity require
  [a compatibility/migration plan](README.md#changing-a-contract), with templates
  and validators updated together. Proposed sync behaviour is not implemented
  merely because routing metadata exists.
- Verify capability prerequisites, invalid dependency handling, subproject
  discovery and Git boundaries when changing the associated implementation.
