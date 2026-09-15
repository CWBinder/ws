# Workspace contracts

Contracts define what implementations must preserve and how they may be
extended. Read them when changing ws, its schemas, adapters, validators or
generators. People and agents using ws share the [usage documentation](../docs/README.md).

A contract contains canonical ownership, schema/identity rules, observable
guarantees, failure boundaries, and extension/compatibility requirements.
Small schema or boundary examples belong here. Setup sequences, command
walkthroughs and advice about which workflow to choose belong in docs.

## Find the governing contract

| Change | Contract | Usage or explanation |
|---|---|---|
| Installation, roots, scaffold | [Workspace](workspace.md) | [Getting started](../GETTING-STARTED.md), [configuration](../docs/reference/configuration.md) |
| Command registration and discovery | [CLI](cli.md) | [Command reference](../docs/reference/commands.md) |
| Identity, lifecycle, adapters | [Objects](objects.md), [statuses](statuses.md) | [Connecting and finding](../docs/relationships.md) |
| Projects and environments | [Project](project.md) | [Project setup](../docs/project-setup.md), [capabilities](../docs/project-install.md) |
| Literature | [Library](library.md) | [Literature guide](../docs/literature.md) |
| Documents | [Documents](documents.md) | [Filing documents](../docs/documents.md) |
| Resources | [Resources](resources.md) | [Bundles](../docs/resources.md) |
| Profile and CV output | [Career](career.md) | [Profile and CVs](../docs/profile.md) |
| Tasks and contacts/events | [Tasks](tasks.md), [logistics](logistics.md) | [Command reference](../docs/reference/commands.md) |
| Cross-domain edges | [Relations](relations.md) | [Connecting records](../docs/relationships.md) |
| Folder views | [Folder anatomy](folder-anatomy.md) | [Browsing](../docs/browsing.md) |
| Derived index, wiki, validation | [Search](search.md), [wiki](wiki.md), [check](check.md) | [Command reference](../docs/reference/commands.md), [wiki guide](../docs/visualization.md) |

`projects.md`, `literature.md` and `profile.md` are namespace entry points
that link to the detailed contracts above. They do not define another schema.
Roster and inbox have independent repositories and contracts.

## Shared invariants

- Each durable fact has one canonical owner. Generated compatibility files,
  indexes and views may copy it only when they remain rebuildable.
- Keep structured state in the domain's declared format, and instructions or
  notes in Markdown. Literature citation truth remains BibTeX.
- Personal settings, records and credentials belong outside the shared source.
- Templates in [templates/](../templates/) must agree with their contract and
  the code that generates records from them.
- Optional extensions must not make previously valid records invalid merely
  because a new field is absent.

## Changing a contract

1. Identify the canonical owner and the guarantee the change affects. Read
   the domain contract and relevant shared contracts before implementation.
2. Prefer additive optional fields, taxonomy values and adapters that preserve
   existing identity and semantics. State defaults for missing new fields.
3. For changed keys, identity, storage paths, required fields or command
   semantics, document compatibility and migration explicitly: what old data
   remains readable, how it converts, what happens on failure, and how users
   recover. Update schema versions when the format changes incompatibly.
   Editing a contract alone does not migrate existing user data.
4. Update the implementation, templates, validators, command effects/help and
   relevant usage guide together. Keep command syntax generated from the
   parser; docs show selected workflows rather than another exhaustive list.
5. Verify the affected guarantees with appropriate tests, especially old-data
   reads, rejected writes, identity preservation and canonical/derived boundaries.
   Record any deliberate compatibility break in the user-facing change notes.

These are contributor requirements. A user's supported changes to taxonomy,
profile facts or browse settings do not require editing the shared contracts.
