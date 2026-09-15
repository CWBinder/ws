# Command reference

The complete live reference is generated from the parser:

```bash
ws domains
ws relations
ws capabilities
ws capabilities --json
ws capabilities documents
ws capabilities maintenance
ws help create project
ws describe add document
```

Bare `ws capabilities` groups every command under the four categories of
global commands — objects, search, maintenance, discovery —
and then each domain's specialists. A kind word or a category word scopes
the listing.

Canonical entity-entry commands — `create` mints, `add` ingests, the kind
is the first word:

```text
ws create project
ws create task
ws create resource
ws create profile
ws add document
ws add person
ws add organisation
ws add event
ws add literature
ws documents types list|add|rename|remove
```

Each command has exactly one spelling. The domain words host only their own
specialists (taxonomy, views, installs, merges); the generic verbs live at
the top level and nowhere else.

Do not maintain a second hand-written exhaustive command list here. The
executable registry is authoritative.

## From syntax to a workflow

`ws --help` prints the installed getting-started and documentation paths.
`ws describe COMMAND` prints its usage guide, purpose, governing contract and
declared effects. Use the guide to carry out the task; consult the contract
when extending the implementation or checking a guarantee. The additive
`guide` field in discovery JSON is relative to the installed ws documentation
root, as is the existing `contract` field.

Flags follow the command path and all operands. For example:

```bash
ws search documents report --json
ws show document:<key> --json
```

Replace `<key>` with a search result. For tasks and contacts, start with
`ws help create task`, `ws help add person`, `ws help add organisation` or
`ws help add event`; connect the resulting records using the
[relationship guide](../relationships.md).
