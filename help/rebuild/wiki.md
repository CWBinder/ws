# Rebuilding the wiki

```bash
ws rebuild wiki
```

The wiki is a browsable Markdown view of the workspace: one note per
object, index notes, and `[[wikilinks]]` for the relations between them.
Obsidian draws its graph from those links, but the notes are ordinary
Markdown that any text editor reads. ws does not install Obsidian.

To browse it in Obsidian, open the `wiki/` folder of the workspace as a
vault and start from `generated/Workspace.md`. Files outside the vault,
such as a project's README or a document's file, are linked as `file://`
links and open in the system's own viewer. Obsidian's local graph gives the
view of one project; there are no separate vaults.

## A view, never a source

Every note is generated from the records and relations, and the wiki is
never read back. A rebuild deletes `wiki/generated/` and writes it again,
so deleting it loses nothing, and each note carries a banner and
`generated: true` in its frontmatter. Never edit a generated note: change
the record with ws, then rebuild. Hand-written notes may live elsewhere in
`wiki/`, outside `generated/`.

The wiki is a snapshot; rebuild it after changes you want to see there. A
workspace kept in git ignores `wiki/generated/`. An `.obsidian/` settings
folder is optional; if tracked at all, keep it minimal and keep personal
settings local.

## What it holds

```text
wiki/generated/
  Workspace.md                     the home note, linking the index notes
  Connections.md                   related projects, project literature,
                                   and every relation in the workspace
  Projects.md  Literature.md       one table each, with status, type and
                                   fields, or authors, year and fields
  Fields.md                        every field, with its number of projects
  Profile.md                       the profile hub
  People.md  Organisations.md  Events.md  Tasks.md  Documents.md
  Resources.md                     one index note per kind
  projects/<name>.md               one note per project
  literature/literature-<key>.md   one note per literature item
  fields/field-<field>.md          one hub note per field
  profile/profile.md               the public professional profile
  profile/skills.md                skills
  people/  organisations/  events/  tasks/  documents/  resources/
                                   one note per object, named
                                   <kind>-<key>.md
```

A project note shows its title, type, status, fields, subfields and
keywords, its relations, its purpose from `.context/purpose.md` (or the
README's `Purpose` section in a project not yet migrated), and the
`Current State` and `Next Steps` sections of its README, copied in at build
time. It links
to the README, `AGENTS.md` and `project.yaml` rather than copying the
instructions. A literature note shows title, authors, year and DOI, its
keywords, fields and summary, the projects that list it, its relations,
and links to the item's files.

The profile notes are filtered for privacy. They show the professional
name, headline and description, the number of items of each CV section,
the skills, and the publications. They leave out contact details, date of
birth, address, provenance and application contents.

Each relation becomes a direct wikilink between its two endpoints, listed
under "Workspace relationships" with its relation word; a relation never
becomes a note of its own. The older project lists `depends_on`, `related`
and `related_literature` still show as their own sections.

## Grouping in the graph

Obsidian's graph draws every link alike. To colour and cluster nodes, make
graph groups on the tags each note carries: `kind/...`, `field/...`,
`subfield/...` and `status/...`. A field note links every project in that
field, so each field forms a visible cluster. Project keywords show in the
note as text, not as tags.

Set `WS_WIKI_DIR` to keep the wiki folder elsewhere
(`ws help configuration`).
