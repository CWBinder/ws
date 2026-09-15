# Resources contract

A resource is a first-class, folder-backed bundle of arbitrary supporting
files. The folder is the object; its children are ordinary files and folders,
not workspace objects.

Canonical storage:

```text
~/workspace/resources/items/<key>/
  resource.yaml
  <arbitrary files and folders>
```

The folder name is the resource key and the public reference is
`resource:<key>`. `resource.yaml` contains the universal object fields from
`objects.md`; a minimal record is:

```yaml
schema_version: 1
id: resource_01K...
key: exampleco-travel-reimbursements
kind: resource
name: ExampleCo Travel Reimbursements
aliases: [ExampleCo expenses]
description: Travel reimbursement material for ExampleCo.
created_at: 2026-08-15T12:00:00+01:00
updated_at: 2026-08-15T12:00:00+01:00
```

There is no required structure beneath the resource folder. Child files have
no IDs, REFs, metadata records, or individual relationships. Search may index
their relative filenames for discovery, but returns the containing resource
once. Relationships attach to the resource object.

## Commands

```bash
ws create resource "ExampleCo Travel Reimbursements"
ws search resources ExampleCo expenses
ws show resource:exampleco-travel-reimbursements
ws resources path resource:exampleco-travel-reimbursements
ws resources files resource:exampleco-travel-reimbursements
ws add resource:exampleco-travel-reimbursements receipt.pdf
ws delete resource:exampleco-travel-reimbursements
ws relate resource:exampleco-travel-reimbursements organisation:example-company --as for
```

`ws add resource:<key> <path>` moves its path into the resource by default;
`--mode copy` preserves the source. It accepts either a file or a folder.
Paths are accepted here because the command explicitly ingests filesystem
content.

## Browse Views

Derived `by-*` rings sit at the resources domain root, beside `items/`,
rebuilt with `ws resources views rebuild`. Resources carry no classifiers,
so their ring set is kinds only — related objects resolved through the
relations store; the default declared in the folder anatomy file (see
`folder-anatomy.md`) is

```yaml
rings: [organisation, project, event]
depth: 1
```

e.g. `resources/by-organisation/<org title>/<key>`. The trees are disposable
symlinks into `items/`; `unclassified/` at the first layer holds resources
without the edge. `resource` is also a kind facet for every other domain, so
documents or projects may declare a `by-resource` ring of their own.

Retiring an over-promoted document into a resource is two explicit steps, not
a dedicated command:

```bash
ws add resource:<key> ~/workspace/documents/files/<file> --name <subpath>
ws delete document:<key>
```

`add` relocates the managed file into the bundle; `delete` then removes
the record and, automatically, every relation touching
it (any managed file still present goes to the Trash with it; `--dry-run`
previews). If the bundle-level fact matters ("expense-for ExampleCo"), assert it
once on the resource with `ws relate` — edges are never inferred.

## Object boundary

- A resource is an unstructured bundle whose contents need no independent
  addressability.
- A document is one file important enough to show, classify, and relate on
  its own.
- A project is structured ongoing work with workflows or deliverables.
- Literature is one bibliographic work.
- A profile object is a reusable CV fact or entry.

A resource child may later be promoted deliberately to a document, and a
document may be retired into a bundle (add the file, delete the record).
Neither direction is automatic or inferred from file type.
