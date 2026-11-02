# Checking the workspace

```bash
ws check
ws check relations
```

Check validates the workspace and reports what it finds. It never repairs,
rewrites or deletes anything, so it is always safe to run. Bare `ws check`
covers every area; name one area to check only that.

Run it after `ws init`, after changing a taxonomy or `folder-anatomy.yaml`,
after updating ws, and whenever something looks wrong.

## Reading the result

Each finding is one line, `severity: area: id message`, and an area with
nothing to report prints `ok: area`. Errors make the exit status 1;
warnings do not. `--json` prints `{"ok": ..., "checks": {...}}` with the
findings of each area.

A finding names the problem and often the command that fixes it, such as
`ws rebuild index` for a stale index. Fix the cause with ws, then check
again.

## The areas

`workspace`
: The required folders exist, and ws's own files are installed.

`projects`
: Each project's files, git repository, sync settings and references, as
  `ws projects check` reports them; its problems count as errors and its
  notes as warnings.

`catalog`
: Every record of the record kinds: well-formed, filed under its key, and
  free of duplicate names or aliases. A document's type must be known and
  its file present; a profile object's type must be known; a past event
  should no longer be active. `tasks`, `documents`, `resources` and
  `logistics` run the same checks for those kinds only, and `documents`
  adds the document taxonomy.

`literature`
: Fields and subfields from the taxonomy, and no empty citation files.

`profile`
: The profile taxonomy and records, and folders left over from the older
  profile layout.

`relations`
: Both endpoints of every edge resolve, no edge points at its own subject,
  dates are valid and in order, and no edge is repeated.

`anatomy`
: `folder-anatomy.yaml` is a valid browse settings file
  (`ws help rebuild views`).

`index`
: The search index exists and holds exactly the current records and
  relations.

`cli`
: The CLI's own surface: every command and flag has help, every writing
  command declares what it changes, no help text teaches a spelling that
  no longer parses, every manual page documents something that exists and
  refers only to pages that do, and an installed shell completion script
  is current (`ws help completions`). It reads no workspace, so it also
  passes on an empty one.

`--stale-after DAYS` (180 by default) sets when a person's contact details
count as old: a person with emails or phones whose record has not been
updated for longer gets a warning.
