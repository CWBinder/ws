# Filing documents

A document is a file with its own searchable record, classification and
relationships. Start with [Getting started](../GETTING-STARTED.md) for a small
project-and-document tutorial. Use a [resource](resources.md) when a collection
of files only needs one identity.

## Add a file

```bash
ws documents types list
ws add document /path/to/report.pdf --type report --mode copy --non-interactive
```

The default mode moves the source into `documents/files/` in your workspace.
`--mode copy` leaves the original in place. `--mode reference` records the
external path, which must remain accessible. `--ensure` reuses a unique
record with the same effective path; it does not compare file contents.

In a terminal, adding without a type opens prompts for type and date. With
non-interactive input, pass the facts you know as flags. An unknown type needs
explicit `--add-type`; scripts never silently extend your vocabulary.
See `ws help add document` for the full set of fields and modes.

## Inspect, connect and find it

Use the actual REF returned by add or search:

```bash
ws show document:<key>
ws relate document:<key> to project:<project-key> as belongs-to
ws search documents report
ws show relations of document:<key>
```

`show` gives the record and content path. Classify with a document type and
date; relate to organisations, projects or events. See
[Document classification](concepts/document-classification.md) for the model.
Views are rebuilt after ingestion and edits. [Browsing](browsing.md) explains
how to reach the same file through different folders.

## Maintain classifications and records

```bash
ws edit document:<key> --type report
ws documents types add TYPE
ws documents types rename TYPE --to NEW-TYPE
ws documents types remove TYPE
ws documents views rebuild
ws check
```

Replace uppercase placeholders with your values. Renaming a type updates
records that use it. Removing a type is refused while records still use it.
Use `ws edit document:<key> --help` for other editable fields.

## Delete deliberately

```bash
ws delete document:<key> --dry-run
ws delete document:<key>
```

Deletion removes the record and its relationships. A managed file moves to
the Trash; a reference-mode external file is left in place. Inspect the
preview before executing deletion.

Maintaining the implementation: [document contract](../contracts/documents.md).
