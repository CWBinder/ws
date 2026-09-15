# Documents contract

Usage: [Filing documents](../docs/documents.md).

Documents form a managed catalogue. `ws add document` creates one stable
YAML record under `documents/items/`.

The default mode moves the source file into `workspace/documents/files/`.
`--mode copy` preserves the source and copies it there; `--mode reference`
explicitly keeps the source outside the workspace. The metadata record stores
the effective path. Relationships are written separately as canonical
edges; ingestion takes no endpoint-linking flags.

`--ensure` makes `add` idempotent by effective path: when the stored path
matches exactly one existing record, that record is returned instead of
creating a new one. Records carry no content digest; duplicate detection
during a bulk registration is the migration pass's job, computed transiently
rather than stored.

## Derived views

Managed files remain in `documents/files/`. Browse entries are relative symlinks
whose shape is governed by [folder anatomy](folder-anatomy.md). Ingestion and
edits rebuild the views. Related-object facets come from canonical edges;
multiple appearances never duplicate the document file.

## Classification

Document classification is faceted. The initial facets are `type`,
`organisation`, and `date`; year and month are derived from date and are not
stored separately. Subject is not a controlled facet.

The controlled vocabulary for the `type` facet is canonical at:

```text
~/workspace/documents/document-taxonomy.yaml
```

New document records store the selected value as:

```yaml
classification:
  type: presentation
```

The older top-level `document_type` key remains readable during migration but
must not be written for new records.

In an interactive terminal, canonical `ws add document FILE` prints the
valid types and prompts for one when `--type` is absent. Tab completes valid
values. An unknown value is added only after explicit confirmation. It
then prompts for the document date; an empty date places the document in the
derived `unclassified/` bucket of the date view.

Non-interactive adds never change the taxonomy implicitly. An unknown
`--type` fails unless `--add-type` is supplied. A unique prefix such as `pr`
may resolve to `presentation`.

`ws delete document:<key> ...` deletes document records outright — no
tombstone — and removes every relation touching them; edges are never left
dangling. A managed file under `documents/files/` is moved to the Trash
with the record's deletion, so the operation stays recoverable; external
(reference-mode) files are never touched. `--dry-run` previews. Merge
tombstones are different: `merged` records from duplicate folding stay,
because their REFs redirect.

Renaming a type updates matching canonical document metadata to the new
value. Removing a type is refused while any document uses it.

## Extension and compatibility rules

- Additional classifiers must have one canonical representation. Continue
  deriving year/month from date and organisations from relationships.
- Retain reads of legacy `document_type`; new writers use `classification.type`.
  Removing legacy support or changing paths/identity requires
  [an explicit migration plan](README.md#changing-a-contract).
- New ingestion or deletion modes must state ownership of the source file.
  Preserve external files on deletion and preserve the distinction between
  deletion and merge redirects.
- Verify validation/taxonomy changes, effective-path idempotency, relationship
  cleanup and managed versus external file handling when extending writers.
