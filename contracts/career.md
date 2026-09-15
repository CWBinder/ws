# Profile and CV Contract

`~/workspace/profile/` owns canonical personal and career material. The domain
uses the same object-store and derived-view pattern as the other domains:

```text
profile/
  items/<profile-id>.yaml       one canonical profile object per file
  profile-taxonomy.yaml        allowed types, in default CV section order
  by-type/  by-organisation/    generated symlink rings; disposable
  applications/                free-form material for individual applications
```

There is deliberately no `profile/profile/`, dedicated `cv/`, application
template tree, or required application-folder anatomy.

## Profile objects

Every CV-worthy fact is a first-class object with the universal object fields
from `objects.md`: `id`, `kind: profile`, `name`, `type`, `aliases`, and
`description`. `description` is reusable CV prose. `bullets` is an optional
list of already useful or draft CV bullet points. An object may also contain
type-specific text and dates such as `subtitle`, `start`, `end`, `year`, and
`location`.

The initial type vocabulary, and its CV order, is:

```text
identity
education
work-experience
publication
talk
teaching
award
skill
volunteering
```

The vocabulary is data, not a closed enum: extend it with
`ws profile add-type <type>` or by editing `profile-taxonomy.yaml`. There may
be at most one active `identity` object. Absent status means active; merged
tombstones are excluded from generated CVs.

Useful optional facts include:

- identity: `headline`, `emails`, `phones`, `address`, `links`, `orcid`,
  `post_nominals`, `date_of_birth`;
- education: `qualification_status` for completion notes such as
  `programme not completed`;
- publication fallback metadata: `author`, `venue`, `year`, `doi`, `isbn`;
- any non-identity object: `subtitle`, `start`, `end`, `year`, `location`,
  `description`, `bullets`.

These are conveniences, not rigid per-type schemas. The durable content is
the text, and agents may add useful domain-specific scalar or list facts
without inventing a parallel storage system.

## Relationships and publications

Pointers to another workspace object are relations, never embedded foreign
keys. Creation supports direct relations to literature, organisations, events,
and projects. Defaults are:

```text
publication --represents--> literature
talk        --presented-at--> event
any object  --at--> organisation
```

A publication object is the CV assertion that a publication belongs in the
profile. Its related literature item's `citation.bib` remains the citation
source of truth. This replaces author-name matching and copied
`own-publications.bib` files. A publication without a literature relation may
use its own fallback metadata.

## Commands

```bash
ws profile init
ws create profile "Alex Example" --type identity --email me@example.org
ws create profile "DPhil Physics" --type education --bullet "Research bullet"
ws create profile "Paper title" --type publication
ws relate profile:<paper-key> to literature:<key> as represents
ws list profile [--type education]
ws show profile:<key>
ws edit profile:<key> --add-bullet "Improved bullet"
ws profile taxonomy
ws profile add-type <type>
ws profile views rebuild
```

`create` and `edit` are the normal writers. Direct YAML editing is permitted
for fields the CLI does not expose, provided the universal fields and taxonomy
remain valid. `ws check profile` validates records, types, and identity
cardinality.

## Comprehensive CV generation

```bash
ws profile make-cv --out <directory>
ws profile make-cv --out <directory> --no-build  # source only
ws profile make-cv --spec <file> --out <directory>
```

`make-cv` writes one long, self-contained, editable `cv.tex` containing every
active profile object, grouped in taxonomy order, and compiles a ready-to-open
`cv.pdf` beside it. The default output directory is the current directory. It
refuses to overwrite either deliverable without `--force`. Auxiliary LaTeX
artifacts go in an `out/` sibling directory. Use `--no-build` only when a TeX
source without a PDF is explicitly wanted. The former `--build` flag remains
accepted for compatibility but is no longer necessary.

Without `--spec`, the comprehensive file is a factual starting point containing
all active profile objects. With `--spec`, the input is a versioned YAML mapping
that may provide an application-specific `headline` and `summary`, an optional
layout `variant`, and an ordered `sections` list. Each section has a profile
`type`, an optional display `title`, and an explicit `items` list. Items identify
canonical objects by full `profile:<key>` REF and may override display fields
(`name`, `subtitle`, dates, location, completion note, description, or bullets)
for that CV only.

The generator validates the spec before writing anything: unknown fields,
unknown or inactive REFs, duplicate selections, and objects placed under the
wrong profile type are errors. Canonical profile objects remain unchanged.
Application-specific prose belongs in the spec; reusable facts belong in the
profile objects.

Example:

```yaml
schema_version: 1
variant: classic
headline: Theoretical physicist with extensive teaching experience
summary: >
  A short application-specific introduction.
sections:
  - type: education
    items:
      - ref: profile:dphil-in-quantum-technologies
      - ref: profile:msc-theoretical-and-computational-physics
        name: MSc studies in Theoretical and Computational Physics
        bullets: []
```

Generated TeX is self-contained and editable, but reproducible application CVs
should normally be changed through the spec or canonical profile objects and
then regenerated. Tailoring must not delete or distort canonical profile data.

## Applications

`applications/` has no enforced internal structure. A folder may contain a job
description, notes, correspondence, a generated CV, letters, PDFs, or anything
else relevant. Tooling must neither require a particular set of files nor
create a dedicated nested CV folder.

## Privacy and Git

The profile root is a local Git repository with no remote by default. Build
artifacts are ignored. The generated wiki may expose a professional name,
headline, description, skills, type counts, and explicitly related
publications, but never contact details, date of birth, address, provenance,
or application contents.
