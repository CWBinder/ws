# Documents contract

Documents form a managed catalogue. `ws add document` creates one stable
YAML record under `documents/items/`.

The default mode moves the source file into `workspace/documents/files/`.
`--mode copy` preserves the source and copies it there; `--mode reference`
explicitly keeps the source outside the workspace. The metadata record stores
the effective path. Requested endpoint links are written as canonical
relationship records.

`--ensure` makes `add` idempotent by effective path: when the stored path
matches exactly one existing record, that record is returned instead of
creating a new one. Records carry no content digest; duplicate detection
during a bulk registration is the migration pass's job, computed transiently
rather than stored.

Raw files remain in `documents/files/`. Derived browse views contain relative
symlinks to those files; their shapes are declared in the folder anatomy file
(see `folder-anatomy.md`); the default ring set is

```yaml
rings: [type, organisation, event, project, year > month]
depth: 2
```

so each value folder holds its documents flat plus nested `by-*` rings for
the facets not yet used along the path:

```text
documents/by-type/<type-or-unclassified>/
documents/by-type/<type>/by-year/<year>/by-month/<MM-Month>/
documents/by-year/<year>/by-organisation/<organisation>/
documents/by-organisation/<organisation>/by-type/<type>/
```

`unclassified/` is the fallback bucket at the first layer; deeper rings
simply omit documents missing the facet, and empty rings are never
created. Ingestion and
document edits rebuild these views automatically. Organisation folders are
derived from document-to-organisation relationships, so one document may
appear under multiple organisations without duplicating a file.
`ws documents views rebuild` recreates the views from canonical records,
relationships, and the anatomy file.

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

Manage the vocabulary with:

```text
ws documents types list
ws documents types add TYPE
ws documents types rename TYPE --to NEW-TYPE
ws documents types remove TYPE
```

Renaming a type updates matching canonical document metadata to the new
value. Removing a type is refused while any document uses it.
