# Organisations

An organisation is an institution, company, university, college, society,
funder or agency you deal with. The record holds what it is and where to
find it online. Who works there, what it organised and which documents it
issued are relations.

Organisations belong to the logistics domain with people and events
(`ws help logistics`). To record one, read `ws help add organisation`.

## Where organisations live

```text
~/workspace/logistics/organisations/<key>.yaml    one record per organisation
```

The key is the name slugified when the organisation is added, so
`Example Institute` becomes `organisation:example-institute`. Renaming
changes the display name, never the key.

## Fields

`name`, `aliases`
: The display name, and other names to find it by. Abbreviations and
  former names belong here: an alias `EXI` lets search and `--ensure` find
  Example Institute.

`type`
: A free word for what kind of organisation it is, such as `company`,
  `university`, `college`, `society` or `agency`. There is no taxonomy
  for organisation types: reuse the word similar organisations already
  carry, and `ws list organisations --type company` lists one type.

`website`
: The organisation's address on the web.

`description`
: One or two sentences on what it is to you.

`status`
: Optional, and absent means active. `merged` marks a duplicate folded into
  another record.

`provenance`
: Which source asserted which fields, and when.

`id`, `key`, `kind`, `schema_version`, `created_at`, `updated_at`
: Bookkeeping, written by ws.

## Connections

Organisations are never classifiers of other objects: a project for a
company, or an invoice from a university, is related to the organisation.
Run `ws relations` to see the words in use; around organisations these are
typically:

```text
person       --works-at-->          organisation
person       --member-of-->         organisation
document     --issued-by-->         organisation
document     --submitted-to-->      organisation
organisation --organised-->         event
organisation --collaborates-with--> organisation
```

Any edge to an organisation, whatever its words and direction, also files
the other object under the organisation's name in the `by-organisation/`
browse folders: by default those of projects, documents, resources and the
profile. Document folders follow at once, the others at the next
`ws rebuild views`. See `ws help relate` for choosing words.

## Duplicates and removal

An organisation added twice, say once by its abbreviation and once by its
full name, is merged into the record you keep; the abbreviation becomes an
alias:

```bash
ws logistics organisations merge organisation:<duplicate> --into organisation:<key>
```

Read `ws help logistics` before merging: only names and relations are
carried over. `ws delete organisation:<key>` is for a record that should
not exist; it removes the record and every relation on it.
