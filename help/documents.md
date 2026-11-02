# Documents

A document is one file worth addressing on its own: an invoice, a
contract, a certificate, a slide deck. It gets a record with a
classification, can be related to projects, organisations, people and
events, and is found by search and through browse views.

Choose the kind by what needs its own identity. Files that only matter
together, such as the receipts of one claim, belong in one resource bundle
(`ws help resources`). A paper or book is literature, never a document,
even when it arrives as a loose PDF (`ws help literature`). To file a
document, read `ws help add document`.

## Where documents live

```text
~/workspace/documents/
  items/<key>.yaml          the records, one per document
  files/                    the managed files, flat
  document-taxonomy.yaml    the allowed document types
  by-type/  by-organisation/  by-event/  by-project/  by-year/
                            derived browse views, rebuilt by ws
```

The record and the file in `files/` are both canonical; the `by-*` folders
hold only symlinks and can be regenerated at any time. A document's
REF is `document:<key>`, where the key is made from its name when it is
added, lowercase and hyphenated. Renaming a document changes its name,
never its REF or its file.

A document added in reference mode keeps its file outside the workspace.
Its record stores the absolute path, which must stay reachable: a document
whose file is missing drops out of the views.

## Fields of a record

`name`, `aliases`
: What search finds the document by. The name defaults to the file name
  without its extension.

`path`, `path_root`
: Where the file is. For a managed file, `files/<file name>` relative to
  the documents folder, with `path_root: documents`; for a referenced file,
  its absolute path, with `path_root: external`.

`classification`
: The document's `type`, from the taxonomy, and its `date` as
  `YYYY-MM-DD`. Year and month are derived from the date, never stored.

`tags`
: Free-form words, searched but never grouped by.

`status`
: Absent means active. Only active documents appear in the browse views;
  any other status keeps a document searchable but out of `by-*`.

`provenance`
: Who or what asserted the facts, and when: `--source` and
  `--observed-at`.

Older records may carry a top-level `document_type`. It is still read, and
the next edit of the type replaces it with `classification.type`.

## Classification

A document is classified along five facets. Two are stored on the record:

```text
type          one value from document-taxonomy.yaml
date          one ISO date; the year and month views derive from it
```

Three come from relations, in either direction and with any relation word:

```text
organisation  every related organisation
event         every related event
project       every related project
```

There is no subject facet. A document is found by its name, aliases and
tags, and placed by its relations.

The type vocabulary is workspace data. ws never extends it silently: a new
type enters only through `ws documents types add`, through `--add-type` on
add, or when you confirm the prompt on a terminal. A unique prefix stands
for the full type, so `pr` means `presentation`; an ambiguous prefix is an
error that lists the matches.

```bash
ws documents types list
ws documents types add payslip
ws documents types rename payslip --to pay-slip
ws documents types remove pay-slip
```

Renaming a type updates every document that uses it. Removing a type is
refused while any document still uses it: reclassify those first with
`ws edit document:<key> --type ...`. `ws list documents --untyped` shows
the documents with no type yet.

## Browse views

The views are shaped by `~/workspace/folder-anatomy.yaml`. For documents
the rings are type, organisation, event, project and year with month
inside it, nested two levels deep:

```text
by-type/invoice/
by-organisation/<organisation name>/
by-year/2026/by-month/09-September/
by-type/invoice/by-year/2026/
by-project/<project title>/by-organisation/<organisation name>/
```

Each entry is a symlink named after the file and pointing at it, so one
file can appear in many folders without being copied. A document that
lacks a facet goes into that ring's `unclassified/` folder at the first
level and is simply left out deeper down.

Adding, editing and relating a document rebuild the document views. To
rebuild them by hand, run `ws rebuild views documents`.

## Working with documents

Use the REF that add or search printed:

```bash
ws search documents venue invoice
ws show document:<key>
ws relate document:<key> to organisation:<key> as issued-by
ws relate document:<key> to project:<key> as presents
ws edit document:<key> --type invoice --date 2026-07-15
```

`show` prints the record, where its file is, and its relations. Relation
words are free; `ws relations` lists the ones already in use, such as
`issued-by`, `submitted-to`, `presents` and `describes`. Pass an empty
`--date ""` to clear a date.

To retire a document into a resource bundle, or to give a file inside a
bundle its own record, see `ws help resources`.

## Removing a document

```bash
ws delete document:<key> --dry-run
ws delete document:<key>
```

Delete removes the record and every relation touching it, and rebuilds the
views. A managed file under `files/` goes to the Trash with it, so the
deletion stays recoverable; a referenced file outside the workspace is never
touched. Read the dry run before deleting.
