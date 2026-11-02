# Logistics

Logistics is the domain of who and what you deal with: people,
organisations and events, each kept as one plain record per object. Every
kind has its own page, `ws help people`, `ws help organisations` and
`ws help events`, and connecting them is covered in `ws help relations`.

## Where it lives

```text
~/workspace/logistics/
  people/<key>.yaml          one record per person
  organisations/<key>.yaml   one record per organisation
  events/<key>.yaml          one record per event
  communications/            templates, styles and reference material
```

The records are written only by ws. To keep a store somewhere else, see
`ws help configuration`.

These things already exist in the world, so they are added, not created:
`ws add person`, `ws add organisation`, `ws add event`. They are shown,
edited and deleted by REF like every other object. The `ws logistics`
command holds only what exists for these kinds alone: `ensure` and `merge`
for each kind, and the communications folder.

## Ensure: get or create

```bash
ws logistics people ensure Maria Schwarz --email maria@example.org
```

`ensure` is `ws add ... --ensure` without prompts, printing only the REF,
which suits scripts. When exactly one existing record matches, ws returns
it instead of creating a duplicate. What counts as a match:

```text
person         same name or alias, or the same email as the first --email
organisation   same name or alias, or the same website when --website is given
event          same name or alias, and the same start date when --start is given
```

Names and aliases are compared ignoring case and spacing. On a match, the
facts you pass fill only fields that are still empty; new aliases, emails
and phones are added to the lists. Name and status are never changed this
way. When more than one record matches, ws names them and writes nothing.

## Merge: fold in a duplicate

When the same person, organisation or event was recorded twice, merge the
duplicate into the record you keep:

```bash
ws logistics people merge person:maria-schwarz-2 --into person:maria-schwarz --dry-run
ws logistics people merge person:maria-schwarz-2 --into person:maria-schwarz
```

Merge moves every relation of the duplicate onto the kept record, dropping
any that the kept record already has, and adds the duplicate's name and
aliases to the kept record's aliases, so a search for either name finds it.
The duplicate stays on disk as a tombstone with status `merged` and a
pointer to the kept record. It no longer appears in lists or searches, and
its REF stops resolving.

Merge carries over names and relations only. Emails, phones, a website,
dates or a description that only the duplicate holds are lost from view, so
copy them first with `ws edit`. Both REFs must be of the same kind.

Merge says "this is a duplicate". Delete says "this should not exist": it
removes the record and its relations, and leaves nothing behind.

## Checks

```bash
ws check logistics
ws check logistics --stale-after 365
```

The check reports records whose file name does not match their key, two
records of a kind sharing a name or alias, a past event whose status is
still empty, `active`, `tentative` or `confirmed`, and people with emails
or phones whose record has not changed for 180 days, or for
`--stale-after` days. It reports and never repairs.

## Communications

`communications/` holds material for writing to people: templates, styles
and reference texts. ws reads it and never writes it:

```bash
ws logistics communications list
ws logistics communications show <path>
ws logistics communications path
```

`show` takes a path relative to the folder, as `list` prints it.
