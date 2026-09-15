# Relationships

Relationships are first-class records, not fields duplicated into both
endpoint objects. The canonical record physically lives in:

```text
~/workspace/relations/<relation-id>.yaml
```

An object YAML therefore keeps its own facts. Incoming and outgoing
relationships are joined when `show`, `search`, or `wiki build` runs.

This makes the graph symmetrical without conflicting copies, lets a relation
carry provenance and lifecycle data, and makes Obsidian/wiki output entirely
rebuildable. The generated endpoint notes contain direct wikilinks, so
relationships appear as edges in the Obsidian graph rather than as distracting
relationship-record nodes.
