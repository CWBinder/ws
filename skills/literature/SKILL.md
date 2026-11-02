---
name: literature
description: Use whenever a paper, preprint, book or citation comes up. Three jobs. Find - check whether a work is already in the library, search arXiv, get a cited answer from the web, follow what a paper cites or what cites it. Read - read, quote or summarise a paper held locally, from its TeX source first. Add - ingest one into the library from a DOI, an arXiv ID or link, an ISBN, a PDF, or a paper someone sent by Slack, mail or chat, with its PDF and source, classification, and links to its authors and projects. Drives ws literature, the one canonical home for papers. Use it instead of saving PDFs into folders, keeping separate .bib files, or answering from memory about a paper that may already be on disk.
---

# Working with the literature library

The library is the `ws` literature domain: one folder per work at
`~/workspace/literature/items/<ItemKey>/`, addressed as `literature:<ItemKey>`.
An item holds the canonical citation (`citation.bib`) and, once acquired, the
PDF, the arXiv record and TeX source, and the person's own notes. Views by
author, field, year and project are generated next to `items/`; edit items,
never views. Everything goes through `ws` with the REF rules of the ws skill:
act only on full REFs taken from `ws search` or from a command's output. When
a flag is in doubt, `ws <command> -h` is the authority, not memory.

The work falls into three parts: **Find** a paper, **Read** it, **Add** it.

## Reading is free; changes need a request

Searching, showing, reading and reporting change nothing, so do them whenever
they help. Adding, downloading, attaching, enriching, classifying and relating
change the person's curated record, so do them when the request asks for that
outcome ("add this", "get me the PDF", "link it to the project"). Two requests
cover more than their words: a request to add or ingest a paper covers all of
section 5, author and project links included, and a request to read a paper
held in the library covers fetching its TeX when it is missing. When a task
turns up papers worth keeping, list them with their identifiers and offer to
add them, rather than adding them unasked.

# Find

## 1. In the library

```bash
ws search literature <a few distinctive words>
```

Every word must match, in any order, so two or three distinctive words beat a
full title, where one misremembered word leaves only partial matches. Good
terms are the first author's surname, rare words from the title, the DOI, or
the arXiv ID without its version suffix (`2606.06442`, not `2606.06442v1`).
When no item has every word, search names the word that matched nothing and
lists partial matches; drop that word and search again. Before saying a work
is absent, try the surname, a title word, the DOI and the arXiv ID. Item keys
look like `Sun2026NanostructureModellingEarly`, but the year may be the
preprint's or the journal's, so search rather than guess keys. Repeat the
search right before adding anything, because a duplicate item is worse than a
missing one.

## 2. Outside the library

After the local search, look outward:

```bash
ws literature search-arxiv <keywords> --category quant-ph
ws literature search-arxiv --title "<words>" --author <surname> --max 10
```

`search-arxiv` returns candidate papers; narrow it with `--author`, `--title`,
`--abstract` and `--category`. For a question that needs an answer with cited
sources rather than a list of papers ("which groups have measured X", "what is
the current record for Y"), use the session's web research tool when it has
one, such as `pplx "<question>"` where the pplx skill is installed. Keep the
source URL of anything you report, and check each hit against the library
(section 1) before offering to add it.

## 3. Along citations

```bash
ws literature citations literature:<key> --fetch        # bibliography into references.txt
ws literature citations literature:<key> --in-library   # cited works already held, as REFs
ws literature cited-by literature:<key>                 # library items that cite this one
```

`citations` means the paper's outgoing bibliography, not its own BibTeX.
`--fetch` asks Semantic Scholar, then OpenAlex. Works without a DOI or arXiv
ID are counted but not listed, and an empty result means the providers lack
data, not that the paper cites nothing.

# Read

## 4. Read from the TeX

Read a paper from its TeX source, not its PDF. The TeX holds the exact text,
the equations as written, the definitions, the figure captions and the
bibliography, all searchable with grep; text extracted from a PDF garbles
equations and symbols and loses structure.

1. `ws show literature:<key>` gives the folder and what the item holds.
2. `arxiv files: yes`: read `source/arxiv/files/`. Start from the main file
   (`grep -l '\\documentclass' *.tex`), follow its `\input` and `\include`,
   and take the references from the `.bbl` or `.bib`. Never read `source.tar`.
3. `arxiv files: no`: fetch the TeX first (section 6), then read it. Read the
   PDF only when no TeX exists: a PDF-only submission leaves `source.pdf`, and
   a work that is not on arXiv has none.
4. Not in the library: offer to add it (section 5), which brings the TeX in.
   Read publisher or arXiv pages only when the person declines.

Figures come with the TeX, as the files the authors uploaded; ws keeps no
separate figure folder. Find them through the TeX: `grep -n includegraphics`
on the `.tex` files gives each figure's path relative to `files/` (often a
`figures/` subfolder, sometimes the top level), and the surrounding `figure`
environment gives its caption and `\label`. Open that file to look at the
figure; it is the original at full resolution. Figures drawn in TeX itself
(TikZ, pgfplots) have no file; for those, and when there is no TeX, look at
the figure in `paper.pdf`.

Open `paper.pdf` otherwise only for typeset tables and page numbers for a
quotation. The TeX is the latest arXiv version; when the main citation is a
journal version its wording and figures may differ, so say which version a
quotation or figure comes from.

`citation.bib` is what to cite; `source/arxiv/citation.bib` is the arXiv
record. `info.yaml`, `summary.md` and `notes.md` hold the person's own reading
context; read them too.

