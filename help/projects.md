# Projects

A project is an open-ended piece of work: an open question, a package to
develop, a paper or a talk to produce. Something deserves to be a project
when its work spans sessions and needs judgement. A one-off action is a task
instead (`ws help tasks`).

Each project is one folder, usually its own git repository. To start one,
read `ws help create project`.

## Where projects live

```text
~/workspace/projects/
  items/<project>/        the store: one folder per project
  by-type/  by-field/  by-status/  by-organisation/  by-event/
                          derived browse views, rebuilt by ws
  project-taxonomy.yaml   allowed types, fields and subfields
```

The store is flat. A project's identity is its folder name, which must be
unique; its REF is `project:<folder-name>`. Grouping is expressed with
fields, keywords and relations, and browsed through the `by-*` views, so
reorganising never changes a project's identity. A path such as
`group/shuttling` is refused as a project name, and so is creating a
project inside another project. For a working area inside a project, see
`ws help create subproject`.

## Files

```text
project.yaml    the record (fields below)
README.md       the project, described for people
AGENTS.md       the project's own rules for agents
CLAUDE.md       a symlink to AGENTS.md
.context/purpose.md   what the project is for, in your words
.context/log.md       the log, newest entry first
.gitignore      from the shipped template
pyproject.toml  Python projects only
```

The purpose is yours. `.context/purpose.md` is its one home: the README
only points there. An agent fills it from what you said, or asks you, and
never makes it up. Agents read the log when they resume and add an entry
after each piece of work. `ws context project:<key>` briefs a session on
both (`ws help context`).

Projects from before `.context/` keep a root `LOG.md` or a purpose in the
README; `ws projects migrate` moves them (`ws help projects migrate`).

## Folders

Every project starts with a minimum set of folders, each with one meaning:

```text
in/      always        inputs the work starts from and cannot regenerate
out/     always        finished outputs: final figures, tables, results
code/    has_code      source code
data/    has_data      intermediate results
paper/   has_paper     manuscript
slides/  has_slides    deck build scripts, slide assets, built decks
```

Material flows from `in/` through `data/` to `out/`. Three more folders have
fixed meanings and are created when first needed:

```text
docs/    stable documentation
refs/    small local references, e.g. a manuscript's bibliography
tmp/     disposable scratch
```

Every folder ws creates holds a `.gitkeep`, so the layout survives a clone.
These folders are a floor, not a ceiling: any other top-level folder, such
as `notes/`, is allowed. Agents add one only when no standard folder fits,
and record it with the reason in `.context/log.md`.

## What git tracks

Git tracks `project.yaml`, the Markdown files, `in/`, `code/`, `paper/`,
the build scripts in `slides/`, `docs/` and `refs/`. Of `data/` and `out/`
it keeps only Markdown descriptions and `.gitkeep`, so the repository holds
a description of each result, not the result. Built decks, `tmp/`, `.venv/`
and agent session folders are ignored. An input too heavy for git gets its
own `.gitignore` line and a `sync.data` entry in `project.yaml`.

## Nested repositories

A project folder can hold its own git repositories, for example `paper/`
cloned from Overleaf or `code/` hosted on GitHub, while the project root
stays a separate repository. Ignore the nested path in the parent so it is
not embedded as a broken gitlink:

```bash
git clone <url> code
echo '/code/' >> .gitignore
```

Each nested repository manages its own history and remote. `ws projects
check` flags any nested repository the parent does not ignore. Use a git
submodule only when the parent should pin an exact nested commit.

## Fields of project.yaml

`name`, `title`
: The folder name, and a human-readable title.

`type`
: What kind of undertaking it is, from the taxonomy
  (`ws help projects taxonomy`). The type also decides which questions the
  creation wizard asks.

`status`
: One of `idea`, `active`, `paused`, `complete`, `archived`.

`created`, `description`
: The creation date, and a one-paragraph description for the catalog. The
  purpose itself lives in `.context/purpose.md`.

`fields`, `subfields`, `keywords`
: Broad disciplines and their specialisms from the taxonomy, shared with
  literature; every subfield must belong to a chosen field. Keywords are
  free-form content words.

`has_code`, `has_paper`, `has_data`, `has_slides`, `server_compute`
: What the project is expected to contain or need. Each `has_` flag goes
  with its folder.

`runtime`
: Local setup, such as `python: true` and `venv: .venv`. Every project owns
  its own virtual environment.

`project_dependencies`
: Other workspace projects installed as editable packages into this
  project's `.venv`, replayed by `ws projects install`.

`hosts`
: The machines the project runs on; defaults to the current one.

`sync`
: Routing for a planned sync command: the primary host, other hosts, the
  repositories synced by git and the heavy paths synced by rsync.

`depends_on`, `related`, `related_literature`
: Legacy lists, read but no longer written. Conceptual links are relations
  now, made with `ws relate` (`ws help relations`).

Change a record with `ws edit project:<key>`; it sets the name, status,
fields, subfields and keywords. Capabilities are added with `ws projects
install` (`ws help projects install`). Nothing is settable only at creation.

## Retiring or removing a project

A finished project is retired, not removed:

```bash
ws edit project:<key> --status archived
```

`ws delete project:<key>` is for a project that should not exist. The folder
goes to the Trash and its relations are removed. Delete refuses while
another project installs or depends on this one, or while it holds
subprojects, and it names any git work that exists only in the folder:
uncommitted changes, and history no remote holds. Run it with `--dry-run`
first to see all of that without moving anything.
