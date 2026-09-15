# Resources contract

Usage: [Bundling supporting files](../docs/resources.md).

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

## Ingestion boundary

Resource ingestion accepts a file or directory and moves it by default;
copy mode preserves the source. Only this explicit ingestion boundary accepts
filesystem paths as object content operands. Relationships remain attached
solely to the containing resource.

## Browse Views

Views derive their related-object facets from the canonical relation store.
Resources have no classifiers. Tree ownership, validation and rebuilding
follow [folder anatomy](folder-anatomy.md); child files never become
independent view objects.

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

## Extension and compatibility rules

- Additional bundle metadata must preserve the universal resource identity.
- New ingestion modes must state source/destination effects and preserve the
  distinction between moving content and creating object identities.
- Promoting a child to a document or retiring a document into a resource is an
  explicit operation. Edges must not be transferred or inferred silently.
- New file indexing may enrich resource discovery but must return the bundle
  once and must not mint child REFs.
- Changes to identity/storage require [a compatibility plan](README.md#changing-a-contract).
