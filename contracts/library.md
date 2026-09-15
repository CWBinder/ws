# Literature Contract

Usage: [Working with literature](../docs/literature.md).
This contract governs implementations and extensions of the literature store.


If `WS_LITERATURE_DIR` is set, that directory is the literature root. By
default it is `~/workspace/literature/`.

Each paper or reference is stored exactly once in an item folder:

```text
items/<ItemKey>/
  citation.bib
  info.yaml
  paper.pdf
  source/
    arxiv/
      citation.bib
      source.tar
      files/
  summary.md
  notes.md
  references.txt
```

Only `citation.bib` is required. It is the bibliographic source of truth and should contain one BibTeX entry whose key matches `<ItemKey>` when possible.

`info.yaml` is optional but recommended for the item's workspace-local facts:
classification and reading context that are not citation truth. It does not
carry identity — the folder name is the identity.

```yaml
schema_version: 1
keywords: []
fields: []
subfields: []
summary: ""
notes: ""
```

Use source-provided or human-curated keywords only. Keep summaries short and useful for recall. Do not duplicate title, authors, year, DOI, ISBN, arXiv ID, PDF status, or source status in `info.yaml`; those are in BibTeX or represented by files.

## Optional Files

Use optional files only when they add real information:

```text
paper.pdf   local PDF copy, if legally available and intentionally attached
source/     TeX/arXiv/source material for the item
summary.md  human- or agent-readable summary
notes.md    local notes
```

Do not create a required `meta.yaml` by default. Do not duplicate title, authors, year, DOI, arXiv ID, ISBN, or file status in a second metadata file.

If a source provides keywords, keep them in `citation.bib`. Do not invent keywords automatically.

## Acquisition guarantees

- Initialisation creates missing base folders and preserves existing content.
- An arXiv import writes the source citation separately. Without
  `--prefer-published`, the preprint is the main citation; with it, a published
  non-arXiv DOI supplied by arXiv becomes the main citation when available.
  `--full` retains its meaning of published preference plus PDF and source.
- ISBN imports produce a book citation with its ISBN; unavailable metadata
  requires supplied facts rather than invented bibliographic details.
- arXiv enrichment uses the latest version and preserves the main publication
  citation. An explicit arXiv ID can disambiguate matching.
- Source acquisition refreshes the arXiv citation, stores the raw e-print at
  `source/arxiv/source.tar` and extracts into `source/arxiv/files/` when possible.
  PDF-only submissions use `source.pdf`. The former source-download `--arxiv`
  flag remains a compatibility no-op.
- Default PDF acquisition tries open access for the main DOI, then the latest
  arXiv PDF. Explicit arXiv and URL modes retain their distinct meanings.

## Classifiers

Literature items carry the same `fields` and `subfields` classifiers as
projects. Both vocabularies live in
`~/workspace/projects/project-taxonomy.yaml`: `fields` is a flat list of broad
disciplines, while `subfields` maps each broad field to its narrower values.
Both may be multi-valued, but every selected subfield must belong to at least
one selected field. Values live in `info.yaml`; incompatible supplied
combinations fail before writing an item. Terminal prompts offer compatible
values; non-interactive imports with no classifiers remain unclassified.
Manual edits remain supported and are validated by checks.

## Derived views

Authors and years come from `citation.bib`; fields and subfields come from
`info.yaml`; related projects come from canonical edges. View shape and rebuild
invariants belong to [folder anatomy](folder-anatomy.md). Item folders never
move during view rebuilding.

## Citations

`references.txt` is an optional item-local list of the works the item cites:
one identifier per line, with optional `# title` comments.

Canonical tokens are `doi:...`, `arxiv:...` (version suffix stripped), and
`isbn:...`, but bare DOIs, arXiv ids, doi.org/arxiv.org URLs, and arXiv DOIs
are understood and normalized on read. `ws literature citations
literature:<ItemKey> --fetch` first queries Semantic Scholar and falls back to
OpenAlex when that graph returns no usable references. It resolves cited works
to DOI/arXiv identifiers, records titles as comments, and reports which
provider succeeded. An empty fetch never overwrites the existing file. The
file can also be written or edited by hand for items no external service knows.

Citations are item-local extracted facts, not curated edges. In-library overlap
is computed on demand from identifiers; no second canonical citation graph is
created.

Deliberate paper-to-paper assertions (supersedes, published-version-of) may
still be `ws relate` edges; they are rare and hand-made.

## Projects

Projects do not store canonical literature items. A project may keep local references under:

```text
projects/items/<project>/refs/
```

Manuscripts should remain buildable with their own local bibliography, even when that bibliography is generated from the global library.

Project literature links are explicit canonical `references` edges. Import
must not write linking flags or a `related_literature` list into project YAML;
that field is read-only legacy. Repeating an identical edge is idempotent.

## Git Boundary

The literature repository should track the lightweight, editable knowledge layer:

```text
citation.bib
info.yaml
summary.md
notes.md
references.txt
source/arxiv/citation.bib
```

It should not track downloaded or bulky local attachments:

```text
paper.pdf
source/arxiv/source.tar
source/arxiv/files/
```

## Extension and compatibility rules

- New metadata providers must produce the same canonical BibTeX and attachment
  layout. Provider responses must not establish a parallel identity store.
- New local fields must represent local knowledge rather than duplicate
  bibliographic facts or infer file status. Keep existing items valid without
  requiring optional files.
- New citation providers must preserve identifier normalization and the
  empty-fetch protection for existing references.
- Schema or identifier changes require an explicit compatibility/migration
  plan under [the shared change rules](README.md#changing-a-contract).
  Never re-key existing items as a side effect of enrichment or view rebuilding.
- Verify import/enrichment citation ownership, validation before item writes,
  empty-reference preservation and attachment Git boundaries when changing them.
