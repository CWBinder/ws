# Adding what already exists

`ws add` brings something that exists outside the workspace into it: a
person, an organisation or an event you deal with, a file as a document, a
paper or book by its identifier, or a file into an existing resource
bundle. Things that do not exist yet are made with `ws create`
(`ws help create`).

The kind comes first, then its operands, then flags:

```bash
ws add person Alex Example --email alex@example.org --ensure
ws add document ~/Downloads/venue-invoice.pdf --type invoice --date 2026-07-15
ws add literature <DOI-or-arXiv-ID>
ws add resource:<key> ~/Downloads/receipt.pdf
```

A REF right after `add` targets the existing object it names: that is how
a file goes into a resource bundle.

Three conventions hold across the kinds:

- **Search first, or pass `--ensure`.** With `--ensure`, a person,
  organisation, event or document that matches an existing one is reused
  instead of duplicated.
- **Sign what you assert.** `--source` says who or what stated the facts,
  `--observed-at` when. Pass both whenever you know them.
- **Files move by default.** `ws add document` moves the file into the
  workspace; pass `--mode copy` to leave the original where it is.

On a terminal, a bare command asks for what is missing; `--non-interactive`
never asks. Adding relates nothing: link the new object afterwards with
`ws relate` (`ws help relate`).
