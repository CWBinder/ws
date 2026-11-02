# Adding literature

```bash
ws add literature 2502.06654 --full --field physics --subfield numerics
ws add literature 10.1038/s41586-019-1666-5
ws add literature 978-0-00-000000-2 --title "Book title" \
  --author "Example, Alex" --year 2001 --publisher "Example Press"
```

Adding creates one item folder under `literature/items/` with its
`citation.bib` and an `info.yaml`, and prints the new REF. It relates
nothing: link authors and projects afterwards. What an item holds is in
`ws help literature`.

Search the library first; a duplicate item is worse than a missing one.
Two or three distinctive words beat a full title: the first author's
surname, a rare title word, the DOI, or the arXiv ID without its version.

```bash
ws search literature <surname> <title word>
```

## Identifiers

```text
10.1038/s41586-019-1666-5       a DOI; also doi:..., or a doi.org URL
2502.06654, 2502.06654v2        an arXiv ID; any version imports the latest
hep-th/9901001                  an old-style arXiv ID
arXiv:2502.06654                an arXiv ID with its prefix
https://arxiv.org/abs/...       an arXiv abs, pdf or e-print URL
978-0-00-000000-2               an ISBN-10 or ISBN-13; hyphens are ignored
```

The kind is detected; `--kind` overrides it. An arXiv DOI such as
`10.48550/arXiv.2502.06654` is detected as a DOI and imported as a plain
DOI citation, without the arXiv record or any download. Pass `--kind arxiv`
with it to import the paper as an arXiv paper.

Run bare on a terminal, add asks for the identifier; an empty answer starts
manual entry.

## What each kind of import does

An arXiv import reads the latest version from arXiv. The preprint becomes
the main citation, and the arXiv record is always written to
`source/arxiv/citation.bib`. When arXiv knows a published DOI, add prints
it; with `--prefer-published`, the journal's citation becomes the main one
and the arXiv record stays alongside. `--pdf` downloads the PDF, `--source`
the TeX package, extracted unless `--no-extract`. `--full` is
`--prefer-published --pdf --source` in one.

A DOI import fetches the citation from doi.org and the metadata from
Crossref, which supplies the key and, when the citation has none, keywords.
Nothing is downloaded: the download flags act on arXiv imports only. Fetch
the files afterwards:

```bash
ws literature download-pdf literature:<key>
ws literature download-source literature:<key>
```

An ISBN import looks nothing up. Title, authors and year must come from
flags or, on a terminal, from prompts; the publisher and URL are optional.
It writes a `@book` entry with the ISBN.

A manual import is for a work without an identifier, such as a thesis, a
report or a chapter: `--kind manual`, or no identifier at all with
`--title`. Title, authors and year are required. `--entry-type` sets the
BibTeX type, `article` unless given; `--journal` names an article's
journal, or an `inproceedings` entry's book title. When any of the three
required facts is missing on a terminal, add asks for the rest, optional
ones included. Leave unknown facts out rather than guessing them.

Give authors as BibTeX writes them: `"Surname, Given and Surname, Given"`.
Always pass `--year` to an ISBN or manual import that runs without a
terminal: where nobody can answer the prompt, the year silently becomes the
current one.

## Duplicates

Add refuses, naming the existing folder, a DOI the library already holds
as a main citation or an arXiv record, an arXiv paper already held, an
arXiv paper whose published DOI is already held, and an ISBN already held.
A manual entry with no identifier is not checked: search first.

## Item key

The key is made from the first author's surname, the year and up to three
title words, without small words such as "the" or "of":
`Sun2026NanostructureModellingEarly`. When that key is taken, a number is
appended. `--key` chooses the key instead and is refused when the folder
exists. A key starts with a letter or digit and holds only letters,
digits, dots, underscores, colons and hyphens.

## Classification at import

`--field` and `--subfield` classify the new item from the vocabulary
shared with projects; every subfield must belong to a chosen field. Without
a terminal, an unknown or mismatched value fails before anything is
written. On a terminal, an unknown field offers to extend the vocabulary,
and with no classification flags add asks for fields and then offers the
subfields that fit them. Without a terminal and without flags, the item
stays unclassified; classify it later with
`ws edit literature:<key> --add-field FIELD --add-subfield SUBFIELD`.

## After adding

```bash
ws show literature:<key>
ws relate person:<key> to literature:<key> as co-authored
ws relate project:<key> to literature:<key> as references
ws rebuild views literature
ws check literature
```

Read the `pdf`, `arxiv source` and `arxiv files` lines of `show` to see
what came in, and complete anything missing (`ws help literature`). Relate
each author who has a person record, checking the full name before
treating a search hit as a match, and each project the work clearly
serves. Adding and relating leave the browse views as they were, hence the
rebuild.
