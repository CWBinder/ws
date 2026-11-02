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
  directly; ws reads them and writes none of them. They are canonical, not
  derived: deleting a note loses it.
- Every note is optional, and an empty note counts as absent. Record-only
  kinds (person, organisation, event, task, document, profile) own no folder,
  so they have no purpose or log of their own.
- `whereami.md` says what a place *is*; `instructions.md` how to work *there*;
  `purpose.md` what the object is *for*; `log.md` what has *happened*.
- The purpose belongs to the person; agents propose changes to it. Which
  purpose an object serves above it is a `contributes-to` edge, not text.
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
may look for it to know it was briefed. Five sections follow, in this order,
the most lasting first, so that a reader who stops early, or a harness that
keeps only the start, loses the newest history rather than the rules:

1. **WHERE YOU ARE**: the whereami layers from the root down. For an object,
   also its REF, folder and description, and its neighbours grouped by
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
   path and entry count.

A section the place cannot have is left out: a store shows no PURPOSE or
UPCOMING, and no LOG unless it keeps one; a record-only object shows no
PURPOSE (unless it serves a purpose above it) and no LOG. Each whereami and instructions layer is labelled
`[<level> · <origin>]`, where the origin is `ws` for a shipped text and the
note's path for the workspace's own note.

Open tasks are the tasks joined to the object by any edge whose `status` is
not closed (done, dropped, cancelled, canceled, closed, complete, completed,
archived; the dashboard's set). Relation words with a gloss show it; the
others show without one.

Older locations are read and marked as such: a project without
`.context/purpose.md` shows its README's `## Purpose` section, and a project
without `.context/log.md` shows its root `LOG.md`. Neither is moved or
rewritten.

`--json` prints the same content as one object with `briefing`, `subject`,
`ref`, `store`, `folder`, `whereami`, `instructions`, `purpose` and `log`;
objects add `description`, `neighbours`, `tasks` and `serves`, stores
`listing`, the root `agenda`. Each `whereami` and `instructions` layer carries
`level`, `source`, `shipped` and `text`. Fields may be added; existing
meanings stay.

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
Projects keep their root `LOG.md` readable until it is moved by hand into
`.context/log.md`. Every command of the layer reads; none writes.
