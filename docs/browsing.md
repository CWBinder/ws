# Browsing the workspace

Browse the workspace's `by-*` folders in your file manager. They contain links
to canonical content, so an item can appear in several places without being
copied. These defaults are created by `ws init`; customisation is optional.

| Domain | Default ways to browse | Depth |
|---|---|---|
| Projects | Type, organisation, event, status, field → subfield | 2 |
| Documents | Type, organisation, event, project, year → month | 2 |
| Literature | Author, field → subfield, year, project | 2 |
| Profile | Type, organisation | 2 |
| Resources | Organisation, project, event | 1 |

Your local `folder-anatomy.yaml` is authoritative if it differs from these
defaults. Paths in this guide are relative to your configured workspace.

## Follow a view

For example, open `documents/by-type/report/`. It contains links to reports
and nested views such as `by-project/` and `by-year/`. A year can contain its
`by-month/` refinement. Literature can be reached through an author and then
a year, or through a field and then one of its subfields.

Organisation, project and event folders come from explicit relationships.
Use [Connecting and finding records](relationships.md) to add those links.
First-level `unclassified/` folders keep items with missing values visible;
deeper views omit them. Empty nested rings are omitted.

Edit the canonical record or content shown by `ws show REF`. Do not file
content directly into a generated `by-*` tree; rebuilding can replace it.

## Optional variations

Edit `folder-anatomy.yaml` in the workspace, preserving `schema_version: 1`
and the other domain sections. A domain's `rings` list selects its browsing
dimensions. `depth` controls how many independent dimensions nest (1–3).
An arrow written as `>` declares a refinement that does not consume depth.

For a shallow literature view, replace only its section with:

```yaml
literature:
  rings: [author, field > subfield, year]
  depth: 1
```

For documents primarily browsed by project and date:

```yaml
documents:
  rings: [project, year > month]
  depth: 2
```

Available classifiers are project type/field/subfield/status, document
type/year/month, literature author/field/subfield/year and profile type.
Resources have no classifiers. Any domain can also browse by a related object
kind: person, organisation, event, task, document, project, literature, profile
or resource. Those views include connections in either direction, of any type.
If a facet name is ambiguous, use `classifier:NAME` or `kind:NAME` explicitly.
Month must be beneath year; subfield must be beneath field.

## Apply and check a change

```bash
ws check anatomy
ws documents views rebuild
ws literature views rebuild
```

Rebuild each domain you changed; projects, profile and resources have the same
`views rebuild` command. Ordinary document ingestion/edits and relation changes
also refresh relevant views. No canonical items move when the view shape changes.

For a graph and generated Markdown notes, see [Wiki](visualization.md).
Maintaining the view engine: [folder anatomy contract](../contracts/folder-anatomy.md).
