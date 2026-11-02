# Project Setup Guide

Use this guide with:

```bash
ws create project --help
```

Install ws first using [Getting started](../GETTING-STARTED.md). Project creation
uses the shipped [metadata template](../templates/project.yaml). The
[project contract](../contracts/project.md) specifies maintainer extension rules.

Allowed project types and broad fields are configured here (workspace data,
next to the projects it describes):

```text
~/workspace/projects/project-taxonomy.yaml
```

## Basic Creation

```bash
ws create project my project
```

When run in an interactive terminal with only the project name, this opens the setup wizard. To create the minimal/default scaffold without prompts, use:

```bash
ws create project my project --non-interactive
```

Project names are normalized to lowercase kebab-case:

```text
my project -> my-project
tax-paper
simulation-study
data-cleaning
```

By default, the project is created in `projects/items/` beneath the configured
workspace root (`~/workspace` unless changed by `ws init` or an environment
override). See [Configuration](reference/configuration.md). To use a
specific projects folder from anywhere on the computer, either pass `--in`:

```bash
ws create project my project --in ~/Projects
```

or set a persistent default:

```zsh
export WS_PROJECTS_DIR="$HOME/Projects"
```

Resolution order:

```text
--in DIR
WS_PROJECTS_DIR
<resolved-workspace-root>/projects/items
```

The command always creates:

```text
project.yaml
README.md
AGENTS.md
CLAUDE.md
LOG.md
.gitignore
.git/
in/
out/
```

`CLAUDE.md` is created as a symlink to `AGENTS.md` (or, on Windows, an `@AGENTS.md` import file). `LOG.md` starts with a first entry; agents read it when they resume and add an entry when they finish.

