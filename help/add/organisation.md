# Adding an organisation

```bash
ws add organisation Example Institute --alias EXI --type university \
  --website https://www.example.org --ensure \
  --source "example.org about page" --observed-at 2026-10-28
```

The name's words are joined, so quotes are optional. ws prints the REF,
`created: organisation:example-institute`. What an organisation record
holds is in `ws help organisations`.

On a terminal, ws asks for whatever the flags left empty: the name, then
aliases, a description, a type and a website; Enter skips each.
`--non-interactive`, `--json` or running without a terminal never asks.

## Name it once, alias the rest

Use the full name as the name and give abbreviations and former names as
aliases. Search and `--ensure` both match aliases, so the next mention of
`EXI` finds the record instead of creating a second one.

The type is a free word; there is no taxonomy command for organisations.
Reuse the word that similar organisations already carry, for example
`company`, `university`, `college` or `society`.

## Search first, or ensure

Without `--ensure`, every call creates an organisation. With it, an
existing one is reused when either matches:

```text
name      the name or an alias, ignoring case and spacing
website   the --website, when one is given
```

The website is compared as written, ignoring only case and spacing, so
`https://www.example.org` and `example.org` do not match. Write websites
one way throughout, or rely on the name and aliases to match.

On a match ws prints `exists: organisation:<key>`. The facts you pass fill
only fields that are still empty and new aliases are added; the name and
status stay as they are. When more than one record matches, ws names them
and writes nothing.

`--source` and `--observed-at` record where the facts came from and when,
as a provenance entry naming the fields they set.

## Then relate

Adding relates nothing. Connect the organisation with the REF ws printed:

```bash
ws relate person:<key> to organisation:example-institute as works-at
ws relate project:<key> to organisation:example-institute as prepared-for
```

`ws help relate` covers choosing words. An organisation recorded twice
anyway is merged, not deleted (`ws help logistics`).
