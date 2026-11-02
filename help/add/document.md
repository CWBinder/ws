# Adding a document

```bash
ws add document ~/Downloads/venue-invoice.pdf --type invoice --date 2026-07-15
```

Adding a document takes one file into the workspace, writes its record and
rebuilds the document views. It prints the new REF; use that REF to relate
the document afterwards, since adding relates nothing. What a document is,
and how it is classified, is in `ws help documents`.

## What happens to the file

```text
--mode move        the default: the file moves into documents/files/
--mode copy        a copy goes into documents/files/; the original stays
--mode reference   the file stays where it is; the record points at it
```

Moving makes the workspace the file's only home. Copy when the original
must stay, for example in a project's `out/` or an application folder.
Reference only a file that is too large to take in and that will stay
reachable at the same path, such as one on an external disk: if it moves,
the record points at nothing and the document drops out of the views.

`documents/files/` is flat, so two files with the same name cannot both be
filed. Adding a file whose name is already taken there is refused, and
nothing is moved; rename the file first. `--name` changes only the
document's name in its record, not the file name.

## Type and date

On a terminal, a missing type and date are asked for. The type prompt
prints the allowed types and completes them with Tab; an unknown value
offers to extend the taxonomy, and an empty answer leaves the document
unclassified. The date prompt takes `YYYY-MM-DD`; an empty answer leaves
the document in the `unclassified/` folder of the year view. A missing file
argument is asked for first.

Without a terminal, as when an agent runs ws, or with `--non-interactive`,
nothing is asked. A type or date you leave out stays empty, and an unknown
`--type` fails unless `--add-type` is given as well. Scripts never extend
the vocabulary by accident. A unique prefix such as `pr` is accepted for
`presentation`.

Set both later with `ws edit document:<key> --type TYPE --date DATE`.

## Adding the same file twice

`--ensure` makes add idempotent by path: when the stored path of exactly
one existing record matches, that record is returned instead of a new one
being created. With the default move or copy, the stored path is
`files/<file name>`; if a file of that name is already there with the same
contents, `--ensure` adopts it and returns its record. Records hold no
checksum, so the same contents under another file name count as a new
document: search before you add.

## Examples

An invoice, kept as a copy, signed with where it came from:

```bash
ws add document ~/Downloads/invoice-2026-07.pdf --type invoice \
  --date 2026-07-15 --mode copy --non-interactive \
  --source "email from the venue" --observed-at 2026-07-16
ws relate document:<key> to organisation:<key> as issued-by
```

A recording too large to move, referenced where it lies:

```bash
ws add document /Volumes/Archive/talk-recording.mp4 --type presentation \
  --mode reference --name "Colloquium talk recording"
```

A type the taxonomy does not have yet, added in the same step:

```bash
ws add document ~/Downloads/statement.pdf --type bank-statement --add-type
```

Then check the result:

```bash
ws show document:<key>
```
