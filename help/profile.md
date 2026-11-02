# Profile

The profile holds your own career facts, one record each: who you are,
each degree, position, publication, talk, teaching post, award and skill.
CVs are generated from these records, so a fact is written once and reused
by every CV. A profile is optional; nothing else in ws needs one.

Record only facts the person supplied or verified: never invent an
employer, a date, a title or a credential. To add a fact, read
`ws help create profile`.

## Where the profile lives

```text
~/workspace/profile/
  items/<key>.yaml          one record per fact
  profile-taxonomy.yaml     the allowed types, in CV section order
  applications/             free-form material for single applications
  by-type/  by-organisation/
                            derived browse views, rebuilt by ws
  README.md  .gitignore  .vscode/
```

A record's REF is `profile:<key>`, the key made from its name when it was
created.

`ws init` creates the folders and the taxonomy. `ws profile init` adds the
README, the `.gitignore`, editor settings that send LaTeX output to `out/`,
and a git repository, local and with no remote, kept apart from the
workspace's records. It creates only what is missing. The `.gitignore`
keeps out the views and LaTeX build files.

## Types

```text
identity          you: name, headline, contact details; at most one
education         a degree or programme
work-experience   a position
publication       a work you published
talk              a talk or conference contribution
teaching          a course or class you taught
award             an award or honour
skill             a skill
volunteering      volunteer work
```

The list is data: `ws profile add-type TYPE` extends it, appending the new
type at the end. Its order is the section order of a comprehensive CV, and
the file may be reordered by hand. A unique prefix stands for a type, so
`edu` means `education`.

There is at most one identity record. A CV cannot be generated without it.

## Fields of a record

`name`, `aliases`, `type`
: The entry's title as the CV shows it, other names it goes by, and its
  type.

`description`
: Reusable CV prose for the entry.

`bullets`
: Achievement lines, finished or draft.

`subtitle`, `location`
: The second line, such as the institution or employer, and the place.

`start`, `end`, `year`
: Dates as `YYYY`, `YYYY-MM` or `YYYY-MM-DD`; `end` may be `present`. A
  start with no end is shown as an open range.

`qualification_status`
: For education, a completion note such as `programme not completed`.

`headline`, `emails`, `phones`, `address`, `links`, `orcid`,
`post_nominals`, `date_of_birth`
: Identity facts. The CV header shows the first address, email and phone,
  the ORCID, and the date of birth and post-nominals unless left off.

`author`, `venue`, `year`, `doi`, `isbn`
: A publication's own citation facts, used only when no literature item
  supplies its citation.

`status`, `provenance`
: An optional status, and who asserted the facts and when.

These are conveniences, not a fixed schema per type. Change a record with
`ws edit profile:<key>`; every field above has a flag there, and
`ws check profile` validates the records. The CV never shows a field
outside this list.

## Relations the CV reads

Links to other objects are relations, made with `ws relate` after the
record exists:

```text
publication  --represents-->    literature
talk         --presented-at-->  event
any entry    --at-->            organisation
```

A publication that `represents` a literature item takes its citation from
the item's `citation.bib`; that is the one place its authors, venue and
year are kept. Without that relation, the publication uses its own
`author`, `venue`, `year`, `doi` and `isbn`. ws never matches publications
to papers by author name. Deleting a literature item a publication
represents is refused until that relation is deleted.

On every entry but a publication, each related object other than
literature, such as the organisation of a position or the event of a
talk, is named on the entry's second line next to its subtitle and
location.

## Generating a CV

```bash
ws profile make-cv --out ~/workspace/profile/applications/example
```

Without a spec, make-cv writes a comprehensive CV: the identity as header,
then every record except merged duplicates, grouped by type in taxonomy
order, newest first within a section, with ongoing entries on top. It
writes an editable `cv.tex` and builds `cv.pdf` beside it with `latexmk`;
the auxiliary files go into `out/` below the output folder. The output
folder defaults to the current one. Existing deliverables are not
overwritten without `--force`, and `--no-build` writes the TeX only, for
when no TeX installation is at hand.

A record's status does not keep it out of a CV; a spec does.

## Tailoring a CV with a spec

Everything specific to one application goes in a spec, a YAML file usually
kept in that application's folder. The canonical records stay unchanged
and keep serving every other CV.

```yaml
schema_version: 1
variant: classic
headline: Software developer and researcher
summary: Two or three sentences aimed at this application.
sections:
  - type: work-experience
    title: Experience
    items:
      - ref: profile:<key>
        bullets:
          - Evidence phrased against the job description.
      - profile:<key>
  - type: publication
    items:
      - profile:<key>
```

```bash
ws profile make-cv --spec spec.yaml --out .
```

`headline` and `summary` replace the identity's headline and description
for this CV. Sections appear in the order listed and hold only the items
listed; a section's `title` defaults to the type's usual heading. An item
is a REF, or a mapping with `ref` and any of `name`, `subtitle`,
`description`, `bullets`, `start`, `end`, `year`, `location` and
`qualification_status`, which change this CV only. The identity cannot be
a section.

The spec is checked before anything is written: an unknown field, an
unknown or merged REF, an item listed twice, or an item under a section of
another type is an error. Edits made to the generated TeX are lost when it
is regenerated; make lasting changes in the spec, or in the records when
the fact itself changes.

`applications/` has no required structure. A folder per application, such
as `applications/<organisation-or-role>/`, can hold the job description,
notes, the spec, letters and the generated CV.

## Privacy

The profile holds personal data. The generated wiki may show your name,
headline, description, ORCID, skills, type counts and related
publications, but never contact details, date of birth, address,
provenance or anything from `applications/`. The browse views are still
derived from personal data and belong in a private workspace. Put contact
details and the date of birth on a CV only where the application calls
for them; `--no-dob` leaves the date of birth off.

## Checking and browsing

```bash
ws check profile
ws rebuild views profile
```

The views group records by type and by related organisation. Creating and
editing a record refresh them; after relating, rebuild them by hand.
