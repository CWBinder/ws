# Object Contract

Every first-class object has one canonical public reference:

```text
REF = <kind>:<key>
```

An object exists to be pointed at. A thing earns a REF exactly when something
else must reference it — as a command operand, an edge endpoint, or a search
result. What nothing needs to point at is not an object: taxonomies,
templates, agent roles, and derived views are workspace data or tooling
configuration, addressed by plain names and paths.

The REF is the only value accepted by commands that act on an existing
object. Names, aliases, titles, DOI/arXiv identifiers, and internal IDs are
search inputs, never action operands. The normal workflow is:

```bash
ws search "Example Company"
ws show organisation:example-company
ws relate person:maria-schwarz organisation:example-institute --as works-at
```

All kinds expose this core:

```text
ref          public identity: kind:key; stable and unique
key          stable human-readable key, unique within kind
id           internal immutable ID; may be a ULID; never typed into the CLI
kind         which kind of object this is: person, organisation, event,
             task, document, project, literature, profile, resource
name         human-readable display name; searchable, not an operand
type         the standard classifier within the kind (college, invoice,
             research, fair, …); may be empty
aliases      alternative search terms; may be empty
description  one or two sentences of prose; searched, never grouped by
```

Search examines names, aliases, keys, identifiers, and domain metadata, and
always returns canonical REFs. Resolution for an action is deliberately
strict: it accepts exactly a full REF of the expected kind. A display-name
edit never changes the key or REF.

## Optional per kind

Beyond the core, a kind may define more — nothing else is universal:

- `status` — lifecycle classifier, written only when set; **absent means
  active**. `merged` marks tombstones that redirect to a canonical record.
  Kind-specific vocabularies (e.g. project statuses) live in
  `contracts/statuses.md`.
- further classifiers — e.g. project `fields` and `subfields`.
- facts — kind-specific truths: `emails`/`phones`/`preferred_name` (person),
  `website` (organisation), `start`/`end`/`timezone`/`location` (event),
  `due`/`priority` (task), `path`/`path_root`/`classification` (document).
- bookkeeping — `schema_version`, `created_at`, `updated_at`, and
  `provenance` entries recording which source asserted which fields, when
  (`--source`, `--observed-at`).

## Acting on objects

A tool whose operand is a full REF needs no domain prefix: the REF names
its kind. `ws show`, `ws edit`, `ws delete`, `ws relate`, and `ws unrelate`
are top-level tools. Show renders any REF — adapters like `project:` and
`literature:` included — and takes several at once, mixing kinds. Edges
are shown through the same tool in sentence form:
`ws show relations of <kind>:<key>` (the `of` is optional filler, like
relate's `to`), narrowed by `--as <relation>`. Edit
reads the kind from the REF and then accepts exactly that kind's flags
(`ws edit document:<key> --help` lists them). A tool that acts on a kind
rather than an object takes the kind as its first word instead:
`ws list documents --type contract`, `ws search documents contract`,
`ws create task <title>`, `ws add document <file>` — each kind keeps its
own flags there. Creation splits by tool, not by position: `create` mints
what did not exist (task, resource, project, profile item), `add` ingests
what already does (a person, a file, a paper). Dropping the kind widens
the scope where that means something: bare `ws list` counts every kind,
bare `ws search <words>` searches everything.

Each of these commands has exactly one spelling. The domains keep no
generic tools of their own: what remains under a domain word is only what
exists for that kind alone — taxonomy machinery, view rebuilds, and folder
specialists (`ws literature enrich`, `ws documents types add`,
`ws projects install`, `ws logistics people merge`, `ws profile make-cv`).
The hand-curated kinds keep their
limits: show renders every REF, but neither projects nor literature can be
deleted, and a project has no edit at all — `ws edit literature:<key>`
carries exactly literature's own classifier flags.

## Removing objects

`ws delete REF...` removes records outright, and with them every relation
touching them — edges never dangle; one call may mix kinds. Deletion means
deletion, and safety comes from recoverability, not friction: a document's
managed file and a resource's whole folder are moved to the Trash rather
than destroyed; `--dry-run` previews. `merge` is the different speech act:
it says "duplicate" — identity redirects to the canonical record and a
`merged` tombstone remains — where delete says "should not exist". Projects
and literature have no delete: a project retires through its lifecycle
status, a literature item by hand.

## Adapters

Minted records live as `<key>.yaml` under their domain store
(`logistics/people/`, `documents/items/`, `profile/items/`, …) and are written
only by `ws`. Their YAML contains both `key` and the internal `id`.
Adapter kinds project native storage instead: a project's core maps from
`project.yaml` (its title is the name and folder slug is the key), a
literature item's from its BibTeX (ItemKey is the key and title is the name).
Subprojects are projects in identity (`project:<parent>/<path>`,
declared by `subproject.yaml`).

The key-to-storage rule is uniform even though storage shapes differ:

| Kind | Key on disk | Example REF |
|---|---|---|
| project | project folder name | `project:virtuallab` |
| literature | item folder/BibTeX key | `literature:Turner2025ModellingImpactDevice` |
| person, organisation, event, task, document, profile | YAML filename stem | `person:maria-schwarz` |
| resource | resource folder name | `resource:exampleco-travel-reimbursements` |

Resources use the deliberate folder-backed exception
`resources/items/<key>/resource.yaml`: the folder is the object and its child
files are not objects.

Thus the key is normally visible in the canonical filename or folder name,
but the terminal operand is always the full REF, including its kind prefix.

## Where the model is defined

```text
contracts/objects.md      this contract — the universal core
contracts/<kind>.md       per-kind facts, classifiers, commands
contracts/relations.md    edges between objects
contracts/statuses.md     lifecycle vocabularies
projects/project-taxonomy.yaml     allowed project type values; the shared fields vocabulary (workspace data)
documents/document-taxonomy.yaml   allowed document type values (workspace data)
profile/profile-taxonomy.yaml      allowed profile types and CV order (workspace data)
```

Taxonomy files key by the classifier name itself (`type`, `fields`, `subfields`), and every
taxonomy-bearing domain exposes the same interface, implemented by one engine
(`ws_lib/taxonomy.py`):

```text
<domain>.load_taxonomy()               -> flat lists and, where needed, parent -> child lists
<domain>.add_taxonomy_value(key, val)  -> slug, dedupe, append, write
```

Keys per domain — projects: `type`, `fields`, `subfields`; literature:
`fields` and `subfields` (the same shared values); documents: `type`; profile:
`type`. Most classifier keys contain flat lists. The project taxonomy's
`subfields` key is the controlled two-level exception: it maps each broad
field to its allowed subfield list. Statuses
are not taxonomies: lifecycle vocabularies are fixed in `statuses.md` and
never extendable from the CLI. Kinds without classifier vocabularies (person,
organisation, event, task) have no taxonomy file — deliberately, until
a classifier there needs curated values.

Edges are never fields: anything pointing at another object is a relation in
`~/workspace/relations/`.
