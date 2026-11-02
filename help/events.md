# Events

An event is something that happens at a time and place: a conference, a
workshop, a talk, a seminar, a visit, a dinner, a hackathon. The record
holds when and where. Who attended or organised it, and what was presented
or spent there, are relations.

Events belong to the logistics domain with people and organisations
(`ws help logistics`). To record one, read `ws help add event`.

## Where events live

```text
~/workspace/logistics/events/<key>.yaml    one record per event
```

The key is the name slugified when the event is added. Each edition of a
recurring event is its own event, so put the year or date in the name:
`Example Workshop 2026` becomes `event:example-workshop-2026` and
stays apart from the 2025 edition. Renaming changes the display name,
never the key.

## Fields

`name`, `aliases`
: The display name, and other names to find it by, such as an acronym or
  the full title.

`type`
: A free word such as `conference`, `workshop`, `talk` or `visit`. There
  is no taxonomy for event types: reuse the word similar events already
  carry. `ws list events --type conference` lists one type.

`start`, `end`
: ISO dates, or date-times; the start may not be after the end. A one-day
  event may leave out the end.

`timezone`
: The IANA name of the event's local time zone, such as `Europe/London`.

`location`
: The place, as free text.

`description`
: One or two sentences on what it is and what it means to you.

`status`
: A free word, written only when set; absent means active. Words such as
  `planned`, `completed` and `cancelled` say where the event stands.
  `merged` marks a duplicate folded into another record.

`provenance`
: Which source asserted which fields, and when.

`id`, `key`, `kind`, `schema_version`, `created_at`, `updated_at`
: Bookkeeping, written by ws.

## Past and coming events

```bash
ws list events --upcoming
ws list events --year 2026
ws edit event:<key> --status completed
```

`--upcoming` and `--past` compare the start date with today, so an event
without a start shows in neither. Bare `ws context` at the workspace root
lists the events that are on now or start within the next fourteen days.

Once an event is over, give it a status that says so. `ws check logistics`
warns about a past event whose status is still empty, `active`,
`tentative` or `confirmed`.

## Connections

Run `ws relations` to see the words in use; around events these are
typically:

```text
person       --attended-->       event
person       --presented-at-->   event
person       --organised-->      event
organisation --organised-->      event
document     --produced-for-->   event
resource     --expense-for-->    event
event        --part-of-->        event
```

`part-of` ties a satellite meeting or a session to the main event. Any edge
to an event also files the other object under the event's name in the
`by-event/` browse folders: by default those of projects, documents and
resources. Document folders follow at once, the others at the next
`ws rebuild views`. See `ws help relate` for choosing words.

## Duplicates and removal

An event added twice is merged into the record you keep:

```bash
ws logistics events merge event:<duplicate> --into event:<key>
```

Read `ws help logistics` before merging: only names and relations are
carried over, so copy any dates or location that only the duplicate holds
first. `ws delete event:<key>` is for a record that should not exist; it
removes the record and every relation on it. A cancelled event is better
kept with the status `cancelled`.