Add `--has-code`, `--has-paper`, `--has-data` or `--has-slides` to also create `code/`, `paper/`, `data/` or `slides/`. Every folder ws creates holds a `.gitkeep`, so the layout survives a clone. `--python` creates Python project metadata and implies `--has-code`; `--venv` creates `.venv` and implies `--python`; `--has-slides` creates `slides/`, editable-installs the `slide_factory` deck generator shipped with ws (plus any theme packages from `slides.themes` in the ws configuration) into `.venv`, and implies `--venv`. See [Folders](#folders) for what goes where.

None of these choices is creation-only. `ws projects install [project:<key>] <capability ...>` records the same capabilities (`code`, `paper`, `data`, `python`, `venv`, `slides`) in `project.yaml` and materializes them for an existing project, and `ws projects install --use-project project:<key>` records and installs a package dependency (with its depends-on edge) after the fact; with no capability words it (re)runs everything the file already records. See [Installing project capabilities](project-install.md) for the workflow.

## Interactive Creation

```bash
ws create project my-project --interactive
```

Run `ws create project` in a terminal without a name, or pass `--interactive`,
and a wizard asks for the rest. Constrained choices print their allowed values
and are checked at once; an unknown type, field or subfield offers to extend
the taxonomy. Status and hosts are not asked; set them with flags.

Every project is asked the same metadata first:

```text
Name          folder name; words are slugified
Title         defaults to the title-cased name
Type          a taxonomy type; defaults to the first one (research)
Description   one paragraph
Fields        comma-separated, from the taxonomy
Subfields     comma-separated, only those of the chosen fields
Keywords      comma-separated, free-form
```

The type then decides which setup questions follow:

| Type | Code, Python, venv | Paper | Data | Slides | Server compute |
|---|---|---|---|---|---|
| `research` | asked | asked | asked | asked | asked |
| `exploration` | asked | asked | — | asked | asked |
| `paper` | asked | set to yes | — | — | — |
| `software` | asked | — | — | — | — |
| `talk`, `teaching` | — | — | — | asked | — |
| `organizatorial`, `other` | — | — | — | — | — |
| any other type | asked | asked | asked | asked | asked |

"Any other type" covers types added with `ws projects add-type` that the
wizard has no routing for; they get every question. The routing table is
`TYPE_QUESTION_SETS` in `cli/ws_lib/project.py`.

The code questions cascade. `Has code` comes first; `Python project` defaults
to yes when the project has code, and `Create Python virtual environment`
defaults to yes for a Python project. Only once a venv is chosen does the
wizard ask whether to install another workspace project into it. Slides need
the venv, so answering yes to slides creates one; a talk's slides question
defaults to yes.

A question the type skips stays off, and nothing is lost by that: every
capability can be added later with `ws projects install`, as described in
[Basic Creation](#basic-creation).

If you create a venv, the wizard asks whether to install another workspace project into that venv. The prompt accepts `y` (it then asks for the project REF) or the REF directly, which counts as yes. For a project such as `virtuallab`, the flow is:

```text
Install another workspace project into this venv [n]: project:virtuallab
Found Python package:
  ~/Projects/virtuallab/pyproject.toml
Editable install command:
  .venv/bin/python -m pip install -e ~/Projects/virtuallab
Run this after creating the venv [y]:
```

That records a `project_dependencies` entry and, after the new project's `.venv` exists, runs the editable install from the new project folder.

## Taxonomy

View the current allowed values:

```bash
ws projects taxonomy
```

Add values from the CLI:

```bash
ws projects add-type dataset
ws projects add-field economics
ws projects add-subfield physics spin-qubits
```

Or edit the file directly:

```text
~/workspace/projects/project-taxonomy.yaml
```

The default project type is the first value in `type`; `fields` and
`subfields` default to empty. Both are shared with literature. Fields are
broad disciplines; subfields are stored under a particular field in the
taxonomy, and each selected subfield must belong to a selected field. Both
may be multi-valued. Use `keywords` for project-specific scientific content.
Organisations are never classifiers — relate the project instead (`ws relate
<project> to <organisation>`).

## Common Options

```bash
ws create project tax-paper \
  --title "Tax Paper" \
  --type paper \
  --status active \
  --description "Draft and analysis for the tax paper." \
  --field physics \
  --subfield quantum-computing \
  --keyword tax \
  --has-paper
```

Python project with a local virtual environment:

```bash
ws create project code-tool --python --venv
```

Project that installs another workspace project as an editable package into its own `.venv`:

```bash
ws create project experiment --python --venv \
  --use-project project:potential-generator-toolkit:package
```

The equivalent interactive workflow is to answer yes to `Create Python virtual environment`, then answer `Install another workspace project into this venv` with yes or with the project REF itself.

The same dependency can be added after creation — this records it, creates its depends-on edge, and installs it into the existing project's `.venv`:

```bash
ws projects install --use-project project:potential-generator-toolkit
```

Repeat these options when needed:

```text
--field
--keyword
--use-project
--host
```

Conceptual links are not creation flags: relate the finished project with
`ws relate project:<key> to <ref> as depends-on` (or any relation words).

List fields and keywords in `project.yaml` may be edited either inline (`fields: [physics]`) or as normal YAML block lists:

```yaml
fields:
  - physics
subfields:
  - spin-qubits
keywords:
  - qudit
```

## `project.yaml` Fields

`schema_version`
: Contract version for the project metadata format. Currently `1`.

`name`
: Lowercase kebab-case project folder name.

`title`
: Human-readable project title.

`type`
: Project category. Configured in `~/workspace/projects/project-taxonomy.yaml`. Default values: `research`, `exploration`, `paper`, `talk`, `software`, `teaching`, `organizatorial`, `other`.

`status`
: Lifecycle status. Allowed values: `idea`, `active`, `paused`, `complete`, `archived`.
  Change it with `ws edit project:<key> --status archived`; the same command
  sets `--name`, and adds or removes fields, subfields and keywords.

`created`
: Creation date in `YYYY-MM-DD` format.

`description`
: One-paragraph purpose or scope.

`fields`
: One or more configured broad disciplinary fields. Defaults to empty. Add values with `ws projects add-field <field>` or by editing `project-taxonomy.yaml`.

`subfields`
: One or more controlled specialisms belonging to a selected field. Defaults
  to empty. Add taxonomy values with `ws projects add-subfield <field>
  <subfield>`.

`keywords`
: Optional free-form content descriptors. They are not restricted by the taxonomy because project-specific scientific keywords should stay easy to edit.

`depends_on`, `related`, `related_literature`
: Read-only legacy lists, no longer written. Conceptual links are canonical
edges in the relations service: `depends-on`, `related`, and `references`
respectively, created exclusively with `ws relate`.

`runtime`
: Local setup choices such as `python: true` and `venv: .venv`. Every project owns its own virtual environment.

`project_dependencies`
: Install recipes replayed by `ws projects install`. The only kind is `package`: install the other project as an editable package into this project's `.venv`. References that install nothing are `depends-on`/`related` edges, not entries here.

`has_code`
: `true` when the project is expected to contain code.

`has_paper`
: `true` when the project is expected to contain a manuscript or paper.

`has_data`
: `true` when the project is expected to contain data.

`has_slides`
: `true` when the project builds slide decks with the `slide_factory` generator; creation and `ws projects install` editable-install it from the ws checkout, with any configured theme packages, into the project's `.venv`.

`server_compute`
: `true` when the project expects server, cluster, or long-running compute.

`hosts`
: Machines where the project is expected to run. Default is `[mac]`.

`sync`
: Routing metadata for the planned `ws sync` (not an available command). `primary_host` is the authoritative host; `remotes` lists other hosts; `git` lists repo paths synced via git push/pull (including nested repos); `data` lists gitignored heavy paths synced via rsync. See the "Git Boundary and Sync" section of the project contract.

## Folders

Every project starts with a minimum set of folders, each with one meaning:

```text
in/      always         inputs the work consumes: device designs, external data, parameters
out/     always         finished outputs: final figures, tables, results to hand on
code/    --has-code     source code
data/    --has-data     intermediate results
paper/   --has-paper    manuscript
slides/  --has-slides   deck build scripts, slide assets, and the built decks
```

Material flows `in/` → `data/` → `out/`. Three more folders have fixed
meanings and are created when first needed:

```text
docs/    stable documentation
refs/    small local references, e.g. a manuscript's bibliography
tmp/     disposable scratch
```

Git tracks `LOG.md`, `in/`, `code/`, `paper/`, the build scripts in `slides/`,
`docs/` and `refs/`. Of `data/` and `out/` it keeps only Markdown descriptions
and `.gitkeep`; built decks and `tmp/` are ignored. An input too heavy for git
gets its own `.gitignore` line and a `sync.data` entry.

These folders are a floor, not a ceiling. You may add any other top-level
folder, such as `notes/`. Agents add one only when no standard folder fits,
and record it with the reason in `LOG.md`.

## Subprojects

A subproject is a working area inside a project that shares the parent's
`.venv`. Create one from inside the parent, where it lands in the current
folder, or from anywhere by naming the parent:

```bash
ws create subproject analysis-study
ws create subproject studies/analysis-study --project project:<parent-key>
```

There is no wizard: type and classification come from the parent. ws creates
`in/`, `code/`, `data/` and `out/`, a `subproject.yaml`, a README, a log and a
`.gitignore`, runs `git init` in the subproject, and adds its path to the
parent's `.gitignore`. See
[Share an environment with a subproject](project-install.md#share-an-environment-with-a-subproject)
for the REF and the nesting rules.

## Nested Repositories

A project subfolder can be its own git repository — for example `paper/` cloned from Overleaf, or `code/` hosted on GitHub — while the project root stays a separate repo for `project.yaml`, `README.md`, `LOG.md`, and the rest.

Create or clone the repo, then ignore its path in the parent so it is not embedded as a broken gitlink:

```bash
git clone <url> projects/items/<project>/code   # or: git init projects/items/<project>/code
echo '/code/' >> projects/items/<project>/.gitignore
```

Each nested repo manages its own history and remote. Run `ws projects check` to confirm the parent ignores it — the check flags any nested git repo that is not ignored. Use a git submodule only when you want the parent to pin an exact nested commit.

See the "Git Boundary and Sync" section of the project contract for the full model.

## Retiring or Removing a Project

A finished project is retired, not removed: `ws edit project:<key> --status archived`.
`ws delete project:<key>` is for a project that should not exist. The folder goes
to the Trash and its relations are removed. Delete refuses while another project
installs or depends on this one, or while it holds subprojects, and it names any
git work that exists only in the folder: uncommitted changes, and history no
remote holds. Run it with `--dry-run` first to see all of that without moving
anything.
