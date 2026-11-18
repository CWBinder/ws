# Creating a project

```bash
ws create project my project
```

In a terminal, a bare name opens the setup wizard, described below. Pass
`--non-interactive` for the default scaffold without questions, or
`--interactive` to get the wizard where it would not start on its own.
Without a terminal, as when an agent runs ws, the wizard never starts:
pass everything as flags.

Names become lowercase kebab-case folder names: `my project` becomes
`my-project`. What a project is, and the layout it gets, is in
`ws help projects`.

## Where it is created

```text
--in DIR             this folder, for this run
WS_PROJECTS_DIR      this folder, whenever the variable is set
otherwise            projects/items/ in the workspace
```

The workspace is `~/workspace` unless `ws init` or an environment variable
says otherwise (`ws help configuration`).

## What it creates

Always: `project.yaml`, `README.md`, `AGENTS.md`, a `CLAUDE.md` symlink to
it, `.context/log.md` with a first entry, `.context/purpose.md`, `.gitignore`,
a git repository, and the `in/` and `out/` folders.

`.context/purpose.md` is the one home of the project's purpose: the README
points there, and `project.yaml` keeps no copy. It holds the
`--description` text, or without one a placeholder that `ws context`
reports as not set yet. Either way the purpose is the person's: fill it
from what they said, or ask them.

The command ends with the next steps for whoever ran it, often an agent:

```text
Next, before any other work:
  purpose   not set. Ask the person what this project is for and write their
            words into .context/purpose.md. Never invent it.
  log       after each piece of work, add an entry at the top of .context/log.md.
  briefing  run now: ws context project:my-project  (house rules and this project's context)
```

With `--description`, the purpose line quotes what `.context/purpose.md`
now holds instead, and asks whoever ran the command to show it to the
person and correct it if these are not the person's own words. An agent
that wrote or reworded the description should do exactly that.

With a capability, its folder and setup:

```text
--has-code      code/
--has-data      data/
--has-paper     paper/
--python        pyproject.toml; implies --has-code
--venv          .venv; implies --python
--has-slides    slides/, and the slide_factory deck generator installed
                into .venv with any configured theme packages; implies --venv
--use-project   another workspace project, installed editable into .venv
```

None of this is creation-only. `ws projects install` adds any capability or
dependency later (`ws help projects install`).

## The wizard

Every project is asked the same metadata first:

```text
Name          folder name; words are slugified
Title         defaults to the title-cased name
Type          a taxonomy type; defaults to the first one (research)
Purpose       in the person's words, into .context/purpose.md;
              Enter leaves it not set
Fields        comma-separated, from the taxonomy
Subfields     comma-separated, only those of the chosen fields
Keywords      comma-separated, free-form
```

Constrained choices print their allowed values and are checked at once; an
unknown type, field or subfield offers to extend the taxonomy. Status and
hosts are not asked; set them with flags.

The type then decides which setup questions follow:

```text
type                     code+python+venv  paper  data  slides  server
research                 asked             asked  asked asked   asked
exploration              asked             asked  -     asked   asked
paper                    asked             yes    -     -       -
software                 asked             -      -     -       -
talk, teaching           -                 -      -     asked   -
organizatorial, other    -                 -      -     -       -
any other type           asked             asked  asked asked   asked
```

"Any other type" covers types added with `ws projects add-type` that the
wizard has no routing for; they get every question. The routing lives in
`TYPE_QUESTION_SETS` in `cli/ws_lib/project.py`.

The code questions cascade. `Has code` comes first; `Python project`
defaults to yes when the project has code, and `Create Python virtual
environment` defaults to yes for a Python project. Only once a venv is
chosen does the wizard ask whether to install another workspace project
into it. That prompt takes `y`, after which it asks for the REF, or the REF
itself:

```text
Install another workspace project into this venv [n]: project:virtuallab
Found Python package:
  ~/Projects/virtuallab/pyproject.toml
Editable install command:
  .venv/bin/python -m pip install -e ~/Projects/virtuallab
Run this after creating the venv [y]:
```

Slides need the venv, so answering yes to slides creates one; a talk's
slides question defaults to yes. A question the type skips stays off.

## Examples

A paper project with its classification:

```bash
ws create project tax-paper --title "Tax Paper" --type paper \
  --description "Draft and analysis for the tax paper." \
  --field physics --subfield numerics --keyword tax --has-paper
```

A Python project with its own environment:

```bash
ws create project code-tool --python --venv
```

A project that installs another workspace project into its environment:

```bash
ws create project experiment --python --venv \
  --use-project project:potential-generator-toolkit:package
```

`--field`, `--subfield`, `--keyword`, `--use-project` and `--host` repeat.
Conceptual links are not creation flags: relate the finished project with
`ws relate project:<key> to <ref> as depends-on`, or any other words
(`ws help relate`).
