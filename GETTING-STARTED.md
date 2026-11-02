# Getting started

Install ws, then run `ws setup`. This guide works for a person at a terminal or
an agent assisting them. If you have an agent, the quickest way is to tell it:

> Install ws by following GETTING-STARTED.md from
> https://github.com/CWBinder/ws, then run `ws setup` and guide me through it.

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

An agent helping with this first checks whether ws is already installed, and
reuses it when it is.

## 2. Set up

```bash
ws setup
```

It asks its questions right there in the terminal. To answer them in a browser
instead:

```bash
ws setup --web
```

Either way it creates the workspace, then your first two objects, which tell
every later agent who you are. You can stop at any point and pick up later.

To see how it works first, add `--test`. It goes through everything in a temporary
folder and keeps nothing, whatever you enter:

```bash
ws setup --test
ws setup --web --test
```

`ws help setup` explains the rest.

## Learning and maintenance

- `ws help`: the overview of the workspace, and the list of manuals.
- `ws capabilities documents`: available document operations.
- `ws help add document`: how to add a document, with its options.
- `ws describe add document`: what it reads and changes.
- `ws help configuration`: the saved root and its overrides.
- `ws check`: whether the workspace is consistent.

To update, run `git pull --ff-only` in the code checkout, then `python3 install.py`
and `ws check`. Rerun the installer after relocating the checkout; it regenerates
the command launcher. Existing personal instructions may still reference the old
checkout location and should be reviewed separately.

If installation finds another `ws` in the destination, it refuses to replace it.
Inspect `command -v ws` and choose the intended installation. If initialisation
reports a conflicting file or directory, inspect it before changing anything.
The basic workflow needs no network after installation. Online literature
lookups need internet access; CV PDF generation needs a TeX toolchain, and the
optional slides capability downloads python-pptx and Pillow into the project's
own environment the first time it is installed.
