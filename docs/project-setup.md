# Project Setup Guide

Use this guide with:

```bash
ws create project --help
```

The project contract is:

```text
~/Projects/ws/contracts/project.md
```

The base metadata template is:

```text
~/Projects/ws/templates/project.yaml
```

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

By default, the project is created in the flat store at
`~/workspace/projects/items` (or `$WS_WORKSPACE_ROOT/projects/items`). To use a
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
WS_WORKSPACE_ROOT/projects/items
~/workspace/projects/items
```

The command always creates:

```text
project.yaml
README.md
AGENTS.md
CLAUDE.md
.gitignore
.git/
```

`CLAUDE.md` is created as a symlink to `AGENTS.md` (or, on Windows, an `@AGENTS.md` import file).

The non-interactive default scaffold contains no empty optional folders. Add `--has-code`, `--has-paper`, or `--has-data` to create the corresponding `code/`, `paper/`, or `data/` folder. `--python` creates Python project metadata and implies `--has-code`; `--venv` creates `.venv` and implies `--python`; `--has-slides` editable-installs the `slide_factory` deck generator from `~/Utils/SlideGenerator` into `.venv` and implies `--venv`. Other allowed folders are created when first needed.

None of these choices is creation-only. `ws projects install [project:<key>] <capability ...>` records the same capabilities (`code`, `paper`, `data`, `python`, `venv`, `slides`) in `project.yaml` and materializes them for an existing project, and `ws projects install --use-project project:<key>` records and installs a package dependency (with its depends-on edge) after the fact; with no capability words it (re)runs everything the file already records. See "Installing capabilities after creation" in the project contract.

## Interactive Creation

```bash
ws create project my-project --interactive
```

Interactive mode prints allowed options for constrained choices and validates them immediately. It prompts for title, type, description, fields, free-form keywords, code/Python/venv setup, paper/data/compute flags, and then asks plain-language follow-ups for the choices that need extra setup. Less common metadata such as status and hosts is set with explicit flags.

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
  --use-project potential-generator-toolkit:package
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
: Project category. Configured in `~/workspace/projects/project-taxonomy.yaml`. Default values: `research`, `paper`, `talk`, `software`, `teaching`, `organizatorial`, `other`.

`status`
: Lifecycle status. Allowed values: `idea`, `active`, `paused`, `complete`, `archived`.

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
: `true` when the project builds slide decks with the `slide_factory` generator; creation and `ws projects install` editable-install it from `~/Utils/SlideGenerator` into the project's `.venv`.

`server_compute`
: `true` when the project expects server, cluster, or long-running compute.

`hosts`
: Machines where the project is expected to run. Default is `[mac]`.

`sync`
: Optional routing for `ws sync`. `primary_host` is the authoritative host; `remotes` lists other hosts; `git` lists repo paths synced via git push/pull (including nested repos); `data` lists gitignored heavy paths synced via rsync. See the "Git Boundary and Sync" section of the project contract.

## Optional Folders

Allowed optional top-level folders are:

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

Project creation is capability-driven:

```text
--has-code   creates code/
--has-paper  creates paper/
--has-data   creates data/
```

Create the remaining folders only when they acquire content or a tool needs them.

Use these meanings consistently:

```text
docs/   stable documentation
notes/  transient but kept working notes
out/    generated outputs that can be recreated
tmp/    disposable scratch
```

Do not create other top-level folders unless the project contract is updated.

## Nested Repositories

A project subfolder can be its own git repository — for example `paper/` cloned from Overleaf, or `code/` hosted on GitHub — while the project root stays a separate repo for `project.yaml`, `README.md`, and notes.

Create or clone the repo, then ignore its path in the parent so it is not embedded as a broken gitlink:

```bash
git clone <url> projects/items/<project>/code   # or: git init projects/items/<project>/code
echo '/code/' >> projects/items/<project>/.gitignore
```

Each nested repo manages its own history and remote. Run `ws projects check` to confirm the parent ignores it — the check flags any nested git repo that is not ignored. Use a git submodule only when you want the parent to pin an exact nested commit.

See the "Git Boundary and Sync" section of the project contract for the full model.
