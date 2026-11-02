# People

A person record is someone you deal with: a colleague, a collaborator, a
supervisor, a contact at a company or a speaker you met. It holds who they
are and how to reach them. Where they work, what they attended and what
they work on are relations, not fields.

People belong to the logistics domain with organisations and events
(`ws help logistics`). To record someone, read `ws help add person`.

## Where people live

```text
~/workspace/logistics/people/<key>.yaml    one record per person
```

The key is the name slugified when the person is added: `Maria Schwarz`
becomes `person:maria-schwarz`, and a second person of the same name gets
`maria-schwarz-2`. Renaming changes the display name, never the key.

## Fields

`name`, `aliases`
: The display name, and other spellings to find them by: a maiden name, a
  transliteration, a nickname, a common misspelling.

`preferred_name`
: How to address them, such as a first name or a nickname.

`emails`, `phones`
: Lists; a person may have several of each.

`description`
: One or two sentences on who they are to you.

`owner`
: Set on one person only: the one whose workspace this is, with
  `--owner`. `ws help owner` says what it does.

`status`
: Optional, and absent means active. `merged` marks a duplicate folded into
  another record.

`provenance`
: Which source asserted which fields, and when, one entry per change made
  with `--source` or `--observed-at`.

`id`, `key`, `kind`, `schema_version`, `created_at`, `updated_at`
: Bookkeeping, written by ws.

## Finding someone

```bash
ws search people maria
ws search people maria@example.org
ws show person:maria-schwarz
```

Search looks at the name, aliases and key and at every other field, so an
email address, a phone number or a word from the description finds the
person too. `ws show` prints the record and every relation, each with the
other end's REF.

## Connections

What a person is to the rest of the workspace is recorded as relations.
Run `ws relations` to see the words in use; for people these are typically:

```text
person --works-at-->      organisation
person --member-of-->     organisation
person --attended-->      event
person --organised-->     event
person --works-on-->      project
person --co-authored-->   literature
person --supervises-->    person
```

A position that started or ended at a known date carries it on the edge:

```bash
ws relate person:maria-schwarz to organisation:<key> as works-at --from 2024-10-01
```

When she moves on, end that edge rather than deleting it, since an ended
relationship is still true history:

```bash
ws edit relation:<id> --until 2026-09-30
```

`ws show person:maria-schwarz` lists each edge with its REF. Choosing the
words is covered in `ws help relate`.

## Keeping contact details current

```bash
ws edit person:maria-schwarz --add-email maria@new.example.org \
  --remove-email maria@old.example.org \
  --source "email signature" --observed-at 2026-10-28
```

Each edit that passes a source or date adds a provenance entry naming the
fields it changed. `ws check logistics` warns about people with emails or
phones whose record has not changed for 180 days.

## Duplicates and removal

The same person recorded twice is merged, not deleted, so their relations
move to the record you keep:

```bash
ws logistics people merge person:maria-schwarz-2 --into person:maria-schwarz
```

Read `ws help logistics` before merging: only names and relations are
carried over. `ws delete person:<key>` is for a record that should not
exist; it removes the record and every relation on it, and nothing goes to
the Trash. `--dry-run` shows how many relations would go.
