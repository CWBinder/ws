# The workspace

The workspace is a second brain: the projects, tasks, documents, papers,
contacts, events and career facts of one person, kept as small plain
records, with explicit relations connecting them. It answers "what do I
have, and how does it hang together" from one place, so a document is found
through its project and a paper through its authors, without copies
scattered across folders.

It lives in `~/workspace` unless `ws init` saved another location
(`ws help configuration`). `ws` is the tool that keeps it; people and
agents use the same commands. The tool itself, with its templates and
contracts, lives apart from the data.

## Objects

Everything the workspace knows is an object of one of nine kinds:

```text
project       a piece of work, with its own folder
task          something to do
document      one file worth addressing on its own: an invoice, a contract
resource      a bundle of supporting files, such as receipts for one claim
literature    a paper or book with a DOI, arXiv ID or ISBN
person        someone you deal with
organisation  an institution, company or group
event         a conference, meeting or talk
profile       one of your own career facts, for CVs
```

Each kind has its own page: `ws help projects`, `ws help people` and so on.

Every object has one REF of the form `<kind>:<key>`, such as
`project:thesis` or `person:jane-doe`. Commands that act on an existing
object accept only the full REF, never a name, title, alias or path. REFs
come from `ws search`, or from the output of the command that made the
object. Renaming an object never changes its REF.

Most records are written by ws alone: a person is a YAML file under
`logistics/people/`, and only ws edits it. Projects, literature and
resources are different. Their folders exist in their own right, so ws
reads them as objects: a project's record is its own `project.yaml`, a
paper's is its BibTeX entry. That is why editing a project's folder by hand
is normal, while editing a person's YAML by hand is not.

## What a record holds

Six fields are common to every object: an internal id that never changes,
the kind, a name, a type, aliases and a description. The type is the
standard classifier of the kind, such as `invoice` for a document or
`research` for a project; it may be empty. The name and aliases are what
search finds the object by. The description is a sentence or two of prose,
searched but never grouped by; a project's description is its purpose, kept
in its `.context/purpose.md`.

Beyond these, each kind adds its own: classifiers such as a project's
fields, facts such as a person's emails or a task's due date, and an
optional `status`, which means active when absent. Every assertion carries
provenance, which source said it and when, given with `--source` and
`--observed-at`. That is what lets agents file facts as they work: each one
is signed and dated.

## Relations

Relations are the edges between objects, and they carry as much knowledge
as the records. An edge is a directed sentence with kebab-case words:

```text
person:<key>   --works-at-->     organisation:<key>
project:<key>  --references-->   literature:<key>
task:<key>     --concerns-->     person:<key>
```

Edges are never made automatically; creating an object links nothing. Who
someone is to you, which project a document belongs to, who organised an
event: all of it lives in edges, not in fields. `ws help relations`
explains how to choose relation words.

## One truth, several renderings

Records and relations are the canonical layer: each fact is stored once,
in one place. Everything else is derived from them and rebuilt by
`ws rebuild`:

```text
by-* folders    browse trees of symlinks, e.g. documents/by-type/
index/          the search index behind ws search
wiki/           an Obsidian wiki, one page per object
dashboard.html  the workspace at a glance
```

Derived layers are read-only. When a view disagrees with a record, fix the
record and rebuild; never edit the view. Taxonomies, the allowed values of
classifiers such as project types, are workspace data too, and so is
`folder-anatomy.yaml`, which shapes the browse trees
(`ws help rebuild views`).

## Working rules

- **Every change goes through ws.** Creating, adding, editing, relating,
  moving and deleting are ws commands, never hand edits to store files. The
  one exception is a project's working content, its code, data, paper and
  slides, which you work on normally.
- **Search before creating.** A duplicate is worse than a gap. Reading is
  free: search, show, and read the files at the paths ws prints.
- **Content enters deliberately.** Material elsewhere stays outside until a
  ws command brings it in. Never symlink it into the workspace.
- **Relate what is stated or evident**, not what merely seems plausible.
- **The root holds only its domains and service layers.** Add no other
  top-level folder to the workspace; new material goes into a domain
  through a ws command.

What deserves to become an object, and the other judgement calls, are in
`ws help values`.

## How the commands are organised

Every command belongs to one of four categories. Objects commands work on
single objects and their edges: create mints something new, add brings in
something that exists, and show, edit, delete and relate act on a REF.
Search commands take a kind or some words and hand REFs back. Maintenance
commands set up the workspace, rebuild the derived layers and check them.
Discovery commands, this manual among them, explain the CLI itself.

Seven domains own the nine kinds; logistics holds people, organisations and
events. A domain word hosts only what exists for its kind alone, such as
`ws projects install` or `ws literature enrich`. Everything else is a
universal verb that comes straight after `ws`.

The map below lists the commands and the grammar. Every command has a page
of its own: `ws help` followed by the command.
