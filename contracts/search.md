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

Query words may be quoted or unquoted, and each matches on its own: a hit
contains every word, in any order, somewhere in its name, key, aliases or other
metadata values. Field names are not discovery terms. Matching ignores case,
non-ASCII letters included. Filler words (`for`, `the`, `about`, `of`, …) are
dropped unless the query has nothing else, so `ws search resources for delft`
finds what `ws search resources delft` finds.

Hits rank by how directly they answer the query: the whole query equal to a
name, key or alias first, then names starting with it, then names containing
it, then hits whose names hold every word, and last hits that need incidental
metadata for some word.

When no hit has every word, the text output says so, names any word that
matched nothing, and lists the hits holding some of the words, most words
first. `--json` stays strict: it returns `[]` and writes the same note to
stderr, so a program never mistakes a partial hit for a match.

A first word that exactly names a kind, singular or plural (`document` or
`documents`, `person` or `people`, …), scopes the search to that kind; filler
in front of it is skipped (`ws search for resources delft`). The word is
compared as typed, so quoting it together with the next word
(`ws search "event horizon"`) keeps it a query word. Scoping filters the
result without changing the REF policy. `ws search` is the only spelling: no
domain carries a search of its own.

```bash
ws search Example Company
ws search organisations ExampleCo
ws search resources ExampleCo expenses
ws search documents slides --type presentation
```

A kind word alone is not a search (`ws search documents` or
`ws search document` fails and points at `ws list documents`); enumeration is
list's job. The refusal must hand over
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
