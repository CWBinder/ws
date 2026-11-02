# Relations

A relation is a directed edge between two objects: a person works at an
organisation, a document presents a project, a task concerns a person. The
edges carry as much knowledge as the records, and they are how ws answers
"what belongs to this?".

A relation reads as a sentence, subject first:

```text
person:maria-schwarz  --works-at-->  organisation:example-institute
SUBJECT               --WORDS-->     OBJECT
```

Any two objects can be related, of any kinds. Relations are their own
layer, not a domain: an edge belongs to neither end. To make one, read
`ws help relate`.

## Where relations live

```text
~/workspace/relations/rel_<id>.yaml    one record per edge
```

Edges are stored once, never copied into the records at either end.
`ws show` and the derived views join them in when they are read. The
store can be moved with `WS_RELATIONS_DIR` (`ws help configuration`).

## Fields

`subject`, `object`
: The two ends. On disk they hold internal ids, or `project:` and
  `literature:` REFs; on screen, ws prints REFs and names.

`relation`
: The words, in lowercase kebab-case, such as `works-at`.

`valid_from`, `valid_until`
: The window of time the relation is true for; empty when unknown or
  unbounded.

`source`, `observed_at`
: Who or what asserted the edge, and when.

`provenance`
: One entry for each later change made with `--source` or
  `--observed-at`, naming the fields it changed.

`id`, `schema_version`, `created_at`, `updated_at`
: Bookkeeping, written by ws.

## Finding edges

An edge's REF is `relation:<id>`: its record id without the `rel_` prefix.
Edges are never search hits or a `ws list` kind; they are found through
their ends. `ws show person:maria-schwarz` prints the record and then every
edge touching it, each starting with the edge's REF:

```text
relations: 2
  relation:<id>  --works-at--> organisation:example-institute (Example Institute)  [from 2024-10-01]
  relation:<id>  <--supervises-- person:alex-example (Alex Example)
```

`-->` leaves the object and `<--` arrives at it; `--as WORDS` narrows the
list to one relation. With an edge's REF in hand:

```bash
ws show relation:<id>
ws edit relation:<id> --as member-of
ws edit relation:<id> --until 2026-09-30
ws delete relation:<id>
```

`show` prints the edge in full: both ends, the words, the dates, the source
and the history of changes. `edit` changes the words or the dates; an empty
value, `--until ""`, clears a date. `delete` removes the edge.

`ws relations` lists the vocabulary in use: each word, how many edges carry
it, and the kinds it connects, subject first. Read it before choosing words
for a new edge.

## Ended, wrong and duplicate edges

Relations have no status: an edge exists or it does not, and every edge
that exists counts. A relationship that ended is still true and keeps its
edge, with `--until` set. An edge that is wrong or unwanted is deleted.
ws keeps no copy of a deleted edge, so `ws delete relation:<id>` prints the
`ws relate` command that would restore it.

Asserting an edge that already exists, with the same ends, words and
dates, changes nothing. Deleting an object deletes every edge touching it,
so no edge is ever left dangling. Merging a duplicate person, organisation
or event moves its edges onto the record that is kept
(`ws help logistics`).

`ws check relations` reports ends that no longer resolve, an object related
to itself, malformed or inverted dates, duplicate edges, and edges with the
generic word `related`. It reports and never repairs.

## What reads the edges

The vocabulary is open, and ws attaches meaning to a few words only:

```text
depends-on       project to project: deleting the project depended on is
                 refused; `--use-project` on `ws create project` or
                 `ws projects install` makes this edge
contributes-to   ws context follows it upwards to show the purpose served
represents       profile entry to literature: the paper supplies the CV
                 citation, and deleting the paper is refused while the
                 edge exists
```

Beyond that, any edge counts. The `by-organisation/`, `by-event/` and
`by-project/` browse folders of the other domains file an object under
the names of everything it is related to, whatever the words and
direction. `ws context REF` groups an object's neighbours by words and
lists the open tasks around it. The wiki and the dashboard graph are drawn
from the same edges. Document browse folders follow a new edge at once;
the others at the next `ws rebuild views`.

## Older spellings

`ws unrelate`, `ws show relations of REF` and `ws relations edit` still
run, and each names its current spelling on stderr.
