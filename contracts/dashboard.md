# Dashboard contract

Usage: `ws help rebuild dashboard`.

`ws rebuild dashboard` renders one self-contained page, `dashboard.html`, at
the workspace root. It is a derived view, like the search index and the
generated wiki: it reads canonical records and relations, writes only that
file, and deleting it loses nothing. It is never read back as a source of
truth, and building it never changes a record or invalidates the index.

## Content

Everything on the page comes from the records, so the page is the same for
any workspace and carries no hand-written or personal text:

- totals: objects, kinds, relations, relation words, open tasks, objects
  without a relation;
- due and coming up: open tasks with a `due` date, overdue first, and events
  whose `end` (else `start`) has not passed; open tasks without a date follow;
- recently added: objects by `created_at`, a project's `created` date, or a
  literature item's citation file date where no creation date is recorded;
- projects grouped by lifecycle status (`statuses.md`);
- objects not yet connected, counted by kind;
- the graph of every object and relation, with the relation vocabulary and
  object tables as its table view.

A task is open unless its status is `done`, `dropped`, `cancelled`,
`closed`, `complete` or `archived`; absent status means open. "Overdue" and
"today" are judged when the page is viewed, not when it was built.

## Guarantees

- The page is one file with no network access: data, styles and script are
  inline, and names are inserted as text, never as markup.
- The write is atomic (a temporary file replaced in one step), so a reader
  never sees a half-written page.
- The graph layout is deterministic: the same data draws the same picture.
- Colour marks three families of kinds (people and places; your work;
  sources) and is validated for colour-blind readers; shape distinguishes
  the kinds within a family, so colour is never the only cue.

## Keeping it out of history

`dashboard.html` is rebuildable output. A workspace kept under version
control ignores it, like `wiki/generated/` and the `by-*` views.
