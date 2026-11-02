# Editing objects and relations

```bash
ws edit task:<key> --status done
```

Edit changes one object or one relation, named by its full REF. The REF
says which kind it is, and the flags that follow are that kind's own, so
the usage below cannot list them. Ask for them with the REF in place:

```bash
ws edit document:<key> --help
ws edit relation:<id> --help
```

## What each kind can change

Record kinds (people, organisations, events, tasks, documents, resources,
profile) change their name and status, most also their description, and
the facts that belong to them: a task's due date and priority, a person's
emails, phones and preferred name, an organisation's website, an event's
dates, time zone and location, a document's type, date and tags. List
values change through paired flags, one to add a value and one to remove
it, so an edit never replaces a list wholesale.

Folder-backed kinds edit only the metadata the catalog holds. A project
changes its title, status, fields, subfields and keywords: edit rewrites
only those keys of `project.yaml` (`subproject.yaml` for a subproject) and
keeps every other line. A literature item changes its fields and
subfields. Everything else in such a folder is edited in place, and a
project gains capabilities with `ws projects install`
(`ws help projects install`).

A relation changes its relation words, its validity dates and its
provenance. A relationship that has ended keeps its edge with an end date;
delete only an edge that is wrong (`ws help delete`).

## Rules

- Renaming changes the display name only. The key, and with it the REF,
  never changes.
- Statuses are fixed vocabularies, not taxonomies. A project's is one of
  `idea`, `active`, `paused`, `complete`, `archived`. A task's is a free
  word; `done`, `dropped`, `cancelled`, `canceled`, `closed`, `complete`,
  `completed` and `archived` close it, and no status reads as open. For
  other kinds an absent status means active.
- Where a kind has a taxonomy (projects, literature, documents, profile),
  types, fields and subfields must come from it; the flag's help lists the
  allowed values and the command that extends them.
- Edges are never fields. To connect two objects, relate them
  (`ws help relate`).
- `--source` and `--observed-at` record who or what asserted the change,
  and when. They are added to the record's provenance together with the
  fields that changed.

## Examples

```bash
ws edit person:<key> --add-email maria@example.org \
  --source "email signature" --observed-at 2026-10-01
ws edit document:<key> --type invoice --date 2026-09-30
ws edit project:<key> --status archived --add-keyword decoding
ws edit relation:<id> --as part-of --until 2026-06-30
```

Edits to documents, projects and profile objects, and to edges that touch
a document, refresh their `by-*` browse folders at once. Other changes, such
as renaming an organisation that names a browse folder, appear there after
`ws rebuild views` (`ws help rebuild views`).
