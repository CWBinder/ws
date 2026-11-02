# Rebuilding derived views

```bash
ws rebuild
ws rebuild views documents
```

Four layers of the workspace are derived from the records and relations,
and deleting any of them loses nothing:

```text
<domain>/by-*/        views       browse folders of links to the content
index/index.sqlite    index       the cache that search reads
wiki/generated/       wiki        Markdown notes for Obsidian
dashboard.html        dashboard   the workspace at a glance, in a browser
```

Bare `ws rebuild` regenerates all four, in that order. Name a target to
regenerate one, and add a domain to `views` to rebuild only that domain's
folders. Each target has its own page below.

Rebuilding reads records and relations and writes only the derived layer.
It never changes a record, and it never discards the search index.

## When to rebuild

Some changes refresh a view at once. Adding or editing a document, editing
a project, creating or editing a profile object, making, changing or
removing an edge that touches a document, and deleting any object refresh
the browse folders concerned. Every change made through ws discards the
search index, which the next search rebuilds.

Everything else waits for a rebuild:

- the browse folders, after creating a project or resource, adding
  literature, relating objects other than documents, or changing
  `folder-anatomy.yaml`;
- the wiki and the dashboard, which are snapshots, after any change you
  want to see there;
- the search index, after a change made outside ws.

`ws check` reports a stale index and a broken browse settings file
(`ws help check`).

## Rules

- Never file anything into a derived folder. A rebuild replaces every
  `by-*` folder and the whole of `wiki/generated/`; keep your own notes
  elsewhere.
- A mistake in `folder-anatomy.yaml` is reported before any browse folder
  is wiped, so the previous ones stand. Bare `ws rebuild` still regenerates
  the other three layers, which do not read that file, and then exits with
  a non-zero status.
- A workspace kept under version control ignores the derived layers.

Each layer once had its own spelling: `ws <domain> views rebuild`,
`ws index rebuild`, `ws wiki build` and `ws dashboard build`. They still
run the same command, and print the current spelling on stderr.
