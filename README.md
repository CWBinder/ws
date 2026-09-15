# ws

`ws` is a local command-line workspace for projects, tasks, documents,
literature, contacts and personal profile records. It connects them with
explicit relationships, so you can find a document by its project or browse
papers by field without keeping duplicate copies.

Records are plain YAML and bibliographic files. Content stays on your machine;
folder views, a search index and an optional Markdown wiki are generated from
those records. People and agents use the same commands.

## Install

Requires **Git and Python 3.10+ on macOS or Linux**. No uv, roster, inbox or
service account is required for core workspace operations.

```bash
git clone https://github.com/CWBinder/ws.git ~/Projects/ws
cd ~/Projects/ws
python3 install.py
```

This creates `.venv/` inside the checkout and a launcher at `~/.local/bin/ws`.
If that directory is not on `PATH`, add `export PATH="$HOME/.local/bin:$PATH"`
to your shell configuration and open a new terminal. Keep the checkout in
place; the installation uses its code and documentation.

```bash
ws init                    # create ~/workspace with defaults; safe to rerun
ws --help
```

Use `ws init --root /path/to/workspace` to choose another location. Initialisation
saves that path, creates missing infrastructure and checks the workspace.
Existing records, classifications and local instructions are preserved.

**Next: [Getting started](GETTING-STARTED.md)** — create a project, copy in a
document, connect them and find it again.

## Find your way

- [Documentation](docs/README.md): explanations and guides.
- `ws help COMMAND`: syntax; `ws describe COMMAND`: declared effects.
- [SKILL.md](SKILL.md): the operating manual for agents using ws.
- [AGENTS.md](AGENTS.md) and [contracts](contracts/README.md): contributing to ws.

## Code and personal data stay separate

The repository ships code, generic defaults, documentation, templates and tests.
Your workspace defaults to `~/workspace`; its path is saved in
`~/.config/ws/config.yaml`. Personal records, generated views, agent instructions
and credentials are not part of the public repository. Provider credentials
stay in their own private stores. Literature acquisition uses external metadata
services; PDF/CV and optional slide workflows have additional requirements.

To update, run `git pull --ff-only` in the checkout and rerun `python3 install.py`.
See [Getting started](GETTING-STARTED.md) for checks and troubleshooting.
