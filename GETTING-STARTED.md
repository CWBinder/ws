# Getting started

This guide works for a person at a terminal or an agent assisting them.
Use the defaults first; no personal profile or category customisation is needed.

## 1. Install

Install Git and Python 3.10 or newer, including Python's `venv` support. On
Linux distributions that package it separately, install the matching
`python3-venv` package. Check `python3 --version` before continuing.

```bash
git clone https://github.com/CWBinder/ws.git ~/Projects/ws
cd ~/Projects/ws
python3 install.py
```

The installer creates a local `.venv`, installs ws with pip, and puts a launcher
in `~/.local/bin`. It does not initialise a workspace or install agent tools.
If `ws` is not found, add this line to your bash/zsh configuration, then open
a new terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Check `ws --help`. You do not need to activate `.venv` for normal use.

## 2. Initialise

```bash
ws init
```

This creates the empty workspace at `~/workspace`, with classification and
browsing defaults, a local `README.md` and `AGENTS.md`, and an initial index.
It remembers the location in `~/.config/ws/config.yaml` and runs `ws check`.
It imports no files and creates no service accounts or personal profile records.

Choose another directory with `ws init --root /path/to/workspace`. Repeating
initialisation fills in missing infrastructure and preserves existing files.
Selecting another root changes the default workspace; it does not move existing
content. Environment overrides still take precedence over the saved root.

## 3. Try one workflow

Create a project:

```bash
ws create project first-project --type other --non-interactive
```

Choose an existing file and replace `/path/to/example.pdf` below with its path.
The explicit `--mode copy` leaves the original in place:

```bash
ws add document /path/to/example.pdf --type report --mode copy --non-interactive
```

The command prints the document's full reference, such as `document:example`.
Use the actual reference it returns in the next commands:

```bash
ws relate document:example to project:first-project as belongs-to
ws search documents example
ws show document:example
ws show relations of project:first-project
ws check
```

You have created, filed, connected and retrieved something. Browse the generated
links in your workspace's `documents/by-type/` and `documents/by-project/`
folders; each points to the same stored document. These are your records—there
is no automatic tutorial cleanup.

## Using an agent (optional)

Give the agent the installed checkout's [SKILL.md](SKILL.md) and the workspace's
`AGENTS.md`. The first explains ws; the second identifies this workspace and can
hold local working conventions. Your agent's existing skill-loading mechanism
or roster can help install the manual, but neither is required by ws.

An agent helping with setup should first check whether ws and the intended
workspace already exist, reuse them when appropriate, and ask for any missing
location or input file. Do not infer personal facts, import unrelated files or
replace existing settings. Read command help when an option is unclear.

## Learning and maintenance

- `ws capabilities documents`: available document operations.
- `ws help add document`: exact arguments and options.
- `ws describe add document`: what it reads and changes.
- [Concepts](docs/concepts/workspace-concepts.html): a visual explanation.
- [Configuration](docs/reference/configuration.md): saved root and overrides.
- [Documentation index](docs/README.md): optional guides for later.

To update, run `git pull --ff-only` in the code checkout, then `python3 install.py`
and `ws check`. Rerun the installer after relocating the checkout; it regenerates
the command launcher. Existing personal instructions may still reference the old
checkout location and should be reviewed separately.

If installation finds another `ws` in the destination, it refuses to replace it.
Inspect `command -v ws` and choose the intended installation. If initialisation
reports a conflicting file or directory, inspect it before changing anything.
The basic tutorial needs no network after installation. Online literature
lookups need internet access; CV PDF generation needs a TeX toolchain, and the
optional slides capability needs the separately installed SlideGenerator tool.
