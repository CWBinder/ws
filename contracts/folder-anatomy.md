# Folder Anatomy Contract

Usage and optional view customisation: [Browsing](../docs/browsing.md).

The shape of every derived `by-*` browse tree is data, declared in one
canonical, hand-edited file at the workspace root:

```text
~/workspace/folder-anatomy.yaml     (override: WS_FOLDER_ANATOMY)
```

One engine (`ws_lib/anatomy.py`) consumes it for all domains — spec loading,
validation, tree building, and the per-domain item supply live in that single
module. The anatomy file and the engine are the only two places view
structure exists.

## Format

```yaml
schema_version: 1

<domain>:                # projects | documents | literature | profile | resources
  rings: [a, b, c > d]   # the facets that may become by-* rings
  depth: 2               # independent hops per path, 1..3 (default 2)
```

One ring set per domain. Every facet in the set gets a `by-<facet>` tree at
the domain root, and the set nests into itself: each value folder holds the
items that reached it plus a `by-*` ring for every facet not already used
along the path, down to `depth` independent hops. `c > d` declares a
dependent facet: `d` appears only beneath a value of `c`, refines it in
place, and does not count toward depth. `schema_version` is required and
must be `1`.

## Facets

A facet is one of exactly two things:

- a **classifier** of the domain's own records — values read from the
  object's canonical files:
  projects `type`, `field`, `subfield`, `status`; documents `type`, `year`, `month`
  (derived from `classification.date`); literature `author`, `field`, `subfield`, `year`
  (authors and year are derived from `citation.bib`); profile `type`;
  resources have none — their rings are kinds only.
- a **kind** — `organisation`, `event`, `person`, `task`, `document`,
  `project`, `literature`, `profile`, `resource` — folders are the *names
  of related objects*, resolved through edges in the relations store, both
  directions, any relation type.

Resolution tries classifiers first, then kinds. A name valid on both sides
is refused as ambiguous; the escape hatch is an explicit prefix
(`classifier:event` / `kind:event`), accepted anywhere a facet is.

Two classifiers are **dependent** and never stand alone: `month` refines
`year`, `subfield` refines `field`. They must be declared behind their
parent (`year > month`, `field > subfield`) and are refused as ring heads.

## Rules

- A facet never repeats along one path; `depth` (at most 3) caps the
  independent hops, dependent refinements ride free.
- `unclassified/` exists only at the first layer beneath a domain root, for
  objects missing that facet (no date, no edge, empty classifier). A
  fallback terminates its path: nothing nests beneath `unclassified/`.
- Below the first layer there are no fallback buckets: an item missing a
  facet stays flat in the value folder and simply does not descend into
  that ring. A ring nobody descends into is never created — empty rings
  prune away, so the visible menu at each node reflects the data.
- Multi-valued facets (several authors, fields, or organisation edges)
  produce one link per value, at every layer.
- When `subfield` follows `field`, the engine emits only values allowed for
  that particular field by the shared taxonomy. A multi-field object
  therefore never creates false field/subfield Cartesian products.
- A domain listed in the file is **complete**: exactly those rings are
  built. Domains absent from the file (or the whole file absent) fall back
  to built-in defaults.

## Stability

- The spec is presentation-only: the engine writes nothing but symlinks
  under `by-*` directories. Canonical stores, records, relations, and
  taxonomies are out of reach.
- Every `by-*` directory at a domain root is owned by the engine and wiped
  on rebuild — removing a facet from the file removes its tree from disk.
- Validation happens **before** any wipe: a broken file aborts with the
  previous trees intact. The retired per-tree grammar (`by-<name>:` keys
  with `group-by`/`levels`/`values`) is refused as a validation error.
- Rebuilds are deterministic: same canonical data + same file = same tree.
- `ws check anatomy` (and bare `ws check`) validates the file.

## Extension and compatibility rules

- Add facets through the common engine and its canonical item suppliers;
  domain-specific copies of the view grammar are not allowed.
- Preserve classifier/kind disambiguation and dependent-facet validation.
- New shape options require validation before destructive view rebuilding.
  Unsupported schema versions must fail without replacing existing views.
- Defaults may evolve for new workspaces; preserve a user's explicit anatomy.
  A new grammar requires [a compatibility plan](README.md#changing-a-contract).
- Verify deterministic output, invalid-spec preservation, multi-value paths,
  unclassified fallbacks and the exclusion of canonical data from writes.
