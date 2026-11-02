# Listing objects

```bash
ws list
ws list tasks --open
ws list documents --type contract
```

List enumerates the objects of one kind, named in the plural as the first
word. Bare `ws list` counts the objects of every kind instead. Each kind
takes its own filters after the kind word; its page lists them, for example
`ws help list tasks`.

Rows start with the object's REF, followed by tab-separated columns that
vary by kind: name and status for most, the due date for tasks, the type
for profile objects. The REF is what `ws show`, `ws edit` and `ws delete`
take. For programs, `--json` prints the rows, or the counts for bare
`ws list`. `ws list projects` is the exception: it prints REFs only and
has no `--json`.

## List or search

List answers "what is there"; search answers "where is the thing I mean".
To find objects by words, use `ws search` (`ws help search`). A search
with a kind but no words is refused and points back here, carrying the
filters already typed.

## Filters worth knowing

- `--type` filters the kind's own classifier, the same meaning it has on
  `ws search`; for documents, projects and profile objects the values come
  from the kind's taxonomy.
- `--open` keeps tasks whose status does not close them. These words close
  a task: `done`, `dropped`, `cancelled`, `canceled`, `closed`, `complete`,
  `completed`, `archived`. `--status WORD` matches one word exactly,
  ignoring case, and `--status open` also matches tasks with no status.
  The dashboard and `ws context` count open tasks the same way.
- Event filters compare the event's start date with today or the given
  dates.

## Pitfall

Every kind but projects stops at 100 rows without saying so. Raise
`--limit` when a count from bare `ws list` is larger than what a listing
shows.
