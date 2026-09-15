# Visualization and Wiki

Use this guide to generate a browsable Markdown view of workspace records and
their connections. For file-manager views, see [Browsing](browsing.md).

## Build and open

```bash
ws wiki build
```

Open your configured workspace folder as a vault in Obsidian if you use it,
then open `wiki/generated/Workspace.md`. The generated files are ordinary
Markdown and can also be read in a text editor. ws does not install Obsidian.
Use its graph or local graph to follow the generated links.

Rebuild after changing canonical records. Keep hand-written notes outside
`wiki/generated/`: rebuilding replaces that directory's contents. Paths below
show the default `~/workspace`; substitute your configured root if different.

## Model

- **Canonical source of truth:** project YAML, literature item records, the career profile, registered workspace object YAML, relationship YAML, and project README files.
- **Generated view:** Markdown notes that Obsidian renders. These are a *view*, never a second source of truth. They are regenerated from the canonical YAML and may be deleted and rebuilt at any time.
- **Optional viewer:** Obsidian draws a graph from `[[wikilinks]]`; it is a separate installation.

## Current output

- ws generates Markdown with Obsidian-style wikilinks. It does not currently generate a static HTML graph.
- **Single workspace vault.** One vault rooted at `~/workspace`. Per-project views come from Obsidian's local-graph view, not separate vaults.

## Vault layout

- Vault root: `~/workspace`.
- Wiki hub: `~/workspace/wiki/`.
- Generated layer: `~/workspace/wiki/generated/` — **regenerable at any time**.
- Hand-written knowledge notes may live alongside under `wiki/`.

```text
wiki/
  generated/                  # gitignored, produced by `ws wiki build`
    Workspace.md              # home map-of-content (MOC)
    Connections.md            # cross-project/literature links
    Projects.md               # index MOC of all projects
    Literature.md             # literature index
    Profile.md                # privacy-filtered profile hub
    Fields.md                 # index MOC of all fields
    projects/<name>.md        # one node-note per project
    literature/literature-<key>.md       # one node-note per canonical literature item
    profile/profile.md        # public professional profile and CV section summary
    profile/skills.md         # skills and research interests
    fields/<field>.md         # one hub note per field
    people/<id>.md            # generated logistics person view
    organisations/<id>.md     # generated organisation view
    events/<id>.md            # generated event view
    tasks/<id>.md             # generated task view
    documents/<id>.md         # generated document metadata view
```

## Node-note conventions

Each generated note carries YAML frontmatter (for tags/grouping) and `[[wikilinks]]` (for edges).

- **Project node** (`projects/<name>.md`): frontmatter `type`, `status`, tags `[type/project, field/<field>, status/<status>]`; displays metadata and connections; embeds the maintained `Purpose`, `Current State`, and `Next Steps` sections from the real project README; links to project instructions rather than copying them.
- **Literature node** (`literature/literature-<key>.md`): title, author, year, DOI, reading context, project backlinks, and links to the canonical literature item.
- **Profile views**: generated from canonical profile objects and literature items explicitly related from publication objects. They expose the professional headline and description, skill objects, type counts, and publications. They deliberately omit contact details, date of birth, address, provenance, and application contents.
- **Field note** (`fields/<field>.md`): hub tagged `type/field`; every project in that field links here, so the field forms a visible cluster.

## Edge and node conventions

- `depends_on` → **directed** edge ("A needs B").
- `related` → **symmetric** edge ("see also").
- `related_literature` → project-to-literature edge using canonical literature ItemKeys.
- `relations/*.yaml` → typed cross-domain edges. These
  records are rendered as direct endpoint wikilinks; relationship records do
  not become graph nodes.
- Obsidian's core graph draws all edges identically; the directed/symmetric distinction lives in frontmatter. The optional **Juggl** plugin can render typed/colored edges later.
- Node coloring/clustering uses Obsidian graph **groups** keyed on tags (`type/*`, `field/*`, `status/*`). Project `keywords` are displayed as readable metadata, not graph-group tags.

## Regeneration

- `ws wiki build` regenerates the `generated/` layer from canonical YAML. It is idempotent — safe to delete `generated/` and rebuild.
- Generated files carry a header marker noting they are generated; never hand-edit them.

## Git and Obsidian config

- `generated/` is gitignored (fully regenerable).
- `.obsidian/` is optional. If tracked at all, keep it minimal and stable; personal/volatile settings stay local.

## Implementation reference

 `ws wiki build` generates the `generated/` layer (project, literature, career, and field node-notes plus the index MOCs) from canonical YAML. It clears and rebuilds `generated/` on each run. Maintainers should read the [wiki contract](../contracts/wiki.md) and the
[profile privacy rules](../contracts/career.md#privacy-and-git). The
[earlier wiki plan](projects-wiki-plan.md) records design history.
