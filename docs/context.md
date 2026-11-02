# Briefing a session

A fresh session starts with an empty memory. `ws context` gives it five
answers about the place it starts in, the most lasting first:

- **where it is**: what the workspace and this part of it are, and what the
  object here is connected to;
- **how to work here**: the house rules, from the workspace down to the object;
- **what it is for**: the object's purpose, and the purposes it serves above it;
- **what is coming up**: the open tasks that concern it, or at the root what
  is due and which events are near;
- **what has happened**: the latest entries of its log.

Every text layer is labelled with where it comes from: `[workspace · ws]` is
text ws ships, `[workspace · ~/workspace/.context/whereami.md]` is your own
note. A section the place cannot have, such as a store's purpose, is left out.

The rules behind it are in the [context contract](../contracts/context.md).

## Reading a briefing

```bash
ws context                          # the folder you are in
ws context project:<key>            # any object, from anywhere
ws show purpose of project:<key>    # one aspect in full
ws show log of project:<key>
ws show location of project:<key>
ws show instructions of project:<key>
```

Bare `ws context` resolves the folder it runs in. Inside a project or
resource folder (or anywhere below it, such as `code/`) it briefs that
object; in a store folder such as `projects/` it briefs the store and lists
what it holds; at the workspace root it lists what is due, what is coming up
and which projects are active. Outside the workspace it prints nothing.

`ws show REF` adds a `purpose:` and a `log:` line under the record once the
object has those notes.

## Writing the notes

The hand-written part lives in `.context/` folders, as plain Markdown that
you and your agents edit directly:

```text
~/workspace/.context/purpose.md               your goals: where every purpose chain ends
~/workspace/.context/whereami.md              anything an agent should know about this workspace
~/workspace/projects/.context/whereami.md     anything about your projects in general
<project>/.context/purpose.md                 what this project is for
<project>/.context/log.md                     what has happened, newest first
<project>/.context/instructions.md            house rules for this project only
```

All of them are optional. ws ships the generic whereami and house-rules text
for the workspace and each store, so your files only add what is specific
to you.

**A purpose** says what the object is for, as an outcome: "find out
whether…", "make this package easy to use for…". Phrase research questions
as questions, so that a clear "no" also counts as an answer. Which purpose
it serves above it is an edge:

```bash
ws relate project:<key> to project:<parent> as contributes-to
```

**A log** gets one entry per finished piece of work or decision, newest
first:

```markdown
## 2026-10-09 · mbp
- Did: what changed
- Decided: what was decided, and why
- Next: what is open
```

When it grows long, fold the oldest entries into one entry headed "Summary
of …". A briefing shows the latest three entries and every summary.

A project that still keeps its log as `LOG.md` at its root, or its purpose
only in its README's Purpose section, is briefed from those, marked as the
older location. To move a log: `mkdir -p .context && git mv LOG.md .context/log.md`
inside the project.

## Briefing every session automatically

Run `ws context` when a session starts. Each harness does this differently.
The examples assume `ws` is installed at `~/.local/bin/ws`; hooks may not see
your shell's `PATH`, so use the absolute path.

**Claude Code**: a SessionStart hook in `~/.claude/settings.json`. Its output
becomes part of the session's context:

```json
"hooks": {
  "SessionStart": [
    { "hooks": [ { "type": "command", "command": "/Users/<you>/.local/bin/ws context" } ] }
  ]
}
```

**Codex**: the same hook in `~/.codex/hooks.json`, as `{"hooks": {"SessionStart":
[...]}}`. Codex runs a new hook only after you review and trust it (`/hooks`).

**Harnesses without hooks**, such as OpenCode: one line in the global
instructions file the harness reads:

```text
If your working directory is inside ~/workspace and your context contains no
WORKSPACE BRIEFING, run `ws context` before doing anything else.
```

Hooks are global, but `ws context` stays silent outside the workspace, so
sessions elsewhere are unaffected. The same conditional line also serves as a
fallback where a hook exists.
