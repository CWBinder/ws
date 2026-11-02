# Relating two objects

```bash
ws relate person:maria-schwarz to organisation:example-institute as works-at
```

The command is a sentence: subject, object, words. `to` and `as` are
optional filler, so `ws relate A B --as works-at` makes the same edge.
Both ends must be full REFs; names, aliases, bare keys and paths are
refused, and `ws search` finds the REF. ws prints the edge's own REF:

```text
created: relation:<id>
person:maria-schwarz --works-at--> organisation:example-institute
```

No create or add command takes relation flags, so relate a new object
right after making it, with the REF that command printed. What an edge
is, and how to inspect it, is in `ws help relations`.

## Choosing the words

Run `ws relations` first. It lists every word in use, how many edges carry
it and the kinds it connects, subject first:

```text
works-at        3 edges    person → organisation
concerns        5 edges    task → person (3), task → project (2)
```

- **Reuse before inventing.** A word that fits is better than a new one
  that fits slightly better: `works-at` and `employed-at` side by side
  split the graph in two.
- **Keep the same direction.** `works-at` runs person → organisation, so
  the person is the subject. Read the edge aloud: "Maria works at Example
  Institute".
- **Assert one direction only.** Every edge shows at both ends, as `-->`
  on the subject and `<--` on the object, so an inverse edge such as
  `employs` adds nothing but a second spelling.
- **Be specific.** Without words the edge is `related`, which
  `ws check relations` flags for refining.
- **State only what is known.** Relate what a source states or the
  material makes evident, never a connection that merely seems plausible.

Words are lowercased and spaces become hyphens, so `as works at` is stored
as `works-at`. Nothing else is changed, so type other words in kebab-case.

A few words carry meaning for ws itself (`depends-on`, `contributes-to`
and `represents`, see `ws help relations`); use them only in that sense.

## Dates

A relation that holds for a period, such as a job, a membership or a role,
carries its window:

```bash
ws relate person:maria-schwarz to organisation:example-institute as works-at \
  --from 2024-10-01 --until 2026-09-30
```

Both take an ISO date or date-time, and the start may not be after the
end. Leave out what is unknown. When the relationship ends, set `--until`
on its edge rather than deleting it; an ended relationship is still true.

The dates are part of the edge. Relating the same two objects with the
same words but other dates makes a second edge, so date an existing edge
by editing it:

```bash
ws edit relation:<id> --from 2024-10-01
```

## Provenance

`--source` says who or what asserted the edge, `--observed-at` when, as an
ISO date. Both are stored on the edge, and `ws show relation:<id>` prints
them. Record both whenever you know them.

Asserting an edge that already exists, with the same ends, words and
dates, is a no-op: ws prints `exists:` and the edge's REF, and records
nothing new, not even a new source. Later changes made with
`ws edit relation:<id>` and a source or date are kept in the edge's
history.

## Fixing a mistake

```bash
ws edit relation:<id> --as member-of
ws delete relation:<id>
```

Edit changes the words and dates. The ends cannot be edited: for a wrong
direction or a wrong object, delete the edge and relate again. Delete
prints the `ws relate` command that would restore the edge. An object
cannot be related to itself.

## Examples

```bash
ws relate task:<key> to project:<key> as concerns
ws relate person:<key> to event:<key> as attended \
  --source "attendee list" --observed-at 2026-09-02
ws relate project:<key> to literature:<key> as references
ws relate document:<key> to organisation:<key> as issued-by
```
