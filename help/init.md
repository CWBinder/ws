# Initialising a workspace

```bash
ws init
ws init --root ~/my-workspace
```

Init creates the empty workspace, by default at `~/workspace`, and saves
its location in `~/.config/ws/config.yaml` so that every later command
finds it. It then runs a full `ws check` and points to `ws setup`, which guides
you through the first objects (`ws help setup`).

Init imports no files, signs in to no service, creates no profile records
and creates no git repository. It is safe to repeat: a second run creates
only what is missing, and keeps personal files, taxonomies and browse
settings as they are.

## What it creates

```text
projects/items/                       projects
tasks/                                tasks
documents/items/  documents/files/    document records, and the files ws
                                      keeps
resources/items/                      resource bundles
literature/items/                     literature
logistics/people/  organisations/  events/  communications/
                                      people, organisations, events
profile/items/  profile/applications/
                                      profile records and applications
relations/                            the edges between objects
index/                                the search index, built if absent
wiki/generated/                       the generated wiki
projects/project-taxonomy.yaml        default classifications, one file
documents/document-taxonomy.yaml      per kind that has them
profile/profile-taxonomy.yaml
folder-anatomy.yaml                   default browse settings
README.md  AGENTS.md                  orientation for people and agents
```

The folders start empty and are real folders, never links to existing
content elsewhere: material outside the workspace stays where it is until
you add it on purpose. The browse folders, the wiki notes and the dashboard
appear later, when they are first built (`ws help rebuild`). Do not create
further top-level folders.

`AGENTS.md` names the workspace for agents and has a section for your own
working conventions; write durable personal facts into records instead and
refer to them. `README.md` describes the layout for people.

## Choosing the location

`--root DIR` chooses the directory for this run, and init saves it as the
default for later commands. `WS_WORKSPACE_ROOT` still overrides the saved
root, and so do the variables that move single stores
(`ws help configuration`).

Choosing another root switches the default; it never moves existing
content. Init refuses your home folder, `/` and `/workspace` as roots, and
refuses a workspace inside the ws checkout: the software and your content
live apart.

## When init refuses

Init checks the layout before creating anything. A file where a folder
belongs, or a symlink in place of a required folder or file, stops it with
an error naming the path. Inspect that path before changing anything.
Inconsistencies that already exist are reported by the final check, not
repaired.

An agent helping with setup first checks whether ws and the intended
workspace already exist and reuses them when appropriate, asks for any
location it does not know, and never infers personal facts, imports
unrelated files or replaces existing settings.
