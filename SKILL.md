---
name: ws
description: "Use ws to read, file and connect workspace knowledge. Discover records by search, then operate on their full references."
---

# Driving the ws CLI

The workspace defaults to `~/workspace`; `ws init` saves a different location
when requested. For first-time setup, follow [GETTING-STARTED.md](GETTING-STARTED.md).
Use `ws` to create, ingest and edit managed records. Read project content at
the paths returned by `ws show`, following the project's local instructions.

## Objects and REFs

Nine kinds of object: project, task, document, resource, literature,
person, organisation, event, profile. Every object has one canonical
reference of the form `<kind>:<key>` (a REF), e.g. `document:some-receipt`.

Any command acting on an existing object accepts only the full REF —
never a name, title, alias, internal id, bare key, or path. REFs come from
`ws search`. Paths are operands only where a command explicitly ingests a
file.

Most objects are defined by one YAML record; literature uses its item folder
and canonical BibTeX citation. Some objects are only a YAML
record (person, task, event); others own content: a document owns one
file, a resource owns a folder of arbitrary files, a project owns a
working folder, a literature item owns citation/PDF/source material.
`ws show <kind>:<key>` prints the record and the paths to any content —
that is how you find the raw material to read.

## Tools (act on objects)

```text
ws create KIND ...              mint something new: project, subproject,
                                task, resource, profile
ws add KIND ...                 ingest something that already exists:
                                person, organisation, event,
                                document (a file), literature (DOI/arXiv/ISBN)
ws add resource:<key> PATH      put a file into an existing resource bundle
ws show REF ...                 record + content locations (mix kinds freely)
ws edit REF --flag value        kind-specific flags; `ws edit REF --help`
ws delete REF ...               removes the object and every relation on it
ws list KIND [filters]          enumerate one kind; bare `ws list` counts all
ws search [KIND] WORDS          find objects; first word may scope by kind
```

You run without a terminal, so the interactive wizard never starts:
prompts are skipped, nothing hangs, and anything not supplied as a flag
stays empty. Pass everything relevant as flags; `ws <command> -h` lists
them. Flags always come last, after the command and its operands.

`ws add document FILE` MOVES the file into the workspace by default; use
`--mode copy` to leave the source in place.

Most read commands take `--json`; prefer it when you parse the output.

## Relations (the graph)

Conceptual connections are made explicitly after creation or ingestion:

```text
ws relate <kind>:<key> to <kind>:<key> as RELATION WORDS
ws unrelate <kind>:<key> to <kind>:<key> as RELATION WORDS   (or: the relation id)
ws show relations of <kind>:<key> [--as WORD]
```

Relation words are free-form kebab-case (`works-at`, `presented-at`).
Recording a project package install dependency also records its `depends-on`
edge; ordinary object creation has no conceptual-link prompts or flags.
Before inventing one, run `ws relations` — it lists every relation word
already in use; reuse one when it fits. Duplicate edges are no-ops. When
you instantiate a new object whose connection to existing objects is part
of the task, assert those edges immediately after creating it.

## Finding your way

```text
ws capabilities KIND     everything one can do with that kind,
                         specialists included (e.g. ws capabilities documents)
ws describe COMMAND      purpose, usage guide, contract and effects
ws <command> -h          how to type it: operands, flags, allowed values
ws <domain> taxonomy     classifier vocabulary (documents, literature,
                         projects, profile)
ws domains / ws relations             the vocabulary listings
```

## Retrieval recipe

1. `ws search [KIND] WORDS` — get REFs.
2. `ws show relations of REF` — fetch connected context if needed.
3. `ws show REF` — locate the object's content, then read the raw files.

For a workflow, read the relevant guide in the shared
[documentation index](docs/README.md), or follow the guide path from
`ws describe COMMAND`. People and agents use the same guides, including setup.
For judgement calls about object boundaries or relation words, read
[workspace values](agent/ws-values.md). Read [contracts](contracts/README.md)
when changing ws or checking an implementation guarantee. Resolve these links
relative to this file so they work wherever ws is installed.
