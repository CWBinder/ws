# Creating a task

```bash
ws create task Book the seminar room --due 2026-11-15 --priority high
```

The title's words are joined, so quotes are optional. ws prints the new
REF, `created: task:book-the-seminar-room`; use it to relate the task. What
a task is, and how it is closed, is in `ws help tasks`.

## The prompts

On a terminal, ws asks for whatever the flags left empty, in this order:

```text
Title         only when none was given
Description   Enter skips
Due           YYYY-MM-DD; a malformed date is asked again
Priority      for example low, normal, high
Aliases       comma-separated
```

Every prompt can be skipped with Enter. `--due ""` means no due date and
skips that prompt. `--interactive` forces the prompts. `--non-interactive`,
`--json` or running without a terminal, as an agent does, never prompts:
what the flags leave out stays empty.

The prompts never ask which project, person or event the task belongs to.
Those are relations, made afterwards:

```bash
ws relate task:book-the-seminar-room to project:<key> as concerns
```

## Reusing an existing task

Without `--ensure`, every call creates a task: the same title twice gives
`task:book-the-seminar-room` and `task:book-the-seminar-room-2`. With it,
a task whose title or alias matches, ignoring case and spacing, is reused
and ws prints `exists:` instead of `created:`:

```bash
ws create task Book the seminar room --due 2026-11-15 --ensure
```

On a match, the facts you pass fill only fields that are still empty, and
new aliases are added. The status is never changed this way; close a task
with `ws edit task:<key> --status done`. When more than one task matches,
ws names them and writes nothing.

`ws tasks ensure` does the same without prompts and prints only the REF,
which suits scripts. With `--json`, both carry a `created` flag.

## Recording the source

`--source` says who or what asked for the task, `--observed-at` when, as an
ISO date. Both go into the record's provenance with the fields they set:

```bash
ws create task Send Maria the appendix plot --due 2026-11-03 \
  --description "She needs it before the paper call." \
  --source "email from Maria Schwarz" --observed-at 2026-10-28
```
