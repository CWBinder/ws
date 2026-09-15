# Command reference

The complete live reference is generated from the parser:

```bash
ws domains
ws relations
ws capabilities
ws capabilities --json
ws capabilities documents
ws capabilities maintenance
ws help projects create
ws describe documents add
```

Bare `ws capabilities` groups every command under the five categories of
global commands — objects, search, maintenance, connectors, discovery —
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
