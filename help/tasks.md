# Tasks

A task is one thing to do: an email to answer, a room to book, a plot to
send. It is a record, not a folder, and it is closed when it is done. Work
that spans sessions and needs judgement is a project instead
(`ws help projects`).

To make one, read `ws help create task`.

## Where tasks live

```text
~/workspace/tasks/<key>.yaml    one record per task
```

The key is the title slugified when the task is created, so the title
`Book the seminar room` gives `task:book-the-seminar-room`; a second task
with the same title gets `-2`. Renaming a task changes its title, never
its key, so a short title makes a short REF. Records are written only by
ws.

## Fields

`name`, `aliases`
: The title, and other words to find it by.

`description`
: One or two sentences: what done looks like, or the context needed.

`due`
: An ISO date (`YYYY-MM-DD`), or nothing.

`priority`
: A free word; `low`, `normal` and `high` are the customary ones.

`status`
: A free word, written only when set. An absent status reads as `open`.

`provenance`
: Which source asserted which fields, and when: from `--source` and
  `--observed-at` at creation, and one more entry for each later change
  that passes them.

`id`, `key`, `kind`, `schema_version`, `created_at`, `updated_at`
: Bookkeeping, written by ws.

What a task is about, who it is for and what it waits on are never fields.
They are relations, made with `ws relate` after the task exists.

## Open and closed

These status words close a task; every other word, and no status at all,
leaves it open:

```text
done  dropped  cancelled  canceled  closed  complete  completed  archived
```

`ws list tasks --open`, the due list on the dashboard and the open tasks in
a `ws context` briefing all read this one set, so they agree on what is
still open. `ws list tasks --status WORD` matches one word exactly, ignoring
case; `--status open` also matches tasks without a status.

```bash
ws list tasks --open
ws edit task:<key> --status done
ws edit task:<key> --due 2026-11-15 --priority high
```

A finished task is closed with a status, not deleted.
`ws delete task:<key>` is for a task that should not exist; it removes the
record and every relation on it.

## Connecting a task

A task belongs to a project, concerns a person or waits on another task by
relation. Run `ws relations` to see the words in use; for tasks these are
typically:

```text
task --concerns-->     person, organisation, project, event
task --depends-on-->   task, resource
task --supported-by--> resource
```

```bash
ws relate task:book-the-seminar-room to project:<key> as concerns
```

Relations are what make a task show up where it matters. `ws context REF`
lists the open tasks related to that object, in either direction, by due
date. Bare `ws context` at the workspace root lists open tasks that are
overdue or due within seven days, and counts the rest. See `ws help relate`
for choosing words.

## Duplicates

Tasks have no merge command. When two tasks turn out to be the same, keep
one, relate it to whatever only the other was related to, and delete the
other. `ws create task --ensure` and `ws tasks ensure` prevent the
duplicate in the first place (`ws help create task`). `ws check tasks`
warns when two tasks share a title or alias.
