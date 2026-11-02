# Adding a person

```bash
ws add person Maria Schwarz --email maria@example.org --ensure \
  --source "email from Maria Schwarz" --observed-at 2026-10-28
```

The name's words are joined, so quotes are optional. ws prints the REF,
`created: person:maria-schwarz`, which the next command needs. What a
person record holds is in `ws help people`.

On a terminal, ws asks for whatever the flags left empty: the name, then
aliases, a description, a preferred name, emails and phones. Lists are
comma-separated and Enter skips. `--non-interactive`, `--json` or running
without a terminal never asks: what the flags leave out stays empty.

## Search first, or ensure

Without `--ensure`, every call creates a person, so adding Maria twice
gives `person:maria-schwarz` and `person:maria-schwarz-2`. Search first,
or let `--ensure` do it. With `--ensure`, an existing person is reused
when either matches:

```text
name     the name or an alias, ignoring case and spacing
email    the first --email, against every email on record
```

On a match ws prints `exists: person:<key>`. The facts you pass fill only
fields that are still empty, and new aliases, emails and phones are added
to the lists. The name and status stay as they are, and a new spelling of
the name is not kept unless you pass it as `--alias`. When more than one
person matches, ws names them all and writes nothing; pick the right REF
and use `ws edit`.

## The owner

`--owner` labels this person as the one whose workspace this is. At most one
person carries it; `ws help owner` explains what it does. `ws setup` normally
makes this record.

## Record where the facts came from

`--source` says who or what stated the facts: an email, a website, a
conversation. `--observed-at` says when, as an ISO date. Together they make
a provenance entry that names the fields they set, so later readers know
which detail came from where. Without them no entry is written.

## Then relate

Adding relates nothing. Connect the person right after, with the REF ws
printed:

```bash
ws relate person:maria-schwarz to organisation:<key> as works-at
ws relate person:maria-schwarz to event:<key> as attended
```

`ws help relate` covers choosing words. A person recorded twice anyway is
merged, not deleted (`ws help logistics`).