When summarising, keep apart what the authors claim, what they actually
demonstrate, and your own inference.

# Add

## 5. Ingest a work

Ingesting means the paper ends up complete and connected, not merely present.
Work through the steps in order and report at the end.

**a. Get the identifier.** Prefer a stable one (DOI, arXiv ID or URL, ISBN);
ws fetches the metadata itself. Find it in what you were given: a link, the
first page of a PDF (`pdftotext -l 1 FILE.pdf - | grep -iE 'doi|arxiv'`), or
`ws literature search-arxiv --title "<words>" --author <surname>`. When the
paper came in a message ("the paper X sent me"), find the message first with
the message tools the session has, such as a Slack connector (search
`from:<sender> has:link`, direct messages included) or a mail and chat skill.
Take the newest link sent directly to the person; if several fit, list them
and ask. Note who sent it and where. A session that cannot read the channel,
such as a subagent without message tools, asks for the link instead of
guessing from a name or topic.

**b. Check the library** (section 1). If the item exists, skip to (d) and
complete what is missing rather than adding it again.

**c. Add it with its files and classification:**

```bash
ws add literature <ID> --full --field <field> --subfield <subfield>
```

- `--full` is `--prefer-published --pdf` plus the arXiv source download. When
  an arXiv paper has since been published, the journal version becomes the
  main citation and the arXiv record is kept alongside.
- Choose field and subfield from the abstract, with values the taxonomy
  already has (section 7).
- Then `ws show` the item and read its pdf and arxiv lines; repair anything
  missing with section 6.
- With no identifier (a thesis, report or chapter), add it with
  `--kind manual`, `--entry-type`, `--title`, `--author`, `--year` and whatever
  else is known (`--publisher`, `--journal`, `--url`). Leave unknown fields out
  rather than guessing them.
- A paper is literature even when it arrives as a loose PDF or an email
  attachment: add it here and attach the file (section 6), rather than filing
  it as a ws document.

**d. Link the authors.** For each author, `ws search person <surname>`, and
confirm the full name or an alias before treating a hit as a match. Relate
each match:

```bash
ws relate person:<key> to literature:<ItemKey> as co-authored
```

Never create a person unasked. List the authors with no person record, with
their affiliations from the author block, and ask which to add. For each one
the person approves, `ws add person` with `--source` naming the paper and a
description from the author block, then relate `co-authored`, and `works-at`
the affiliation when that organisation exists (`ws search organisation`).

**e. Link projects.** Compare the abstract with `ws list projects`: each
candidate's README purpose and the literature it already references. Relate
clear fits as `references` (section 7). Name borderline candidates in the
report with the reason they were left out.

**f. Verify** with `ws rebuild views literature` and `ws check literature`.

Report the REF, which citation is the main one (journal or arXiv), which files
came in, the classification, who sent it, each link made, the authors waiting
on the person's answer, and projects considered but not linked.

## 6. Get the PDF and the source

Ingesting with `--full` fetches both; the commands here complete an item added
without them, or repair a download that failed.

`ws show literature:<key>` lists what the item already has: `pdf`, `source`,
`arxiv source`, `arxiv package`, `arxiv files`, `info`, `summary`, `notes`.
Read those lines before fetching anything, and judge completeness from all of
them, not from one.

PDF:

```bash
ws literature download-pdf literature:<key>            # open-access DOI copy, else latest arXiv
ws literature download-pdf literature:<key> --arxiv    # force the arXiv PDF
ws literature attach-pdf literature:<key> <PATH>       # a PDF you were given (copied in)
```

If no open copy exists, say so and ask the person for the file; do not work
around paywalls.

arXiv source, the TeX that section 4 reads:

```text
show has "arxiv source: <id>"    -> ws literature download-source literature:<key>
no arXiv identity recorded       -> ws literature enrich literature:<key> --arxiv
                                    then show again, then download-source
you know the arXiv ID            -> ws literature enrich literature:<key> --arxiv --arxiv-id <ID>
you have the files locally       -> ws literature attach-source literature:<key> <PATH>
```

If enrich reports several candidates, show them and ask instead of picking
one. Some submissions have no TeX: `arxiv files` then stays empty and a
`source.pdf` appears instead. `--force` replaces existing files, so use it
only when the person asked for a replacement.

## 7. Link and classify

Linking a paper to the project it serves is what puts it among the project's
relations and in the by-project view:

```bash
ws relate project:<key> to literature:<ItemKey> as references
```

`references` is the word already in use for this; check `ws relations` before
inventing another. Judgements between papers (`supersedes`, for example) are
explicit relations too.

Classify only with values the taxonomy already has:

```bash
ws literature taxonomy
ws edit literature:<key> --add-field physics --add-subfield spin-qubits
ws rebuild views literature
```

A subfield must belong to a selected field. The taxonomy is shared with
projects, so adding a value (`ws literature add-field`, `add-subfield`)
changes it everywhere: propose the value and ask first.

## Verify and report

After any change:

```bash
ws show literature:<key>
ws check literature
```

Say exactly what changed and what is still missing, for example "added with
the journal citation; PDF downloaded; no TeX, the arXiv submission is
PDF-only". Never fill in bibliographic data, identifiers, classifications or
file status you have not seen, and delete an item only on an explicit request:
`ws delete literature:<key>` moves its folder to the Trash, and is refused while
one of the person's CV publications takes its citation from the item.
