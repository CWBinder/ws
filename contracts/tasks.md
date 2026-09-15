# Tasks contract

Tasks are structured first-class objects. Each task has a stable ID and one
canonical YAML record under `tasks/`. Project, assignee, and other cross-domain
links are relationship records rather than duplicated task fields.

## Facts and capture

A task's own facts are `description`, `due` (an ISO date), `priority` (a
free word; `low`, `normal`, `high` are the customary ones), plus the shared
`aliases` and `status`. Absent `status` means open.

`ws create task <title>` takes each fact as a flag. On a terminal it opens
the guided prompts for whatever the flags left empty, in capture order:
description, due date, priority, aliases. Every prompt is Enter-skippable;
a malformed due date is asked again. `--non-interactive` (or a non-terminal
stdin, or `--json`) never prompts. Which project, person, or event the task
belongs to is never asked: those are edges, made afterwards with
`ws relate task:<key> to <kind>:<key> as <word>`.
