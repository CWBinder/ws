# Working with literature

Use this guide to find, import, read and connect papers or books. It works for
people and agents. Start with [Getting started](../GETTING-STARTED.md) if ws
is not installed. Online acquisition needs internet access.

Examples containing `ID`, `FIELD`, `SUBFIELD`, `URL` or `<key>` are templates:
replace them with your identifier, taxonomy value or the REF printed by ws.
Use `ws help add literature` and `ws capabilities literature` for current options.

## Find and import a work

```bash
ws literature search-arxiv quantum computing
ws add literature ID
```

Search can be narrowed with `--author`, `--title`, `--abstract` and `--category`.
Import accepts a DOI, arXiv identifier, ISBN or manual metadata. An arXiv ID
imports the preprint citation; its `10.48550/arXiv.ID` DOI form also works.
For a book, supply the ISBN. If public metadata is unavailable, supply title,
author, year, publisher and URL through the available flags or terminal prompts.

```bash
ws add literature ID --prefer-published --pdf --source
```

For an arXiv import, `--prefer-published` chooses the published DOI citation
when arXiv supplies one. The arXiv citation is kept separately. `--pdf` and
`--source` download attachments; `--full` is shorthand for all three options.
Import does not connect the item to a project automatically.

`ws init` already creates the literature store. `ws literature init` can
initialise this domain separately; rerunning it preserves existing folders.

## Read and enrich an existing item

```bash
ws search literature quantum computing
ws show literature:<key>
ws literature download-pdf literature:<key>
ws literature download-source literature:<key>
```

Use the actual REF from search/import. `show` locates the canonical item folder.
Read its `citation.bib`, PDF and notes there. PDF download tries open access for
the main DOI, then the latest arXiv version. Choose `--arxiv` for arXiv explicitly,
or `--url URL` for a direct PDF; `--open-or-arxiv` selects the default strategy.
Downloaded attachments stay local and are ignored by the literature Git setup.

```bash
ws literature enrich literature:<key> --arxiv
ws literature enrich literature:<key> --arxiv --arxiv-id ID
```

Enrichment records the latest arXiv citation without replacing the main
publication citation. Supply an explicit ID when matching is ambiguous.
Source download keeps the raw package and extracts it when possible; a
PDF-only submission appears as `source.pdf`. Use `attach-pdf` or `attach-source`
with a local path to attach material you already have; inspect their help first.

## Classify and keep reading notes

```bash
ws literature taxonomy
ws literature add-field FIELD
ws literature add-subfield FIELD SUBFIELD
ws edit literature:<key> --add-field FIELD --add-subfield SUBFIELD
```

Projects and literature share the field/subfield vocabulary. Each subfield
must belong to a selected field. You can also pass `--field` and `--subfield`
on import. Terminal prompts offer compatible choices; non-interactive imports
without these flags remain unclassified. Existing defaults are sufficient.

In the item's optional `info.yaml`, keep classification and short reading context:

```yaml
schema_version: 1
keywords: [survey]
fields: [computer-science]
subfields: []
summary: "Overview of the main approaches and their tradeoffs."
notes: "Compare the evaluation methods with the project plan."
```

Use source-provided or deliberately curated keywords. Keep bibliographic facts
in `citation.bib`; use optional `summary.md` or `notes.md` for longer notes.
Manual editing is supported; run `ws check` afterward.

## Connect a work to a project

```bash
ws relate project:<project-key> to literature:<key> as references
ws show relations of project:<project-key>
```

Use this for structurally important project literature. A manuscript can keep
its own buildable bibliography in its project; the global item remains canonical.

## Follow citations

```bash
ws literature citations literature:<key> --fetch
ws literature citations literature:<key>
ws literature citations literature:<key> --in-library
ws literature cited-by literature:<key>
```

Fetching tries Semantic Scholar, then OpenAlex when no usable references are
returned. An empty result preserves an existing `references.txt`. You can also
maintain that file by hand, one DOI, arXiv or ISBN identifier per line with an
optional `# title` comment. Citation overlap is computed from these files.
Use explicit relation edges for your own assertions such as `supersedes`.

## Browse and check

```bash
ws literature views rebuild
ws check
```

Browse by author, field/subfield, year or connected project. Views point to the
same item folders; edit the items, not the generated trees. See
[Browsing](browsing.md) for defaults and optional variations.

Maintaining the implementation: [literature contract](../contracts/library.md).
