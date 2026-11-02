# Showing objects

```bash
ws show person:<key>
```

Show prints an object's record, where its content lives, and every relation
touching it, so the graph around an object comes without a second command.
Read the full content at the path it names: a document's file, a project's
folder, a literature item's folder.

Show takes full REFs only, `kind:key`. Names, titles, aliases, DOIs and
internal IDs are search terms, never operands: find the REF with
`ws search` first (`ws help search`) and use exactly what it returns.
Several REFs may follow one `show`, of any kinds; they print one after the
other.

Projects and literature print richer views than the other kinds: a project
adds its folder, dependencies and subprojects, a literature item its folder,
citation data and which of its files are present (PDF, source, summary,
notes). A folder-backed object also gets a `purpose:` line
(the first paragraph) and a `log:` line (entry count and latest heading)
once its `.context/` folder holds those notes (`ws help context`).

## Relations

Every edge prints on one line, starting with its own REF:

```text
relations: 2
  relation:01KYTNTBD9T7K071PSJ568ZDZ8  --belongs-to--> project:first-project (First Project)
  relation:01M2ZN0XKW2T4CMR3G59W68H1F  <--presents-- event:<key> (Workshop)
```

`-->` leaves the object and `<--` arrives at it. `--as WORD` narrows the
list to one relation word. The edge's REF works like any other:

```bash
ws show relation:<id>      # the edge in full: direction, dates, source, history
ws edit relation:<id> --until 2026-06-30
ws delete relation:<id>
```

How edges are made and named is in `ws help relations`.

## One aspect in full

```bash
ws show purpose of project:<key>
ws show log of project:<key>
ws show location of project:<key>
ws show instructions of project:<key>
```

An aspect takes exactly one REF, and `of` may be left out. `purpose` adds
the chain of purposes the object serves, `log` prints every entry, and
`location` the whereami notes from the root down, the object's neighbours
and what is coming up. `ws context REF` prints all of them as one briefing
(`ws help context`).

## For programs

`--json` prints one object for one REF and a list for several. Each object
carries its relations, and `purpose` and `log` keys where the notes exist.
