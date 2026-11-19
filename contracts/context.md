# Context contract

Usage: `ws help context`.

The context layer tells a fresh session, a person's or an agent's, where it
is in the workspace, what the object there is for, what has happened, and how
to work there. It adds no records. It consists of hand-written notes in
`.context/` folders and a view computed from records and relations.

## The .context/ notes

Three levels may hold a `.context/` folder:

| Level | Folder | Notes it may hold |
|---|---|---|
| workspace | `<root>/.context/` | `whereami.md`, `instructions.md`, `purpose.md` (the owner's goals), `log.md` |
| store | `<root>/<store>/.context/` for projects, resources, literature, documents, tasks, logistics, profile | `whereami.md`, `instructions.md`, and `log.md` where sessions work in the store itself |
| object | the folder a folder-backed object owns: a project or subproject, a resource, a literature item | `whereami.md`, `instructions.md`, `purpose.md`, `log.md` |

- Notes are plain Markdown owned by the workspace. People and agents edit them
  directly. ws writes one only where a command says so: creating a project or
  subproject writes its `purpose.md` and `log.md`, setup writes the notes its
  answers give, and `ws projects migrate` moves a project's older notes in
  ([Project](project.md#context-migration-root-logmd-readme-purposes-and-description)).
  The commands of this layer only read. Notes are canonical, not derived:
  deleting a note loses it.
- Every note is optional. An empty note counts as absent, and so does one
  that holds only HTML comments: that is how a placeholder is written, and
  a briefing reports such a purpose as not set yet. Comments are left out
  wherever a note is shown. Record-only kinds (person, organisation, event,
  task, document, profile) own no folder, so they have no purpose or log of
  their own.
- `whereami.md` says what a place *is*; `instructions.md` how to work *there*;
  `purpose.md` what the object is *for*; `log.md` what has *happened*.
- The purpose belongs to the person; agents fill it from what the person
  said or by asking, never by invention, and propose changes to it. Which
  purpose an object serves above it is a `contributes-to` edge, not text.
- `purpose.md` is the one home of an object's purpose. Other files point at
  it rather than copy it; a project's README says where it is.
- A log lists entries newest first. Each entry starts with a `## ` heading,
  conventionally `YYYY-MM-DD · host`; text before the first heading is the
  log's preamble. An entry whose heading contains "summary" condenses older
  entries.

## Shipped layers

ws ships generic texts for the workspace and store levels,
`context/whereami/<level>.md` and `context/instructions/<level>.md` in its
checkout (installed under `share/ws/context/`), where `<level>` is
`workspace` or a store name. At each level a briefing shows the shipped text
first and then the workspace's own note. `{system}` in a shipped text stands
for the ws checkout. Objects have no shipped text.

## The briefing

`ws context [REF]` prints one briefing. Without a REF it briefs the folder it
runs in, resolved after following symlinks (so a `by-*` view briefs the
object it points to):

- outside the workspace root, nothing is printed and the exit status is 0, so
  one session-start hook may run it everywhere;
- inside an object's folder, the deepest enclosing object;
- otherwise inside a store folder, that store;
- otherwise the workspace root.

The text form opens with the line `WORKSPACE BRIEFING: <subject>`; a session
may look for it to know it was briefed. For an object that owns a folder and
has no purpose yet (no `purpose.md`, or only the placeholder, and no older
location), one line comes next, ahead of everything else, because it must
happen before other work:

```text
Next: the purpose is not set. Ask the person, then write their words into <folder>/.context/purpose.md
```

The PURPOSE section still says the same in its place. Five sections follow, in this order,
the most lasting first, so that a reader who stops early, or a harness that
keeps only the start, loses the newest history rather than the rules:

1. **WHERE YOU ARE**: the whereami layers from the root down. The workspace
   level closes with the owner's name and a pointer to `ws owner`, looked up
   from the records each time a briefing is built (`contracts/objects.md`);
   without an owner the line is left out. For an object,
   also its REF, folder and description (a project's description is its
   purpose, shown under PURPOSE), and its neighbours grouped by
   relation word and direction with what each means for the work. For a
   store, its contents. For the root, the active projects.
2. **HOUSE RULES**: the instructions layers from the root down.
3. **PURPOSE**: the place's `purpose.md`. For an object, also the chain of
   purposes it serves, following outgoing `contributes-to` edges until none
   remains or the chain would repeat an object.
4. **UPCOMING**: for an object, the open tasks related to it; for the root,
   open tasks due within 7 days or overdue, the count of other open tasks,
   and events in the next 14 days.
5. **LOG**: the latest three entries and any summary entry, with the log's
   path and entry count. Each entry shows at most its first 25 lines. A line
   after them names the entries left out and where to read them:
   `ws show log of REF` for an object, the log's file for a store or the
   root, which have no REF.

A section the place cannot have is left out: a store shows no PURPOSE or
UPCOMING, and no LOG unless it keeps one; a record-only object shows no
PURPOSE (unless it serves a purpose above it) and no LOG. Each whereami and instructions layer is labelled
`[<level> · <origin>]`, where the origin is `ws` for a shipped text and the
note's path for the workspace's own note.

Open tasks are the tasks joined to the object by any edge whose `status` is
not closed (done, dropped, cancelled, canceled, closed, complete, completed,
archived; the dashboard's set). Relation words with a gloss show it; the
others show without one.

Older locations are read and marked as such: a project without a purpose in
`.context/purpose.md` shows its README's `## Purpose` section (unless that
section only points at `.context/purpose.md`), and a project without
`.context/log.md` shows its root `LOG.md`. The briefing names
`ws projects migrate` as the command that moves them; it never moves or
rewrites them itself.

### Size

A session-start hook's output reaches a Claude Code session whole only up
to 10,000 characters; beyond that the session gets a file path and a short
preview, which still holds the `WORKSPACE BRIEFING` line. The text form
therefore prints fewer than 9,500 characters, its final newline included.
A briefing longer than that gives things up in this order, each step only
as far as needed:

1. older log entries, the oldest shown first, down to the newest entry;
   then the end of the newest entry, cut at a word, down to its first
   1,000 characters;
2. the lists of related objects, step by step down to none: an object's
   neighbours under each relation, a store's contents, the root's active
   projects;
3. the workspace's own notes (whereami, instructions, purpose) of 500
   characters or more, the longest first, each replaced by a line that
   gives its size and tells the reader to read the file. The texts ws ships
   are never replaced.

Then it takes back what still fits, related objects before log entries.
Every shortened list ends with a line counting what is left out and naming
the command that prints it (`ws show REF --as WORD`, `ws list <store>`,
`ws list projects --status active`). Should all three steps not suffice,
the end of the text is cut, which keeps the most lasting part.

A trimmed briefing closes with one line naming what was given up and the
command that prints everything:

```text
Trimmed to stay under 9,500 characters: 2 older log entries and 23 related objects. Everything: ws context project:<key> --full
```

For a store or the root, which have no REF, the command reads
`` `ws context --full`, run in <folder> ``. A briefing that fits has no such
line. `--full` prints everything with no size limit: every log entry whole,
and every object of every list.

`--json` prints the same content as one object with `briefing`, `subject`,
`ref`, `store`, `folder`, `whereami`, `owner`, `instructions`, `purpose` and
`log`; `owner` is `null` without an owner, else `name`, `person` and `identity`
(a REF is empty when that record does not exist). Objects add `description`, `neighbours`, `tasks` and `serves`, stores
`listing`, the root `agenda`. Each `whereami` and `instructions` layer carries
`level`, `source`, `shipped` and `text`. Fields may be added; existing
meanings stay. The size limit and `--full` concern the text alone: the JSON
always holds every log entry and every neighbour, and is the same with or
without `--full`.

## Aspects

`ws show ASPECT of REF` prints one aspect of an object in full: `purpose`
(with the chain it serves), `log` (every entry), `location` (whereami layers,
neighbours, then the UPCOMING section) or `instructions`. The filler `of` is optional.
Relations remain listed under `ws show REF`.

`ws show REF` adds a `purpose:` line (the first paragraph) and a `log:` line
(entry count and latest heading) when the object's own `.context/` has those
notes; its JSON gains `purpose` and `log` keys under the same condition.
Older locations are not consulted there.

## Compatibility

The layer is additive: no existing record, field or file changes meaning.
Projects keep their root `LOG.md` and README purpose readable until
`ws projects migrate` moves them into `.context/`. Every command of the layer
reads; none writes. Since the size limit, a long briefing's text is trimmed
by default; `--full` prints everything, every log entry and every related
object included. The JSON is unchanged.
