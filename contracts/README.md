# Workspace contracts

Contracts define what implementations must preserve and how they may be
extended. Read them when changing ws, its schemas, adapters, validators or
generators. People and agents using ws share the manual, printed by `ws help`.

A contract contains canonical ownership, schema/identity rules, observable
guarantees, failure boundaries, and extension/compatibility requirements.
Small schema or boundary examples belong here. Setup sequences, command
walkthroughs and advice about which workflow to choose belong in the
manual (`help/`, printed by `ws help`).

## Find the governing contract

| Change | Contract | Manual |
|---|---|---|
| Installation, roots, scaffold | [Workspace](workspace.md) | [Getting started](../GETTING-STARTED.md), `ws help init`, `ws help configuration` |
| Command registration and discovery | [CLI](cli.md) | `ws help`, `ws capabilities` |
| Identity, lifecycle, adapters | [Objects](objects.md), [statuses](statuses.md) | `ws help show`, `ws help search` |
| Projects and environments | [Project](project.md) | `ws help projects`, `ws help create project`, `ws help projects install` |
| Literature | [Library](library.md) | `ws help literature` |
| Documents | [Documents](documents.md) | `ws help documents` |
| Resources | [Resources](resources.md) | `ws help resources` |
| Profile and CV output | [Career](career.md) | `ws help profile` |
| Tasks and contacts/events | [Tasks](tasks.md), [logistics](logistics.md) | `ws help tasks`, `ws help people` |
| Cross-domain edges | [Relations](relations.md) | `ws help relations` |
| Context notes and briefings | [Context](context.md) | `ws help context` |
| Folder views | [Folder anatomy](folder-anatomy.md) | `ws help rebuild views` |
| Derived index, wiki, dashboard, validation | [Rebuilding](workspace.md#derived-layers), [search](search.md), [wiki](wiki.md), [dashboard](dashboard.md), [check](check.md) | `ws help rebuild`, `ws help check` |

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
