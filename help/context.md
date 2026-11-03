# Briefing a session

A fresh session, a person's or an agent's, starts with an empty memory.
`ws context` gives it five answers about the place it starts in, the most
lasting first:

```text
WHERE YOU ARE   what the workspace and this part of it are, and what the
                object here is connected to
HOUSE RULES     how to work here, from the workspace down to the object
PURPOSE         what the object is for, and the purposes it serves above it
UPCOMING        the open tasks that concern it; at the root, what is due
                and which events are near
LOG             the latest entries of its log
```

The order is deliberate: a reader who stops early, or a harness that keeps
only the start, loses the newest history rather than the rules. A section
the place cannot have is left out. The briefing opens with the line
`WORKSPACE BRIEFING: <subject>`, which a session can look for to know it
has been briefed.

## Which place

```bash
ws context                    # the folder you are in
ws context project:<key>      # any object, from anywhere
```

Bare `ws context` resolves the folder it runs in, after following symlinks,
so a `by-*` browse folder briefs the object it points to:

```text
outside the workspace          nothing is printed, and the exit status is 0
inside an object's folder      the deepest enclosing object, also from
                               anywhere below it, such as code/
inside a store folder          that store, with what it holds
anywhere else                  the workspace root: what is due, what is
                               coming up, which projects are active
```

At an object, WHERE YOU ARE adds its REF, folder and description, and its
neighbours grouped by relation word and direction, with what each word
means for the work. UPCOMING lists the open tasks joined to it by any edge.
At the root, UPCOMING lists open tasks due within 7 days or overdue, counts
the other open tasks, and shows events in the next 14 days. LOG shows the
latest three entries and every summary entry, with the log's path and its
entry count.

Each whereami and house-rules layer is labelled with where it comes from:
`[workspace · ws]` is text that ships with ws,
`[workspace · ~/workspace/.context/whereami.md]` is your own note.

`[workspace · owner]` closes the workspace level in every briefing. It is
computed, not written: each time it builds a briefing, ws looks for the person
labelled owner and the profile identity, names them, and points to `ws owner`
for their details (`ws help owner`). A workspace with neither is briefed
without the line.

One aspect in full, without the rest, comes from `ws show`
(`ws help show`):

```bash
ws show purpose of project:<key>
ws show log of project:<key>
```

## Writing the notes

The hand-written part lives in `.context/` folders as plain Markdown, which
you and your agents edit directly; ws reads them and writes none. They are
canonical, not derived: deleting a note loses it.

```text
~/workspace/.context/purpose.md             your goals: where every purpose
                                            chain ends
~/workspace/.context/whereami.md            what an agent should know about
                                            this workspace
~/workspace/projects/.context/whereami.md   anything about your projects
<project>/.context/purpose.md               what this project is for
<project>/.context/log.md                   what has happened, newest first
<project>/.context/instructions.md          house rules for this project
```

Three levels may hold notes. The workspace root may hold `whereami.md`,
`instructions.md`, `purpose.md` and `log.md`. A store folder (projects,
resources, literature, documents, tasks, logistics, profile) may hold
`whereami.md` and `instructions.md`, and `log.md` where sessions work in the
store itself. A folder-backed object, that is a project or subproject, a
resource or a literature item, may hold all four. Record-only kinds such as
people, tasks and documents own no folder, so they have no purpose or log of
their own.

Every note is optional, and an empty note counts as absent. ws ships the
generic whereami and house-rules text for the workspace and each store, so
your notes add only what is specific to you.

`whereami.md`
: What a place is.

`instructions.md`
: How to work there.

`purpose.md`
: What the object is for, as an outcome: "find out whether ...", "make this
  package easy to use for ...". Phrase a research question as a question,
  so that a clear "no" also counts as an answer. The purpose belongs to the
  person; agents propose changes to it.

`log.md`
: What has happened, one entry per finished piece of work or decision,
  newest first.

Which purpose an object serves above it is an edge, not text. The briefing
follows outgoing `contributes-to` edges until none remains or the chain
would repeat an object:

```bash
ws relate project:<key> to project:<parent> as contributes-to
```

A log entry starts with a `## ` heading, conventionally the date and host:

```markdown
## 2026-10-09 · mbp
- Did: what changed
- Decided: what was decided, and why
- Next: what is open
```

When the log grows long, fold the oldest entries into one entry headed
"Summary of ...". Text before the first heading is the log's preamble.

A project without `.context/log.md` is briefed from its root `LOG.md`, and
one without `.context/purpose.md` from its README's `## Purpose` section;
both are marked as the older location and never moved or rewritten. To
move a log, run this inside the project:

```bash
mkdir -p .context && git mv LOG.md .context/log.md
```

## Briefing every session automatically

Run `ws context` when a session starts; it stays silent outside the
workspace, so a global hook leaves other sessions alone. Hooks may not see
your shell's `PATH`, so give the absolute path of `ws`; the examples
assume `~/.local/bin/ws`.

Claude Code: a SessionStart hook in `~/.claude/settings.json`, whose output
becomes part of the session's context:

```json
"hooks": {
  "SessionStart": [
    { "hooks": [ { "type": "command", "command": "/Users/<you>/.local/bin/ws context" } ] }
  ]
}
```

Codex: the same hook in `~/.codex/hooks.json`, as
`{"hooks": {"SessionStart": [...]}}`. Codex runs a new hook only after you
review and trust it with `/hooks`.

Harnesses without hooks, such as OpenCode: nothing to add. The `AGENTS.md`
that `ws init` writes at the workspace root tells any agent reading it to run
`ws context` when no briefing is in its context, and it holds where a hook
exists too. Outside the workspace there is nothing to brief, on purpose.

## For programs

`--json` prints the same content as one object with `briefing`, `subject`,
`ref`, `store`, `folder`, `whereami`, `owner`, `instructions`, `purpose` and
`log`. `owner` is `null` without an owner, else its `name`, `person` and
`identity`; either REF is empty when that record does not exist.
Objects add `description`, `neighbours`, `tasks` and `serves`, stores add
`listing`, and the root adds `agenda`. Each whereami and instructions layer
carries `level`, `source`, `shipped` and `text`.
