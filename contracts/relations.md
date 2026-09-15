# Objects and Relationships Contract

Relations is its own layer, not a domain and not a service. It is not a
domain because an edge carries an id rather than a REF, belongs to no kind,
and is never shown or listed as an object. It is not a service because a
service owns nothing canonical, while an edge is asserted by hand, exists
nowhere else, and cannot be regenerated from any other store. Bare
`ws relations` lists the relation vocabulary in use with per-word edge
counts; the vocabulary is open, so that listing is read back from the edges
themselves rather than from a fixed list.

This contract defines the shared object graph used by `ws`.

## Canonical domain roots

Each object belongs to its domain store:

```text
~/workspace/
  projects/
  tasks/
  literature/items/
  documents/items/
  resources/items/
  logistics/
    people/
    organisations/
    events/
    communications/
  profile/items/
```

Canonical cross-domain edges have their own workspace-root store:

```text
~/workspace/relations/
  rel_01K....yaml
```

Override the root with `WS_DATA_DIR`. Individual domain directories also have
`WS_*_DIR` overrides; see `ws_lib/paths.py`.

Override only the relationship store with `WS_RELATIONS_DIR`. Migrate records
from the former `documents/Workspace/relations/` location with
hand, into the canonical relations store.

The catalog indexes each canonical domain store through adapters instead of
copying objects into a central metadata folder.

## Relate grammar

Edges come into being exclusively through `ws relate` — no create or add
command takes relation flags, and no creation wizard asks for endpoints.
The one derived exception: a project `--use-project` install dependency
records its own depends-on edge.

Relation types are free-form kebab-case; `ws relate` lowercases and hyphenates
whatever follows `as` (or `--as`). Both endpoints must be canonical REFs:

```bash
ws relate person:maria-schwarz to organisation:example-institute as works at
ws relate person:maria-schwarz organisation:example-institute --as works-at
```

`ws unrelate` accepts the same endpoint grammar. Names, aliases, paths, and
internal IDs are not accepted; use `ws search <query>` to discover each REF.

## Object records

People, organisations, events, tasks, registered documents, resources, and profile
entries use one YAML file per object. Required keys:

```yaml
schema_version: 1
id: person_01K...
key: maria-schwarz
kind: person
name: Maria Schwarz
aliases: []
created_at: 2026-07-30T12:00:00+02:00
updated_at: 2026-07-30T12:00:00+02:00
```

Objects may carry an optional lifecycle `status` (absent means active; see
`objects.md`). Internal IDs and public keys never change. The canonical
filename is `<key>.yaml`. A merge retains the duplicate record as a redirect.
Relationship records store internal IDs where available, while CLI input and
public output use REFs.

Project references use `project:<workspace-relative-project-path>`. Literature
references use `literature:<ItemKey>`. These preserve their existing canonical
identifiers.

## Relationship records

Relationships are workspace-owned and stored once:

```yaml
schema_version: 1
id: rel_01K...
subject: doc_01K...
object: project:shuttling
relation: deliverable
valid_from: ""
valid_until: ""
source: ""
observed_at: ""
created_at: 2026-07-30T12:00:00+02:00
updated_at: 2026-07-30T12:00:00+02:00
```

**Relations are stateless assertions**: a record exists or it does not, and
every record that exists counts. There is no lifecycle status. The temporal
axis is separate: `valid_from`/`valid_until` bound a relationship that is
true about a window of time — an ended relationship is still a true relation.
A wrong or unwanted relationship is deleted.

Do not duplicate a relationship into both endpoint object files.
`ws show relations of REF`, `ws show relations of`, and `ws wiki build`
assemble incoming and outgoing relationships at read time.

The command:

```bash
ws relate SUBJECT_REF OBJECT_REF --as RELATION
```

is directional. It reads “SUBJECT relates to OBJECT as RELATION.” Repeating an
identical relationship is idempotent. `ws unrelate` deletes the record and
prints the exact `ws relate` command that would restore it (the store is not
under git, so the hint is the undo path).

## Index and wiki

`ws index rebuild` produces a derived SQLite index at `index/index.sqlite` by
default. It is never authoritative.

`ws wiki build` renders direct Obsidian wikilinks between object notes. Raw
relationship records do not become Obsidian graph nodes. A canonical edge may
be rendered in both endpoint notes because the generated Markdown is
rebuildable.

## Integrity

Use:

```bash
ws check
ws check projects
ws check catalog
ws check logistics
ws check relations
ws check index
```

Checks never repair or delete data.
