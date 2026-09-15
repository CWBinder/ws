# Literature contract

Literature is a managed database. `ws add literature` accepts a DOI, arXiv
identifier, ISBN, or manual metadata and places the item in the canonical
literature item store. The detailed item, BibTeX, classifier, and view invariants
remain in `library.md`.

Relations are created exclusively with `ws relate`: `add` ingests the item
and nothing else. Link it afterwards, e.g.
`ws relate project:<key> to literature:<ItemKey> as references`.

Items carry the shared workspace classifier system: broad `fields` and their
controlled, field-specific `subfields`, both multi-valued and stored in
`info.yaml`, browsable via
`ws literature views rebuild`. Authors and year are derived directly from
`citation.bib`; the default browse trees are `by-author`,
`by-field/<field>/<subfield>`, and `by-year` (see `library.md`, Classifiers).

Citations are extracted facts, not curated edges: each item may carry a
`references.txt` identifier list, and `ws literature citations`/`cited-by`
compute the in-library overlap on demand (see `library.md`, Citations).
