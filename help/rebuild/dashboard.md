# Rebuilding the dashboard

```bash
ws rebuild dashboard
```

The dashboard is one page, `dashboard.html` at the workspace root, that
shows the workspace at a glance. Open it in any browser; it needs no
network, since its data, styles and script are all inside the file.

## What it shows

- Totals: objects, kinds, relations, relation words, open tasks, and
  objects without a relation.
- Due and coming up: open tasks with a due date, overdue first, and events
  whose end, or else start, has not passed; open tasks without a date
  follow.
- Recently added: objects by when they entered the workspace, from the
  record's creation time, a project's `created` date, or for literature the
  date of its citation file.
- Projects grouped by status.
- Objects not yet connected, counted by kind.
- The whole graph of objects and relations. Hover a node to identify it,
  click it to list its relations the way `ws show` does, search by words,
  filter by kind, or switch to a table view of the relation words and
  objects.

A task is open unless its status is `done`, `dropped`, `cancelled`,
`canceled`, `closed`, `complete`, `completed` or `archived`; a task without
a status is open. This is the same test `ws list tasks --open` and
`ws context` use.

Everything on the page comes from the records, so it carries no
hand-written text and looks the same for any workspace. Colour marks three
families of kinds (people and places, your work, sources) and is chosen to
be readable for colour-blind readers; shape tells the kinds within a family
apart, so colour is never the only cue. The same data always draws the
same picture.

## A snapshot

The page shows the workspace as it was at the last rebuild: rebuild it
after changes. Only "overdue" and "today" are judged when you view the
page, not when it was built.

Like the other derived layers it is never read back, and deleting it loses
nothing. Building it reads records and relations, writes only this file,
and never changes a record or discards the search index. The file is
replaced in one step, so a browser never sees a half-written page. A
workspace kept in git ignores `dashboard.html`.
