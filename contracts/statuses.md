# Status Contracts

Shared lifecycle vocabularies.

## Project Status

Allowed project `status` values:

```text
idea      planned but not active
active    currently worked on
paused    intentionally inactive
complete  finished but kept current
archived  inactive historical record
```

Use in:

```text
projects/items/<project>/project.yaml
```

Set with `ws create project --status` and change with
`ws edit project:<key> --status`.

## Task Status

Task `status` is a free word, written only when set; an absent status reads
as `open`. These words close a task, and every other one leaves it open:

```text
done  dropped  cancelled  canceled  closed  complete  completed  archived
```

The set is `catalog.CLOSED_TASKS`. `ws list tasks --open`, the dashboard's
due list and the open tasks in a `ws context` briefing all read it, so they
agree on what is still open. `ws list tasks --status WORD` matches one word
exactly, ignoring case, with `open` also matching tasks that have no status.

Set with `ws create task --status` and change with
`ws edit task:<key> --status`.
