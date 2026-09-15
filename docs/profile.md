# Profile records and CVs

Profile records are optional reusable career facts. You do not need a profile
to use ws. People and agents can use this guide to maintain one and generate
a CV. Record only information the user supplies or verifies.

## Create and inspect facts

`ws init` creates the profile scaffold; `ws profile init` can initialise this
domain separately. Inspect the available types, then add the facts you need:

```bash
ws profile taxonomy
ws create profile "Alex Example" --type identity --email me@example.org
ws create profile "Degree in Computing" --type education --bullet "Research project"
ws list profile --type education
```

Replace the fictional details with your own. There can be at most one active
identity. Other default types include work experience, publication, talk,
teaching, award, skill and volunteering. Add another with `ws profile add-type TYPE`.

```bash
ws show profile:<key>
ws edit profile:<key> --add-bullet "A reusable description of the work"
```

Use the actual REF printed by create or search. `ws help create profile` and
`ws edit profile:<key> --help` list supported fields. For facts without a CLI
flag, edit the YAML path reported by `show`, preserving its identity fields.
Useful fields include description, bullets, dates, location and subtitle.
Keep application-specific wording in a CV spec rather than rewriting a fact
for each application.

## Link a publication or organisation

```bash
ws create profile "Paper title" --type publication
ws relate profile:<paper-key> to literature:<literature-key> as represents
ws relate profile:<experience-key> to organisation:<organisation-key> as at
ws relate profile:<talk-key> to event:<event-key> as presented-at
```

Create or find the endpoints first. The publication entry selects a work for
your CV; its linked literature citation supplies the bibliographic details.
Without that link, a publication can use its own author, venue, year, DOI or
ISBN fields. Connections are explicit; there is no author-name matching.

## Generate a comprehensive CV

```bash
ws profile make-cv --out /path/to/cv-output
```

This writes editable `cv.tex` and builds `cv.pdf` using your TeX toolchain.
It includes active profile objects in taxonomy order. Use `--no-build` for
source only when TeX is unavailable or a PDF is not needed. The default output
directory is the current directory; existing deliverables require `--force`
to overwrite. Auxiliary build files go in `out/` beneath the output directory.

## Tailor a CV for an application

Save a local YAML spec, replacing the REF with an existing education record:

```yaml
schema_version: 1
variant: classic
headline: Software developer and researcher
summary: A short introduction tailored to this application.
sections:
  - type: education
    items:
      - ref: profile:degree-in-computing
        name: Degree in Computing
        bullets: []
```

```bash
ws profile make-cv --spec /path/to/application.yaml --out /path/to/cv-output
```

Sections select and order records. Item overrides change display text for this
CV only. The generator checks the spec before writing: unknown fields, missing
or inactive records, duplicate selections and type mismatches are errors.
Canonical profile facts stay unchanged. You may edit generated TeX directly;
change the spec when you want those edits to survive regeneration.

The workspace's `profile/applications/` directory is free-form. Keep job
descriptions, notes, specs, letters or generated CVs wherever useful within it.

## Check and browse

```bash
ws check profile
ws profile views rebuild
```

Browse by type or connected organisation. The profile domain's Git setup is
local with no remote by default. The generated wiki omits contact details,
date of birth, address, provenance and application contents, but generated
views still derive from your personal data and belong in your private workspace.

Maintaining the implementation: [profile and CV contract](../contracts/career.md).
