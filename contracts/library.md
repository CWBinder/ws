# Literature Contract


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

Example after reading a paper:

```yaml
schema_version: 1
keywords:
  - neutral atoms
  - qudits
fields:
  - physics
subfields:
  - quantum-computing
summary: "All-optical control proposal for nuclear-spin qudits in alkaline-earth atoms."
notes: "Useful comparison point for project-level control assumptions."
```

## Initialization

Use:

```text
ws literature init
```

This command creates the base folders:

```text
~/workspace/literature/items/
```

It is idempotent. If a folder already exists, it is left unchanged and reported as `ok`. It does not delete, empty, rename, overwrite, or reorganize existing files.

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

For arXiv search and import, use:

```text
ws literature search-arxiv <keywords> [--author <name>] [--title <words>] [--abstract <words>] [--category <cat>]
ws add literature <arxiv-id> [--prefer-published] [--pdf] [--source]
ws add literature <arxiv-id> --full
```

`search-arxiv` queries arXiv metadata and prints result numbers, arXiv IDs, authors, categories, DOI when present, URLs, and abstract snippets. `add` with an arXiv id creates one canonical item, always writes `source/arxiv/citation.bib`, and can optionally download the PDF and arXiv source. `--full` is shorthand for `--prefer-published --pdf --source`.

For an arXiv-only preprint or unpublished manuscript, use `add` without `--prefer-published`; the arXiv DOI form works too:

```text
ws add literature <arxiv-id>
ws add literature 10.48550/arXiv.<arxiv-id>
```

This makes the arXiv citation the main `citation.bib` for that item.

For a book, ISBN is sufficient as the stable identifier. Use:

```text
ws add literature <isbn>
```

The command writes an `@book` entry with `isbn` in `citation.bib`. If public ISBN metadata is not available through the current tooling, provide title, author, year, publisher, and URL through flags or the interactive prompts.

If a published paper also has an arXiv version, keep the published `citation.bib` clean. Store the arXiv citation separately at:

```text
items/<ItemKey>/source/arxiv/citation.bib
```

`ws add literature <arxiv-id> --prefer-published` uses the non-arXiv DOI exposed by arXiv as the main `citation.bib` when available, and keeps the arXiv BibTeX at `source/arxiv/citation.bib`.

`ws literature enrich literature:<ItemKey> --arxiv` should use the latest arXiv version and write that source citation without changing the main publication citation. If the automatic DOI/title match is ambiguous or unavailable, use:

```text
ws literature enrich literature:<ItemKey> --arxiv --arxiv-id <arxiv-id>
```

`ws literature download-source literature:<ItemKey>` uses the latest arXiv version, refreshes `source/arxiv/citation.bib`, downloads the raw arXiv e-print package to `source/arxiv/source.tar`, and extracts it into `source/arxiv/files/` when possible. If arXiv only provides a submitted PDF rather than TeX source, the extracted file is named `source.pdf`. The former `--arxiv` flag remains accepted as a compatibility no-op.

`ws literature download-pdf literature:<ItemKey>` should first try an open-access PDF for the main DOI and then fall back to the latest arXiv PDF when available. Use explicit modes when needed:

```text
ws literature download-pdf literature:<ItemKey> --open-or-arxiv
ws literature download-pdf literature:<ItemKey> --arxiv
ws literature download-pdf literature:<ItemKey> --url <direct-pdf-url>
```

Downloaded PDFs are local attachments and are not tracked by the literature git repository by default.

## Classifiers

Literature items carry the same `fields` and `subfields` classifiers as
projects. Both vocabularies live in
`~/workspace/projects/project-taxonomy.yaml`: `fields` is a flat list of broad
disciplines, while `subfields` maps each broad field to its narrower values.
Both may be multi-valued, but every selected subfield must belong to at least
one selected field. `ws literature taxonomy` shows the allowed values;
`add-field` and `add-subfield <field> <subfield>` extend them.

