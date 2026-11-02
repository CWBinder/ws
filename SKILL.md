---
name: ws
description: "Use for anything that creates, adds, edits, moves, relates or deletes something in the workspace (~/workspace), the person's second brain of projects, tasks, documents, resources, literature, people, organisations, events and profile; and for finding what is already there and how it connects. Load it before running any ws command and before answering what ws can do. Every change to the workspace goes through ws, never by editing or moving its files by hand."
---

# ws: the workspace and its tool

The workspace (`~/workspace` by default) is the person's second brain:
projects, tasks, documents, papers, contacts, events and career facts kept
as records, with explicit relations between them. `ws` is the tool that
keeps it. People and agents use the same commands and read the same
manual.

**The manual is `ws help`.** Bare, it gives the overview and a map of
every command; `ws help <kind>` and `ws help <command>` give one page in
full. This skill holds only what you need before your first command.

## Rules

- **Every change goes through ws.** Creating, adding, editing, relating,
  moving and deleting are ws commands, never hand edits to store files.
  The one exception is a project's working content (code, data, paper,
  slides), which you work on normally, following the project's own
  instructions.
- **Search before creating.** A duplicate is worse than a gap. Reading is
  free: search, show, and read the files at the paths ws prints.
- **Content enters deliberately.** Material elsewhere stays outside until a
  ws command brings it in; never symlink it in. Add or change things when
  the request asks for that outcome; otherwise propose the command.
- **Generated layers are read-only.** The `by-*` folders, `index/`, `wiki/`
  and `dashboard.html` are rebuilt by `ws rebuild`; never edit them.
- **Asked to remember something?** It goes into the workspace, never into
  notes of your own: a fact about someone, the person themselves included,
  on their person record. `ws help values` lists where each kind goes.
- **Judgement calls**, such as what deserves to be an object, which
  relation words to use and when to delete, are in `ws help values`.

## Objects and relations

Nine kinds: project, task, document, resource, literature, person,
organisation, event, profile. Every object has one REF, `<kind>:<key>`,
such as `project:thesis`. Commands that act on an existing object accept
only the full REF, never a name, title or path; REFs come from
`ws search` or from the command that made the object.

Relations are directed edges with kebab-case words
(`person:<key> --works-at--> organisation:<key>`). Nothing is related
automatically: relate a new object right after making it when the task
calls for it. Run `ws relations` first and reuse a word that fits, the
same way round.

## Core commands

```text
ws search [KIND] WORDS          find objects and get their REFs
ws show REF ...                 record, content paths, every relation
ws context [REF]                briefing: purpose, log, house rules
ws list KINDS [filters]         every object of one kind, e.g. ws list tasks --open
ws create KIND ...              mint: project, subproject, task, resource, profile
ws add KIND ...                 ingest: person, organisation, event,
                                document (a file), literature (DOI/arXiv/ISBN)
ws add resource:<key> PATH      put a file into an existing bundle
ws edit REF --flag value        change a record
ws relate REF to REF as WORDS   connect two objects
ws delete REF ...               remove an object and its relations
```

To answer a question about the workspace: `ws search` for the REF,
`ws show` for the record and its relations, follow a relation with another
`ws show`, then read the raw files at the paths it printed. A session that
starts inside the workspace runs `ws context` first when no WORKSPACE
BRIEFING is in context.

## Running commands as an agent

- Without a terminal nothing is asked, so pass everything as flags; flags
  always come last. `ws <command> -h` lists them.
- `ws add document` moves the file by default; `--mode copy` leaves it.
- Sign assertions with `--source` and `--observed-at` when you know them.
- Most read commands take `--json`; prefer it when you parse output.
- `ws capabilities KIND` lists every command for a kind, specialists
  included; `ws describe COMMAND` says what it reads and writes.

## Deeper skills

Two domains have their own skill, shipped under [skills/](skills/). Load
the one you need and keep this one loaded:

- **literature** ([skills/literature](skills/literature/SKILL.md)): adding
  a paper with PDF, TeX source and links; reading, quoting or summarising
  one; finding papers; following citations.
- **cv** ([skills/cv](skills/cv/SKILL.md)): making or updating a CV, or
  adding a publication, talk or other career fact to the profile.

Setup is in [GETTING-STARTED.md](GETTING-STARTED.md). When changing ws
itself, start with [AGENTS.md](AGENTS.md) and the
[contracts](contracts/README.md).
