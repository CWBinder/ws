# Search contract

Search reads a derived, rebuildable index. It never makes the SQLite index
canonical and never mutates domain records.

Canonical mutations invalidate the index. The next search rebuilds it once;
later searches reuse that cache until another mutation. Search must not
rebuild the index unconditionally for every query.

Names, aliases, keys, titles, bibliographic identifiers, classifiers, and
other domain metadata are discovery terms. Internal IDs are deliberately not
indexed. Every hit returns exactly one canonical `kind:key` REF; callers then
use that REF with show, edit, relation, citation, and attachment commands.

Query words may be quoted or unquoted. Exact name, key, and alias matches rank
before prefixes, general substrings, and incidental metadata matches. A first
word that exactly names a kind (`documents`, `people`, `organisations`, …)
scopes the search to that kind; anything else is a query word. Scoping filters
the result without changing the REF policy. `ws search` is the only spelling:
no domain carries a search of its own.

```bash
ws search Example Company
ws search organisations ExampleCo
ws search resources ExampleCo expenses
ws search documents slides --type presentation
```

A kind word alone is not a search (`ws search documents` fails and points at
`ws list documents`); enumeration is list's job. The refusal must hand over
a command that does what was asked, carrying the filters already typed:
`ws search documents --type presentation` points at
`ws list documents --type presentation`, never at a bare `ws list documents`
that silently drops the filter.

`--type` means the kind's own classifier here, exactly as it does on
`ws list` — never the kind itself, which the first word already names and
which has no second spelling. It therefore requires a kind scope, refuses a
kind that has no type classifier, and refuses a value outside that kind's
taxonomy. A filter that cannot match must say so; silently returning `none`
for a misunderstood flag is a defect, not a result.

Resource child filenames are searchable incidental metadata. A matching child
returns its containing `resource:<key>` once; child files never become hits of
their own.

## Result shape

`ws search --json` returns rows in the universal object vocabulary of
`objects.md`, the same shape the catalog commands emit:

```json
{"ref": "person:maria-schwarz", "kind": "person", "name": "Maria Schwarz"}
```

The SQLite columns are still named `type` and `title`. That naming is internal
to the cache and must not reach any output: the row mapping renames them at the
boundary, and both the text and `--json` branches read the renamed keys.
