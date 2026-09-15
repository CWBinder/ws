# Bundling supporting files

A resource groups supporting files that do not need separate identities.
Use a document for a file you want to classify and relate individually, a
project for structured ongoing work, and literature for a bibliographic work.

## Create and fill a bundle

```bash
ws create resource "Workshop materials"
ws add resource:workshop-materials /path/to/handouts --mode copy
ws resources files resource:workshop-materials
ws resources path resource:workshop-materials
```

Use the REF actually printed by create. Add accepts a file or directory;
`--mode copy` preserves the source. Its default mode moves the source into the
bundle. `--name` chooses a destination subpath; consult `ws help add resource`.
Contents can have any useful folder structure.

## Find and connect it

```bash
ws search resources workshop
ws show resource:workshop-materials
ws relate resource:workshop-materials to project:<key> as supports
ws resources views rebuild
```

Relationships attach to the bundle. Its child files have no individual REFs.
Browse resources by connected organisation, project or event; see [Browsing](browsing.md).

## Move an individually registered document into a bundle

Inspect the document with `ws show document:<key>` and note its actual file
path and relationships. Move its file, then preview deletion of the old record:

```bash
ws add resource:workshop-materials /actual/document/file.pdf --name handout.pdf
ws delete document:<key> --dry-run
ws delete document:<key>
```

Deleting the record removes its relationships. Reassert any meaningful
bundle-level connections on the resource. Any managed document file still
present at deletion goes to the Trash. Moving the file alone does not transfer
its relationships. In the other direction, deliberately register a child as
a document when it needs an independent identity; this is never automatic.

Before removing a whole bundle, use `ws delete resource:<key> --dry-run` and
inspect the output. See `ws describe delete` for declared effects.

Maintaining the implementation: [resource contract](../contracts/resources.md).
