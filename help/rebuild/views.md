# Rebuilding the browse views

```bash
ws rebuild views
ws rebuild views documents
```

Each domain has `by-*` folders to browse in a file manager. They hold
links to the canonical content, so an item appears in several places
without being copied. For example, `documents/by-type/report/` holds links
to every report, and nested views such as `by-project/` and `by-year/`, a
year in turn holding its `by-month/` refinement. Literature can be reached
through an author and then a year, or through a field and then one of its
subfields.

`ws rebuild views` rebuilds the folders of every domain; name one domain to
rebuild only its folders. Some changes refresh the folders at once and
others wait for this command (`ws help rebuild`).

## Rules

- Edit the record or content that `ws show REF` names, never a browse
  folder. Rebuilding wipes every `by-*` folder at a domain root and builds
  it again, writing nothing but links; records, relations and taxonomies
  are never touched.
- Organisation, project, event and other kind folders come from explicit
  relations, in either direction and of any relation word. Relate an object
  to make it appear there (`ws help relate`).
- `unclassified/` exists only at the first level beneath a domain root, for
  objects that lack the facet: no date, no edge, an empty classifier.
  Nothing nests beneath it. Deeper down, an object missing a facet stays in
  its value folder and simply does not descend further.
- A nested view that no object reaches is not created, so the folders on
  offer at each level reflect the data.
- An object with several values, such as several authors or fields, gets
  one link per value at every level. Beneath a field, only the subfields
  the taxonomy allows for that field appear.
- The same records and the same settings always give the same folders.

## The default shapes

```text
domain      browse by                                            depth
projects    type, organisation, event, status, field > subfield  2
documents   type, organisation, event, project, year > month     2
literature  author, field > subfield, year, project              2
profile     type, organisation                                   2
resources   organisation, project, event                         1
```

`ws init` writes these defaults into `folder-anatomy.yaml` at the
workspace root. That file is authoritative where it differs from them; a
domain missing from it, or a missing file, falls back to the default.

## Changing a shape

Edit `folder-anatomy.yaml` by hand. Keep `schema_version: 1`, which is
required, and the other domains' sections; a domain listed in the file is
complete, so exactly the rings it names are built.

```yaml
schema_version: 1

literature:
  rings: [author, field > subfield, year]
  depth: 1
```

`rings`
: The facets that become `by-*` folders. Each gets a tree at the domain
  root, and the set nests into itself: every value folder offers a `by-*`
  folder for each facet not yet used along its path.

`depth`
: How many independent facets nest along one path, 1 to 3; 2 when
  omitted.

`a > b`
: A refinement: `b` appears only beneath a value of `a`, and does not count
  towards the depth.

A facet is one of two things. A classifier of the domain's own records:
project `type`, `field`, `subfield` and `status`; document `type`, `year`
and `month`, from the document's date; literature `author`, `field`,
`subfield` and `year`, the authors and year from its citation; profile
`type`. Resources have no classifiers. Or a kind, whose folders are the
names of related objects: `person`, `organisation`, `event`, `task`,
`document`, `project`, `literature`, `profile` or `resource`.

`month` must sit beneath `year` and `subfield` beneath `field`; neither can
head a ring. A facet never repeats along one path. Where a name could mean
either a classifier or a kind, write `classifier:NAME` or `kind:NAME`.

For documents browsed mainly by project and date:

```yaml
documents:
  rings: [project, year > month]
  depth: 2
```

Check the file, then rebuild:

```bash
ws check anatomy
ws rebuild views
```

Validation comes before any folder is wiped: if the file has a mistake, the
rebuild stops and the previous folders stay as they were. Removing a facet
from the file removes its folder on the next rebuild. No canonical item
ever moves when a shape changes. Set `WS_FOLDER_ANATOMY` to keep the file
elsewhere (`ws help configuration`).
