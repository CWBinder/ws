# Objects and Relationships Contract

Usage: `ws help relations` and `ws help relate`.

Relations is its own layer, not a domain and not a service. It is not a
domain because an edge joins objects of any kinds and belongs to none; the
universal tools address it by its own REF, `relation:<id>` (see Addressing
an edge), but it is never searched or listed as an object. It is not a
service because a service owns nothing canonical, while an edge is asserted
by hand, exists nowhere else, and cannot be regenerated from any other
store. Bare
`ws relations` lists the relation vocabulary in use: each word, its edge
count, and the kinds it connects, subject first (`person → organisation`),
so a new edge can reuse a word the right way round. The vocabulary is open,
so that listing is read back from the edges themselves rather than from a
fixed list.

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
configuration (`ws help configuration`).

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

Names, aliases, paths, and internal IDs are not accepted as endpoints; use
`ws search <query>` to discover each REF.

## Addressing an edge

An edge's REF is `relation:<id>`: its record id without the `rel_` storage
prefix, so `relation:01KYTNTBD9T7K071PSJ568ZDZ8` names
`relations/rel_01KYTNTBD9T7K071PSJ568ZDZ8.yaml`. `ws relate` prints it, and
`ws show REF` lists every edge touching an object by it, so the REF is at
hand without a lookup command.

- `ws show REF` prints the object, then `relations:` with one line per edge:
  the edge's REF, `--words-->` for an edge leaving the object or
  `<--words--` for one arriving, and the other endpoint with its name.
  `--as WORD` narrows the list; `--json` carries it as `relations`.
- `ws show relation:<id>` prints the edge in full: subject, words, object,
  validity, source and provenance history.
- `ws edit relation:<id>` changes the words (`--as`) and validity dates
  (`--from`, `--until`), recording provenance (`--source`, `--observed-at`).
- `ws delete relation:<id>` removes the edge and prints the `ws relate`
  command that restores it; `--dry-run` previews.

Edges are found through their endpoints: a relation REF is never a search
hit or a `ws list` kind. The key accepts only an id's characters. The bare
storage id (`rel_...`) also resolves, for output printed before relation
REFs existed.

The older spellings still run and name the current one on stderr:
`ws show relations of REF` (the relations list alone), `ws unrelate` (by REF
or by the sentence `A to B as WORDS`) and `ws relations edit RELATION_ID`.
They are compatibility spellings, listed only by `ws capabilities --all`.

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
`ws show REF` and `ws rebuild wiki` assemble incoming and outgoing
relationships at read time.

A relation is directional. It reads “SUBJECT relates to OBJECT as RELATION.” Repeating an
identical relationship is idempotent. `ws delete relation:<id>` deletes the
record and prints the exact `ws relate` command that would restore it (the
store is not under git, so the hint is the undo path).

## Index and wiki

`ws rebuild index` produces a derived SQLite index at `index/index.sqlite` by
default. It is never authoritative.

`ws rebuild wiki` renders direct Obsidian wikilinks between object notes. Raw
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
