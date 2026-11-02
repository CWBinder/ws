# Connecting and finding records

People and agents use the same sequence: find references, inspect records,
then act on those references. A REF looks like `project:first-project` or
`document:report`; names, aliases, paths and internal IDs cannot replace it.

## Retrieve context

```bash
ws search report
ws show document:<key>
```

Use the actual REF returned by search. `show` locates the canonical content
and lists the record's relations underneath; read that file or project for
the full information. Use `ws search documents
report` to restrict the search. Every word must match, in any order, so a few
distinctive words find more than a sentence; when no record has them all,
search says which word matched nothing and shows partial matches. Most read
commands offer `--json` for programs.

## Add an explicit connection

Find both endpoint REFs, then inspect existing relationship words:

```bash
ws relations
ws relate document:<key> to project:<key> as belongs-to
```

`ws relations` prints each word with its edge count and the kinds it
connects, subject first (`works-at   3 edges   person → organisation`). The
sentence is directional: subject, object, relation. Words are free-form and
normalized to kebab-case. Reuse an existing word when it expresses the same
relationship, the same way round. Repeating the same edge is a no-op.

Creation and ingestion do not ask for conceptual links. Add them explicitly
afterward. A project package install dependency is a special case: recording
the install recipe also records its `depends-on` edge.

## Inspect, change or remove a connection

`ws show REF` lists every edge touching the record, each by its own REF:

```text
relations: 2
  relation:01KYTNTBD9T7K071PSJ568ZDZ8  --belongs-to--> project:first-project (First Project)
  relation:01M2ZN0XKW2T4CMR3G59W68H1F  <--presents-- event:<key> (Workshop)
```

`-->` leaves the record and `<--` arrives at it; `--as WORD` narrows the
list. Use the edge's REF like any other:

```bash
ws show relation:<id>
ws edit relation:<id> --as part-of --until 2026-06-30
ws delete relation:<id>
ws check relations
```

`show` prints the edge in full, with dates, source and history. `edit`
changes the words, validity dates and provenance (`ws edit relation:<id>
--help`). `delete` prints the `ws relate` command that would restore the
edge. A relationship that ended can retain its validity dates; delete
assertions that are wrong or unwanted. Checks report inconsistencies without
repairing or deleting data.

Connections power related-object [browse folders](browsing.md) and the
[wiki](visualization.md). Learn the rationale in
[Relationship concepts](concepts/relationships.md).

Maintaining the implementation: [object](../contracts/objects.md) and
[relationship](../contracts/relations.md) contracts.
