# Adding an event

```bash
ws add event Example Workshop 2026 --type workshop \
  --start 2026-09-14 --end 2026-09-16 --timezone Europe/Berlin \
  --location "Konstanz, Germany" --status planned --ensure \
  --source "workshop website" --observed-at 2026-10-28
```

The title's words are joined, so quotes are optional. ws prints the REF,
`created: event:example-workshop-2026`. What an event record holds is in
`ws help events`.

On a terminal, ws asks for whatever the flags left empty: the title, then
aliases, a description, start, end and location; Enter skips each. The
time zone and type are taken only as flags. `--non-interactive`, `--json`
or running without a terminal never asks.

## Dates

`--start` and `--end` take an ISO date, `2026-09-14`, or a date-time,
`2026-09-14T09:30`. ws checks both before writing anything: a malformed
date, or a start after the end, stops the command, typed answers to the
prompts included. `--timezone` takes an IANA name such as `Europe/London`
and is stored as given.

## Search first, or ensure

Without `--ensure`, every call creates an event. With it, an existing event
is reused when its name or an alias matches, ignoring case and spacing,
and, when `--start` is given, its start falls on the same day. An ensure
for next year's edition, with its own start date, therefore creates a new
event rather than returning last year's. Put the year in the name all the
same: `ws check logistics` warns about two events sharing a name.

A record without a start never matches an ensure that passes `--start`.
When an earlier record lacks its date, find it with `ws search events`
and complete it with `ws edit event:<key> --start <date>` instead.

On a match ws prints `exists: event:<key>`. The facts you pass fill only
fields that are still empty and new aliases are added; the name and status
stay as they are, so a status change goes through `ws edit`. When more than
one event matches, ws names them and writes nothing.

`--source` and `--observed-at` record where the facts came from and when,
as a provenance entry naming the fields they set.

## Then relate

Adding relates nothing. Connect the event with the REF ws printed:

```bash
ws relate person:<key> to event:example-workshop-2026 as attended
ws relate document:<key> to event:example-workshop-2026 as produced-for
```

`ws help relate` covers choosing words. An event recorded twice anyway is
merged, not deleted (`ws help logistics`).
