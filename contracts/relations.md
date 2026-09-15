# Objects and Relationships Contract

Usage: [Connecting and finding records](../docs/relationships.md).

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

The configured workspace root determines these default locations.
Individual domains also have environment overrides; see
[configuration](../docs/reference/configuration.md).

Override only the relationship store with `WS_RELATIONS_DIR`. Legacy records from `documents/Workspace/relations/` require explicit migration
into this store; readers must not establish a second canonical edge store.

The catalog indexes each canonical domain store through adapters instead of
copying objects into a central metadata folder.

## Relate grammar

Edges come into being exclusively through `ws relate` — no create or add
command takes relation flags, and no creation wizard asks for endpoints.
The one derived exception: a project `--use-project` install dependency
records its own depends-on edge.

Relation types are free-form kebab-case; `ws relate` lowercases and hyphenates
whatever follows `as` (or `--as`). Both endpoints must be canonical REFs.

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

A relation is directional. It reads “SUBJECT relates to OBJECT as RELATION.” Repeating an
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

## Integrity and extension

Checks report problems without repairing or deleting data. Both endpoints
must resolve; object deletion must remove incident edges as specified by the
object contract.

- New relation words extend the open vocabulary without a schema change.
- New edge attributes must not duplicate endpoint facts or introduce a
  lifecycle status; validity dates remain distinct from existence.
- New domain adapters resolve canonical objects in place. They must preserve
  public REFs and internal-ID storage where available.
- Identity or edge-format changes require [a compatibility/migration plan](README.md#changing-a-contract).
  Preserve idempotent assertion, directional semantics, merge redirects and
  restore information on removal; verify these boundaries when changing them.
