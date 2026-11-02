---
name: cv
description: Create or update a CV tailored to a specific application — job, fellowship, internship, scholarship, grant. Use whenever the person mentions a CV, resume, or Lebenslauf in any context: making one for a company or role, refreshing or regenerating an existing one, adding a publication, talk, or skill to their career profile, or asking what their CV should emphasize for an application. Drives ws profile and its LaTeX generator; tailoring lives in per-application spec files, never in the canonical facts.
---

CVs are generated from the canonical profile store (`~/workspace/profile/`:
education, work, publications, talks, teaching, awards, skills) through a
fixed, hand-tuned LaTeX template. Neatness comes from the template and the
spec workflow, not from repeated visual inspection — trust the template,
verify from the build log, look at the PDF exactly once.

Load the `ws` skill before running ws commands. Reference:
[docs/profile.md](../../docs/profile.md); contract:
[contracts/career.md](../../contracts/career.md).

## Step 1: Application folder
Work in `~/workspace/profile/applications/<org-or-role>/` (create it if new;
contents are deliberately free-form). Put the job description and any notes
there and read whatever is already present. Understand the target before
tailoring: what the role values determines section order and bullet emphasis.

## Step 2: Survey the facts
`ws list profile` (or per `--type`) to see what exists; `ws show profile:<key>`
for detail. Pick the objects that serve this application. If a needed fact is
missing — a new talk, skill, paper — that is a canonical change: propose the
`ws create profile` / `ws edit` command and get the person's confirmation
before running it. Never invent employers, dates, titles, metrics, or
credentials, and never edit canonical facts just to suit one application.

## Step 3: Write the spec
All tailoring goes in `spec.yaml` in the application folder. Do not hand-edit
the generated TeX (those edits die on regeneration) and do not rewrite
canonical objects (they serve every future CV):

```yaml
schema_version: 1
variant: classic
headline: <one line aimed at this application>
summary: <2-3 sentence introduction tailored to this application>
sections:
  - type: work-experience   # section order = emphasis order
    title: Experience        # optional; defaults per type
    items:
      - ref: profile:<key>
        name: <optional shorter title if the canonical one runs long>
        bullets:             # optional rewrite for this CV only; omit to keep canonical text
          - <evidence phrased against the job description>
```

Sections select and order records; anything not listed simply does not
appear. Item overrides (`name`, `subtitle`, `description`, `bullets`) change
this CV only. The generator validates the spec — unknown fields, inactive
refs, duplicates, and type mismatches all fail loudly before anything is
written.

## Step 4: Generate and build
```bash
ws profile make-cv --spec spec.yaml --out .
```
Writes `cv.tex` and builds `cv.pdf` (latexmk; aux files under `out/`).
Re-runs need `--force`, which is fine while the spec is the only thing being
edited. Iterate by editing the spec and regenerating — never by patching TeX.

## Step 5: Neatness check — log first, one look
The template already guarantees margins, fonts, spacing, and orphan control.
Do not restyle the preamble. Verify cheaply, in this order:

1. `grep -E "Overfull|Underfull" out/cv.log` — each hit is a line intruding
   into the margin; fix by rewording that bullet or shortening that title in
   the spec. A clean template build has zero hits.
2. `grep -o "([0-9]* pages" out/cv.log` — over the application's page limit
   means cutting or tightening entries in the spec, not shrinking type.
3. Read `cv.pdf` once (the Read tool renders PDFs) and check: within the page
   limit, no heading stranded at a page bottom, no long entry title colliding
   with its date rule, no near-empty final page, dates and links correct,
   section order matching the application's priorities.

Fix findings in the spec, rebuild, re-check the log. One visual pass plus at
most one fix-and-rebuild cycle; if it still looks off after that, show
the person the PDF and ask rather than polishing further — their eye settles
taste questions faster than another iteration.

## Step 6: Deliver and file
Give the person the final PDF (send the file when a send tool is available).
If they want it kept, ingest it into the documents store with `ws add document`
(use `--mode copy` so the application folder keeps its copy) and relate it to
the target organisation, following the pattern of earlier CV documents
(`ws search documents cv`).

## Rules
- Facts live in the profile store; tailoring lives in the spec; canonical
  edits happen only with the person's explicit confirmation.
- Never delete or suppress profile objects because one application does not
  need them.
- Include contact details and date of birth only when appropriate for the
  application; never copy application material into the public wiki.
- If a `cv.tex` was hand-edited at some point, do not regenerate over it
  without checking with the person first.
