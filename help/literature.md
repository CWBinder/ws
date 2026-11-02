# Literature

A literature item is one bibliographic work, a paper, preprint or book,
held once in the workspace library: its citation and, once acquired, its
PDF, its arXiv TeX source and your own notes. Every other place that needs
the work relates to the item instead of keeping a copy.

A paper is literature even when it arrives as a loose PDF or an email
attachment: add the work by its identifier and attach the file, rather
than filing it as a document. To add one, read `ws help add literature`.

## Where literature lives

```text
~/workspace/literature/
  items/<ItemKey>/          one folder per work
  by-author/  by-field/  by-year/  by-project/
                            derived browse views, rebuilt by ws
```

The library can live elsewhere when configured (`ws help configuration`).
The folder name is the item's identity, and its REF is
`literature:<ItemKey>`. Keys are made from the first author's surname, the
year and up to three title words, as in
`Sun2026NanostructureModellingEarly`. The year may be the preprint's or
the journal's, so find a key with `ws search literature` rather than
guessing it.

## Files of an item

```text
citation.bib                the citation; the only required file
info.yaml                   classification and short reading context
paper.pdf                   a local copy of the PDF
source/arxiv/citation.bib   the arXiv record, kept beside the main citation
source/arxiv/source.tar     the raw arXiv source package
source/arxiv/files/         the extracted TeX, figures and bibliography
summary.md                  a longer summary
notes.md                    your notes
references.txt              the works this item cites
```

`citation.bib` holds one BibTeX entry, normally keyed like the folder. It
is the bibliographic truth: title, authors, year, DOI, ISBN and arXiv ID
live there and nowhere else, and keywords a source supplied go there too.
`ws show literature:<key>` prints the citation's main fields and the
classification, then says which of the PDF, the source, the arXiv record,
package and files, `info.yaml`, the summary and the notes the item has.

Everything but `citation.bib` is optional, and is created only when it adds
something. A submission with no TeX leaves `source.pdf` in `files/`
instead. Source material you already have goes under `source/` with
`ws literature attach-source`.

## Fields of info.yaml

`keywords`
: Keywords the source provided or you chose deliberately; never invented.

`fields`, `subfields`
: The classification, from the vocabulary shared with projects.

`summary`, `notes`
: Short reading context: why the work matters, what to compare. Longer
  text goes in `summary.md` and `notes.md`.

Do not repeat bibliographic facts or file status here. `info.yaml` and the
Markdown files may be edited by hand; run `ws check literature` afterwards.

## Classification

Items carry the same fields and subfields as projects, from
`~/workspace/projects/project-taxonomy.yaml` (`ws help projects taxonomy`).
Fields are broad disciplines; every subfield must belong to a chosen field.

```bash
ws literature taxonomy
ws edit literature:<key> --add-field physics --add-subfield spin-qubits
```

Extending the vocabulary with `ws literature add-field` or
`ws literature add-subfield` changes it for projects too, so add a value
only when none of the existing ones fits.

## Main citation and arXiv record

An item has one main citation in `citation.bib`. For a paper on arXiv, the
arXiv record is kept separately in `source/arxiv/citation.bib`, so a
journal citation and its preprint live side by side. Which one is main is
decided at import (`ws help add literature`).

```bash
ws literature enrich literature:<key> --arxiv
ws literature enrich literature:<key> --arxiv --arxiv-id 2502.06654
```

Enrich finds the latest arXiv version of an item added another way and
writes its arXiv record, leaving the main citation unchanged. It matches
by DOI, then by exact title, and takes the first hit: check the arXiv ID
it prints, and name the ID with `--arxiv-id` when the match is missing or
wrong.

## The PDF and the TeX

```bash
ws literature download-pdf literature:<key>
ws literature download-source literature:<key>
ws literature attach-pdf literature:<key> ~/Downloads/paper.pdf
```

The PDF download tries an open-access copy of the main DOI, then a PDF
link the DOI's metadata lists, then the latest arXiv PDF; `--arxiv` and
`--url` pick one source. If no open copy exists, ask for the file and
attach it; do not work around paywalls.

The source download uses the item's arXiv record, or looks the paper up on
arXiv the way enrich does and records what it finds. It stores the raw
package and extracts it into `source/arxiv/files/`. When the lookup finds
nothing or the wrong paper, run enrich with an explicit ID first.
`--force` replaces what is already there.

Read a paper from its TeX rather than its PDF: the TeX holds the exact
text, the equations as written, the captions and the bibliography, all
searchable. Start from the file containing `\documentclass`, follow its
`\input` and `\include`, and find the figures through `\includegraphics`.
The TeX is the latest arXiv version; when the main citation is a journal
version, its wording may differ.

## Citations

`references.txt` lists the works an item cites, one identifier per line
with an optional `# title` comment:

```text
doi:10.1000/example.123  # Title of the cited work
arxiv:2502.06654
isbn:9780000000002
```

Bare DOIs, arXiv IDs and their URLs are understood too. Fetch the list, or
write it by hand for a work no service knows:

```bash
ws literature citations literature:<key> --fetch
ws literature citations literature:<key> --in-library
ws literature cited-by literature:<key>
```

`--fetch` asks Semantic Scholar, then OpenAlex. Cited works without a DOI
or arXiv ID are counted but not listed, and an empty fetch never
overwrites an existing file; it means the providers lack data, not that the
work cites nothing. `--in-library` shows the cited works the library
holds, and `cited-by` the items that cite this one. These are extracted
facts, not relations. Your own judgements between papers, such as
`supersedes`, are relations made with `ws relate`.

## Connecting a work

```bash
ws relate project:<key> to literature:<key> as references
ws relate person:<key> to literature:<key> as co-authored
```

A project relates to the literature it builds on; a manuscript may still
keep its own buildable bibliography in the project's `refs/`, generated
from the library. Authors are related as people. A publication on your CV
is a profile record that `represents` the item, which then supplies the
CV's citation (`ws help profile`).

## Browse views

```text
by-author/<author>/<ItemKey>
by-field/<field>/by-subfield/<subfield>/<ItemKey>
by-year/<year>/<ItemKey>
by-project/<project title>/<ItemKey>
```

Authors and years come from `citation.bib`, fields and subfields from
`info.yaml`, projects from relations. Each value folder also holds `by-*`
folders for the other facets, two levels deep, and each entry is a symlink
to the item folder. Adding, editing and relating do not refresh the views;
run `ws rebuild views literature` afterwards.

## What git keeps

The lasting layer of an item is small text: `citation.bib`, `info.yaml`,
`summary.md`, `notes.md`, `references.txt` and the arXiv
`citation.bib`. The PDF, the source package and the extracted files are
bulky and can be downloaded again, so a repository holding the library
ignores `paper.pdf`, `source/arxiv/source.tar` and `source/arxiv/files/`.

## Removing a work

```bash
ws delete literature:<key> --dry-run
ws delete literature:<key>
```

The item folder, with its citation, PDF, source and notes, goes to the
Trash; its relations are removed and the views rebuilt. Delete is refused
while a profile publication `represents` the item, because the CV would
lose that entry without notice: delete that relation first.
