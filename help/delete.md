# Deleting objects and relations

```bash
ws delete document:<key> --dry-run
ws delete document:<key>
```

Delete removes records outright, and with each object every relation
touching it, so no edge is left pointing at nothing. One call may name
several REFs of different kinds. Run it with `--dry-run` first: it names
each object, how many relations go with it, and what moves to the Trash,
without changing anything.

## What happens to the content

Safety comes from recoverability rather than from questions:

```text
person, organisation, event,      the record is removed
task, profile
document                          the record is removed; a file kept in
                                  documents/files/ goes to the Trash, a
                                  file referenced in place is left alone
resource, literature, project     the whole folder, record included, goes
                                  to the Trash
relation                          the edge is removed
```

The Trash is `~/.Trash`. Where that folder does not exist, as on most Linux
systems, a document's file or an object's folder is removed for good. The
relations of a deleted object never go to the Trash: look at them with
`ws show REF` before deleting if you may want any back.

`ws delete relation:<id>` removes one edge and prints the `ws relate`
command that would restore it. ws keeps no history of edges, so that line
is the way back. Every relation REF in a call must resolve before any edge
goes, so a typo in the second cannot leave the first half done.

## What delete refuses

The Trash cannot undo breakage elsewhere, so delete refuses, before
anything moves:

- a project that another project installs as a package or depends on,
- a project that holds subprojects; delete those first,
- a literature item that supplies the citation of a profile publication;
  delete that `represents` edge first.

Deleting a project also warns about git work that exists only in its
folder: uncommitted changes, and history that no remote holds.

## Delete, archive or merge

Delete says "this should not exist". Other situations have their own
commands:

```bash
ws edit project:<key> --status archived       # finished, keep it
ws edit relation:<id> --until 2026-06-30      # a relationship that ended
ws logistics people merge <duplicate> --into <canonical>
```

A merge says "duplicate": the duplicate's relations move to the canonical
record, its name and aliases become aliases there, and a `merged` tombstone
remains that redirects to it. Organisations and events merge the same way
under `ws logistics`.

After a delete, the browse folders of that kind are rebuilt.
