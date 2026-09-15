# Document classification

A facet is one dimension of classification. A facet value is the value
assigned to a document.

```text
facet: type
value: presentation
```

The controlled list of valid type values is the document taxonomy. It belongs
to the documents domain and lives with the document library rather than in CLI
code.

`organisation` is a repeatable facet backed by first-class organisation IDs.
`date` is stored once as an ISO date. Generated browse views derive year and
month folders from that date:

```text
by-year/2026/by-month/09-September/
```

Missing values remain visible through the `unclassified/` fallback bucket
at the first layer of each ring; deeper rings simply omit them. The browse
trees are derived symlink views shaped by
`~/workspace/folder-anatomy.yaml`; the raw file remains canonical in
`documents/files/`.

Classification drives browsing. Typed relationships continue to drive
contextual graph traversal.
