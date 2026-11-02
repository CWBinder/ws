# Creating a profile record

```bash
ws create profile BSc Physics --type education \
  --subtitle "University of Example" --start 2013-10 --end 2017-03
```

Each record is one career fact: a degree, a position, a talk, a skill. The
name's words are joined, so quotes are optional; the key is the name in
lowercase with hyphens, and the command prints the REF. What the types and
fields mean, and how CVs are made from them, is in `ws help profile`.

A name and a type are required. On a terminal, a missing name is asked for,
and a missing type is asked for with the allowed types listed. Without a
terminal, as when an agent runs ws, a missing name or `--type` is an error.
An unknown type is refused; extend the list first with
`ws profile add-type TYPE`. A unique prefix stands for a type.

Only facts the person supplied or verified belong here. Write the record
once in reusable words; wording for one application goes in that
application's CV spec, not into the record.

## Dates

`--start` and `--end` take `YYYY`, `YYYY-MM` or `YYYY-MM-DD`, and `--end`
also takes `present` for something ongoing. Anything else is refused. A
start without an end shows on the CV as an open range; `--year` suits a
single date such as a publication or an award.

## The identity

```bash
ws create profile Alex Example --type identity \
  --headline "Physicist and software developer" \
  --email alex@example.org --orcid 0000-0002-1825-0097
```

There is at most one identity, and every CV needs it. Creating a second is
refused; `--ensure` with the existing identity's name or one of its aliases
returns it instead. `--email`, `--phone`, `--address` and `--link` repeat;
more can be added later with `ws edit profile:<key>`. The CV header shows
the first email, phone and address.

## Avoiding duplicates

`--ensure` returns an existing record of the same type whose name or one
of whose aliases matches, ignoring case, and fills in fields it does not
have yet, instead of creating a second record. Search first otherwise:

```bash
ws list profile --type talk
ws search profile <words>
```

## Relating the new record

Creating a record relates it to nothing. The CV reads three relations:

```bash
ws relate profile:<key> to organisation:<key> as at
ws relate profile:<key> to event:<key> as presented-at
ws relate profile:<key> to literature:<key> as represents
```

`at` names the organisation of a position, degree or award; `presented-at`
the event of a talk. A publication that `represents` a literature item
takes its citation from that item. Without one, give the publication its
own `--author`, `--venue`, `--year` and `--doi` or `--isbn`, which the CV
uses instead. Create or find the other end first.

## Examples

A position with achievement lines, then its employer:

```bash
ws create profile Research Intern --type work-experience \
  --subtitle "Example Labs" --start 2024-06 --end 2024-09 \
  --bullet "Built the simulation pipeline for the device team" \
  --bullet "Cut run times by a factor of four"
ws relate profile:<key> to organisation:<key> as at
```

A degree that was left unfinished:

```bash
ws create profile MSc Computing --type education \
  --subtitle "Example University" --start 2018 --end 2019 \
  --qualification-status "programme not completed"
```

A publication whose citation comes from the library:

```bash
ws create profile "Paper title" --type publication
ws relate profile:<key> to literature:<key> as represents
```

A skill, described once for every CV:

```bash
ws create profile Python --type skill \
  --description "Scientific computing, packaging and testing"
```
