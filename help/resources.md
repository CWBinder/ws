# Resources

A resource is a bundle: one folder of supporting files that belong
together and need only one identity between them, such as the receipts of
one reimbursement, the material of one application or the handouts of one
workshop. The folder is the object; what is inside it is ordinary files.

Choose the kind by what needs addressing on its own:

```text
resource      files that matter together, under one identity
document      one file to show, classify and relate by itself
project       structured ongoing work with its own workflow
literature    one bibliographic work
profile       one reusable fact for your CV
```

To start a bundle and put files into it, read `ws help create resource`.

## Where resources live

```text
~/workspace/resources/
  items/<key>/                one folder per bundle
    resource.yaml             the record
    .context/                 optional notes: purpose.md, log.md
    <files and folders>       the contents, in any structure
  by-organisation/  by-project/  by-event/
                              derived browse views, rebuilt by ws
```

The folder name is the key and the REF is `resource:<key>`. The contents
have no required structure, and the files in them have no records, no REFs
and no relations of their own: everything attaches to the bundle. Search
indexes the files' relative paths, so searching for a file name finds the
bundle that holds it, once.

## Fields of resource.yaml

`name`, `aliases`
: What search finds the bundle by. Renaming changes the name, not the key
  or the folder.

`description`
: A sentence or two on what the bundle holds.

`status`
: A free lifecycle word such as `open` or `draft`; absent means active.

`provenance`
: Who or what asserted the facts, and when.

`created_at`, `updated_at`
: `updated_at` also moves whenever a file is added to the bundle.

Change the record with `ws edit resource:<key>`. Resources have no type and
no other classifier; they are placed by their relations.

## Working in a bundle

Files inside an existing bundle may be added, replaced and deleted directly;
only a new bundle (`ws create resource`) and its record (`ws edit`) need ws.
`ws add resource:<key> PATH` is the convenient way to bring a file in from
elsewhere: it also stamps `updated_at` and refreshes search. After changing
files by hand, run `ws rebuild index` so search finds them. The `.context/`
notes are edited directly too: `purpose.md` says what the bundle is for and
`log.md` what has happened, newest entry first. A bundle that keeps
growing, such as an application in progress, benefits from both.
`ws show resource:<key>` summarises them under the record, and
`ws context resource:<key>` gives the full briefing (`ws help context`).

```bash
ws resources files resource:<key>
ws resources path resource:<key>
ws relate resource:<key> to project:<key> as supports
ws relate resource:<key> to organisation:<key> as expense-for
```

`files` lists the contents relative to the folder, `path` prints the
folder itself. Relation words are free; `ws relations` lists those already
in use.

## Browse views

Resources are browsed by their related organisations, projects and events,
one level deep:

```text
by-organisation/<organisation name>/<key>
by-project/<project title>/<key>
by-event/<event name>/<key>
```

Each entry is a symlink to the bundle's folder. Creating a bundle or
relating it does not refresh these folders; run
`ws rebuild views resources` to bring them up to date.

## Documents and bundles

A document can be retired into a bundle when it no longer needs its own
record. Note its file path and relations with `ws show document:<key>`,
move the file into the bundle, then delete the old record:

```bash
ws add resource:<key> ~/workspace/documents/files/handout.pdf \
  --name handouts/handout.pdf
ws delete document:<key> --dry-run
ws delete document:<key>
```

Deleting the record removes its relations; moving the file does not carry
them over. Relate the bundle again where a connection still matters.

The other direction is just as deliberate: when a file in a bundle needs
its own identity, register it with `ws add document`
(`ws help add document`). The file then moves out of the bundle into the
documents store, unless you add it with `--mode copy`. Neither direction
ever happens automatically, and neither is inferred from a file's type.

## Removing a bundle

```bash
ws delete resource:<key> --dry-run
ws delete resource:<key>
```

The whole folder, record and contents, goes to the Trash, every relation
of the bundle is removed, and the views are rebuilt. Read the dry run
first.
