# Searching the workspace

```bash
ws search march report
ws search documents march report
```

Search turns words into REFs. Every hit is one canonical `kind:key`
reference, which `ws show`, `ws edit`, `ws relate` and `ws delete` then
take. Names, aliases, titles, DOIs and arXiv identifiers are what you
search for; they are never operands of another command. Internal IDs are
not searchable at all.

The usual sequence is to find, inspect, then act:

```bash
ws search report
ws show document:<key>
ws relate document:<key> to project:<key> as belongs-to
```

## How words match

- Every word must match, in any order, somewhere in a hit's name, key,
  aliases or other metadata values. Field names do not count: searching
  for `description` does not match every record that has one.
- Matching ignores case, for non-ASCII letters too.
- Filler such as `for`, `the`, `about` or `of` is dropped unless the query
  has nothing else, so `ws search resources for delft` finds what
  `ws search resources delft` finds.
- A few distinctive words find more than a sentence.
- A resource's file names are searchable too; a match returns the resource
  once, never the file itself.

Hits rank by how directly they answer the query: the whole query equal to a
name, key or alias first, then names starting with it, then names
containing it, then hits whose names hold every word, and last hits that
need other metadata for some word.

When no hit has every word, search says so, names any word that matched
nothing, and lists the hits holding some of the words, most words first.
`--json` stays strict: it prints `[]` and writes the note to stderr, so a
program never mistakes a partial hit for a match.

## Searching one kind

A first word that names a kind, singular or plural, limits the search to
that kind, and filler in front of it is skipped:

```bash
ws search people for maria
ws search documents slides --type presentation
ws search "event horizon"
```

The kind word is compared as typed, so quoting it together with the next
word keeps it a query word: the last line searches every kind for "event"
and "horizon".

A kind word alone is not a search. `ws search documents` is refused and
points at `ws list documents`, keeping any filter already typed
(`ws help list`).

`--type` filters the kind's own classifier, exactly as on `ws list`. It
therefore needs a kind first, is refused for kinds without a type
(people, tasks, resources, literature), and refuses a value outside the
kind's taxonomy.

## The index

Search reads a derived SQLite index, `index/index.sqlite` in the workspace.
Every change made through ws discards it, and the next search rebuilds it
once; later searches reuse it until the next change. A change made outside
ws is not seen until `ws rebuild index`, and `ws check index` reports an
index that no longer matches the records. Deleting the index loses
nothing.
