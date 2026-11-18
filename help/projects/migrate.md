# Migrating project context

Every project keeps its context in `.context/`: the purpose in
`.context/purpose.md`, the log in `.context/log.md`. Projects from before
kept the log in a root `LOG.md`, the purpose in the README's Purpose
section, and a copy of it as `description` in `project.yaml`. Migrate moves
them, and shows what it would do first.

```bash
ws projects migrate
ws projects migrate --apply
ws projects migrate project:<key> --apply
```

Without `--apply` nothing is written: you get the plan, project by project.
With it, the same changes are made and reported. Without a REF it covers
every project and subproject.

## What it changes

```text
a root LOG.md               moves to .context/log.md, unchanged
no .context/purpose.md      written from README.md's Purpose section,
                            verbatim, or else from project.yaml's
                            description; a placeholder when there is neither
README.md's Purpose         replaced by a pointer to .context/purpose.md
                            when it says the same, so the purpose has one home
project.yaml's description  removed when it is the old placeholder, or when
                            .context/purpose.md or the README says the same
                            (also subproject.yaml's)
AGENTS.md, README.md        the template lines that named LOG.md now name
                            .context/
no log at all               .context/log.md with a first entry
```

It moves and copies, removes only a copy whose text stays elsewhere, and
never merges text. Each change shows in
the project's own `git status`, and restoring the files undoes it. A second
run changes nothing.

## What it leaves for you

Some things need a person, so migrate lists them and leaves them as they
are:

- a log in both places: merge `LOG.md` into `.context/log.md`, then delete it;
- a README Purpose section that differs from `.context/purpose.md`: settle
  the purpose with its owner, keep it in `.context/purpose.md`, and point
  the README there;
- a `description` in `project.yaml` that differs from both: it may be the
  oldest wording, so settle the purpose with its owner first, then delete
  the key;
- other lines that still name `LOG.md`, such as a hand-written rule.

`ws projects check` reports a project that still needs migrating, and a
purpose that is not set yet.
