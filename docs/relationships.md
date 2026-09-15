# Connecting and finding records

People and agents use the same sequence: find references, inspect records,
then act on those references. A REF looks like `project:first-project` or
`document:report`; names, aliases, paths and internal IDs cannot replace it.

## Retrieve context

```bash
ws search report
ws show document:<key>
ws show relations of document:<key>
```

Use the actual REF returned by search. `show` locates the canonical content;
read that file or project for the full information. Use `ws search documents
report` to restrict the search. Most read commands offer `--json` for programs.

## Add an explicit connection

Find both endpoint REFs, then inspect existing relationship words:

```bash
ws relations
ws relate document:<key> to project:<key> as belongs-to
```

The sentence is directional: subject, object, relation. Words are free-form
and normalized to kebab-case. Reuse an existing word when it expresses the
same relationship. Repeating the same edge is a no-op.

Creation and ingestion do not ask for conceptual links. Add them explicitly
afterward. A project package install dependency is a special case: recording
the install recipe also records its `depends-on` edge.

## Remove or inspect connections

```bash
ws show relations of project:<key>
ws unrelate document:<key> to project:<key> as belongs-to
ws check relations
```

`unrelate` accepts the same endpoint syntax and prints a restore command.
To edit dates or provenance, use `ws help relations edit`. A relationship that
ended can retain its validity dates; delete assertions that are wrong or unwanted.
Checks report inconsistencies without repairing or deleting data.

Connections power related-object [browse folders](browsing.md) and the
[wiki](visualization.md). Learn the rationale in
[Relationship concepts](concepts/relationships.md).

Maintaining the implementation: [object](../contracts/objects.md) and
[relationship](../contracts/relations.md) contracts.