The values live in `info.yaml`. `ws add literature` applies them with
`--field` and `--subfield`; incompatible combinations fail before the item is
written. With no flags on a terminal, the wizard asks first for fields and
then only their compatible subfields. Non-interactive adds without flags
leave the item unclassified. Use `ws edit literature:<ItemKey>` with
`--add-field`/`--remove-field` and `--add-subfield`/`--remove-subfield` for
existing items; manual `info.yaml` editing remains supported and `ws check`
validates it.

The derived browse trees sit at the literature domain root, beside the
`items/` store, rebuilt with `ws literature views rebuild`. Their shapes are
declared in the folder anatomy file (see `folder-anatomy.md`); the default
ring set is

```yaml
rings: [author, field > subfield, year, project]
depth: 2
```

so each value folder holds its items flat plus nested `by-*` rings for the
facets not yet used along the path:

```text
literature/by-author/<full-author-name>/<ItemKey>
literature/by-author/<full-author-name>/by-year/<year>/<ItemKey>
literature/by-field/<field>/by-subfield/<subfield>/<ItemKey>
literature/by-project/<project title>/<ItemKey>
```

Unclassified items land in first-layer `unclassified/` buckets so nothing
is invisible; deeper rings simply omit them.
The trees are disposable symlinks; item folders never move. Authors and year
are derived from `citation.bib`; fields and subfields are the editable
literature classifiers. Multi-valued items appear under every valid path; the
view engine never places a subfield beneath an unrelated field.

## Citations

`references.txt` is an optional item-local list of the works the item cites:
one identifier per line, with optional `# title` comments.

```text
doi:10.1103/physreva.57.120  # Quantum computation with quantum dots
arxiv:2301.01234  # Some cited preprint
```

Canonical tokens are `doi:...`, `arxiv:...` (version suffix stripped), and
`isbn:...`, but bare DOIs, arXiv ids, doi.org/arxiv.org URLs, and arXiv DOIs
are understood and normalized on read. `ws literature citations
literature:<ItemKey> --fetch` first queries Semantic Scholar and falls back to
OpenAlex when that graph returns no usable references. It resolves cited works
to DOI/arXiv identifiers, records titles as comments, and reports which
provider succeeded. An empty fetch never overwrites the existing file. The
file can also be written or edited by hand for items no external service knows.

Citations are extracted facts of the item, so they are stored here rather
than as relation edges, and the in-library overlap is computed on demand:

```text
ws literature citations literature:<ItemKey>                 all cited identifiers
ws literature citations literature:<ItemKey> --in-library    cited works held here, as REFs
ws literature cited-by literature:<ItemKey>                  library items whose references include this one
```

Deliberate paper-to-paper assertions (supersedes, published-version-of) may
still be `ws relate` edges; they are rare and hand-made.

## Projects

Projects do not store canonical literature items. A project may keep local references under:

```text
projects/items/<project>/refs/
```

Manuscripts should remain buildable with their own local bibliography, even when that bibliography is generated from the global library.

### Recording new items in a project

Relations are created exclusively with `ws relate` — `add` takes no linking
flags and asks no linking questions. After adding, record the connection as
`ws relate project:<key> to literature:<ItemKey> as references`.
`project.yaml`'s `related_literature` field stays read-only legacy and is
never written. Duplicate edges are no-ops.

## Commands

Use:

```text
ws literature init
ws add literature <doi|arxiv-id|isbn>
ws add literature <arxiv-id> --full
ws add literature <doi> --field physics --subfield spin-qubits
ws literature taxonomy
ws literature add-field <field>
ws literature add-subfield <field> <subfield>
ws edit literature:<ItemKey> --add-field <field> --add-subfield <subfield>
ws literature views rebuild
ws literature search-arxiv <keywords>
ws show literature:<ItemKey>
ws search literature <query>
ws literature enrich literature:<ItemKey> --arxiv
ws literature download-source literature:<ItemKey>
ws literature download-pdf literature:<ItemKey>
ws literature attach-pdf literature:<ItemKey> <path>
ws literature attach-source literature:<ItemKey> <path>
ws literature citations literature:<ItemKey> [--in-library] [--fetch]
ws literature cited-by literature:<ItemKey>
```

Manual editing is supported. Keep `citation.bib` valid and treat every `by-*` folder as replaceable.

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
