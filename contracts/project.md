# Project Contract

Usage: `ws help projects`, `ws help create project` and
`ws help projects install`.

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
default; see `ws help configuration`.

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
own `.context/` (log and purpose, as in [Context](#context)), `in/`, `code/`,
`data/` and `out/`, with the meanings in
[Folders](#folders), and **its own git repository, ignored by
the parent's** (`create-subproject` runs `git init` and appends the
subproject's path to the parent's `.gitignore`), but no `.venv` of its own
(`subproject.yaml` records the parent's, e.g. `venv: ../../.venv`). Older
subprojects carry `results/` instead of `out/`; it stays valid.

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
.context/log.md
.context/purpose.md
.gitignore
```

`CLAUDE.md` is a symlink to `AGENTS.md` (on Windows, an `@AGENTS.md` import instead), so Claude Code reads the same instructions. Both files must convey the same project instructions.

## Folders

Every project starts with a bare minimum of folders, each with one fixed
meaning. They are a floor, not a ceiling.

Always created:

```text
in/      inputs the work consumes: device designs, external data, parameters
out/     finished outputs: final figures, tables and results to hand on
```

Created with their capability:

```text
code/    has_code     source code
data/    has_data     intermediate results
paper/   has_paper    manuscript
slides/  has_slides   deck build scripts, slide assets, and the built decks
```

Conventional, created when first needed:

```text
docs/    stable documentation
refs/    small local references, e.g. a manuscript's bibliography
tmp/     disposable scratch
```

Material flows `in/` → `data/` → `out/`: `in/` holds what the work starts
from and cannot regenerate, `data/` what it produces along the way, `out/`
what it delivers.

`ws create project` creates the always-created folders and those of the
requested capabilities, each with a `.gitkeep` so the layout survives a
clone; `ws projects install` materializes the same set on an existing
project. Wherever one of these folders exists, it has the meaning above, and
material goes in the standard folder that fits it.

Other top-level folders are allowed (for example `notes/`, or `src/` and
`tests/` in a software project). A person may add any folder. An agent adds
one only when no standard folder fits, and records the folder and the reason
in `.context/log.md`. ws neither creates nor flags them.

`notes/` is no longer a conventional folder: kept working notes belong in
`.context/log.md`. Existing `notes/` folders stay valid.

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
subfields: [numerics]
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
exploration
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
  physics: [numerics, experimental]
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
generator. Creation and `ws projects install` create `slides/`, which holds
the deck build scripts, slide-only assets and the built decks (the decks
themselves are ignored by git). They also editable-install the generator from
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

`ws edit project:<key>` changes the catalog metadata of `project.yaml`
(`subproject.yaml` for a subproject): `--name` (the title), `--status`, and
added or removed fields, subfields and keywords, validated against the shared
taxonomy. It rewrites only those keys and preserves every other line.
`ws delete project:<key>` moves the folder to the Trash under the guards in
[Removing objects](objects.md#removing-objects): refused while another
project installs or depends on it or while it holds subprojects, and naming
git work that exists only in the folder. A finished project retires through
its status instead.

## `README.md`

Human-readable project overview.

Should contain:

- a `## Purpose` section that points at `.context/purpose.md` and does not
  copy it, so the purpose has one home and cannot drift
- current state
- important files or folders, including `.context/purpose.md` and
  `.context/log.md`
- how to run/build/read the project, if applicable

## `AGENTS.md`

Project-wide instructions.

Should contain:

- read-first list, with `.context/purpose.md` and `.context/log.md` right
  after `README.md`, then `ws context project:<key>` for the full briefing
- the standard folders and their meanings
- the context rules: the purpose is filled or changed only from the person's
  words, and a `.context/log.md` entry follows each piece of work
- project-specific safety rules
- testing/build/review expectations

Project `AGENTS.md` should not accumulate session-specific state or durable
agent memory; that belongs in `.context/log.md`.

## Context

A project keeps its context in `.context/`, as every folder-backed object may
([Context contract](context.md)). Creation writes both notes; they are
plain Markdown that people and agents edit directly.

### `.context/purpose.md`

What the project is for: the one canonical home of its purpose. The purpose
belongs to the person; an agent fills it from what they said or by asking
them, and never invents it. `ws create project` writes the `--description`
text there; without one it writes the placeholder from
`templates/purpose.md`, an HTML comment that the context layer reads as not
set yet. `project.yaml`'s `description` is catalog metadata and is not kept
in step. `README.md` points at the file instead of repeating it.

### `.context/log.md`

The project's running record, so that a person or agent resuming the project
can understand its scope and state without replaying its history. `README.md`
keeps the stable overview and `AGENTS.md` the standing instructions; the log
keeps what happened.

Newest entry first. After each piece of work that changes the project, or
decides something about it, one dated entry is added at the top:

```markdown
## YYYY-MM-DD · <host>

- Did: what changed
- Decided: decisions taken, and why
- Next: open threads
```

An entry also names any new top-level folder and why it was needed. Entries
are added, not rewritten; when the log grows long, older entries may be
condensed into one summary entry. `ws create project` writes the first entry.
`.context/` is tracked in git.

### What creation reports

After creating, `ws create project` (and `ws create subproject`) prints a
short block for whoever ran it, usually an agent: the purpose is in
`.context/purpose.md` and must come from the person's words or a question to
them, never invention (or, with `--description`, that it holds that text);
the log is `.context/log.md`, with an entry after each piece of work; and
`ws context project:<key>` gives the full briefing.

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
.context/        (purpose and log)
in/              (inputs; heavy files excepted, see below)
code/  paper/    (unless nested repositories, see below)
slides/          (build scripts and assets; built decks excepted)
docs/            (stable docs)
refs/            (small local references)
```

Never tracked:

```text
data/**          (intermediate results; manifest layer only)
out/**           (finished outputs; manifest layer only)
slides/**/*.pptx (built decks)
tmp/             (scratch)
.claude/ .codex/ (agent sessions)
nested repos     (see below)
```

`data/` and `out/` keep only a manifest layer in git — Markdown files that
describe their contents, and `.gitkeep` — via this `.gitignore` pattern:

```gitignore
data/**
!data/**/
!data/**/*.md
!data/**/.gitkeep
out/**
!out/**/
!out/**/*.md
!out/**/.gitkeep
```

`in/` is tracked because inputs usually cannot be regenerated. An input too
heavy for git (see the 5 MB check below) is ignored by its own `.gitignore`
line and listed under `sync.data`, so it travels by rsync instead. Small
curated data goes in `in/`.

### Nested repositories

A project may contain its own sub-repositories — for example `paper/` cloned from Overleaf, or `code/` hosted on GitHub. The parent repo must **ignore** those paths (add `/paper/`, `/code/` to the project `.gitignore`) so they are never embedded as gitlinks. Each sub-repo manages its own history and remote independently. Use git submodules only when deliberate version pinning is wanted.

### Sync model

`ws sync` (planned) uses two channels and never conflates them:

- **git channel** — repos sync via `git push`/`pull` to their remotes (the parent repo and each nested repo independently). Never rsync `.git/`.
- **rsync channel** — gitignored heavy data (`data/`, `out/`, and heavy inputs listed under `sync.data`) syncs via rsync with `--exclude .git`.

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
~/Projects/ws/templates/LOG.md        (written to .context/log.md)
~/Projects/ws/templates/purpose.md    (the not-set-yet placeholder)
~/Projects/ws/templates/gitignore
```

## Layout migration: `in/`, `out/`, `slides/`

Projects created before `in/` and `out/` became standard stay readable.
`project.yaml` gains no keys, so `schema_version` stays `1`.

- `ws projects check` reports a missing `in/`, `out/`, or `slides/` (when
  `has_slides`) as a note.
- `ws projects install project:<key>`, with no capability words, adds what is
  missing: `.context/log.md` with a first entry pointing at the git history
  and `README.md`, when the project has no log anywhere;
  `.context/purpose.md` as the placeholder, when neither it nor a README
  Purpose section exists; `in/` and `out/` (and `slides/` when `has_slides`)
  with `.gitkeep`; the missing ignore lines in `.gitignore` (the `out/**`
  manifest pattern replaces a bare `out/` line, and `slides/**/*.pptx` is
  added). In an `AGENTS.md` from before the project log, the rule lines of
  that template are replaced where they appear verbatim, and the folder and
  context rules are added.
- It never moves, renames or deletes content. Existing `notes/`, `results/`,
  decks under `out/slides/`, and inputs kept elsewhere stay where they are
  until someone moves them on purpose; older context is moved by
  `ws projects migrate`, below.
- Replacing `out/` with the `out/**` manifest pattern keeps every existing file
  ignored; only Markdown files and `.gitkeep` under `out/` become trackable.
- Every change lands in the project's own working tree and shows in its
  `git diff`; restoring those files undoes it.

## Context migration: root `LOG.md` and README purposes

Projects created before the context moved into `.context/` kept their log in
a root `LOG.md` and their purpose in the README's `## Purpose` section. They
stay readable: the context layer briefs from those older locations and marks
them as such ([Context](context.md)). No key changes, so `schema_version`
stays `1`.

`ws projects migrate [REF ...]` converts them, for the named projects or
every project and subproject in the store. Without `--apply` it prints the
plan and writes nothing; with it, it makes these changes:

- a root `LOG.md` moves to `.context/log.md`, unchanged;
- where `.context/purpose.md` is absent, empty or still the placeholder, it
  is written from the README's Purpose section verbatim; with no such
  section, the placeholder is written;
- a README Purpose section that matches `.context/purpose.md` word for word
  (ignoring whitespace) is replaced by the pointer, so the purpose keeps one
  home;
- the lines the previous templates wrote in `AGENTS.md` and `README.md`
  naming `LOG.md` are replaced, where they appear verbatim, by the current
  template lines naming `.context/`;
- a project with no log at all gets `.context/log.md` with a first entry.

Migration moves and copies; it never deletes content or merges text. What it
cannot decide is listed for the person and left as it is: a log in both
places, a README Purpose section that differs from `.context/purpose.md`,
and other lines that still name `LOG.md`. Running it again changes nothing
already migrated. Every change lands in the project's own working tree and
shows in its `git status`; restoring those files undoes it.

`ws projects check` reports a project that still needs migration as a
problem naming the planned changes, the decisions left to the person as
notes, and a purpose that is still the placeholder as a note.

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
