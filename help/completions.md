# Shell completions

`ws completions` prints a tab-completion script for bash or zsh. Load it
from your shell's startup file.

zsh, on macOS or Linux, in `~/.zshrc`:

```zsh
autoload -Uz compinit
compinit
eval "$(ws completions zsh)"
```

bash, in `~/.bashrc`:

```bash
eval "$(ws completions bash)"
```

Loaded this way, the script is generated afresh in every new shell and so
always matches the installed ws.

## A saved copy

You may save the script to a file instead, for zsh as `~/.zfunc/_ws`, with
`fpath=(~/.zfunc $fpath)` before `compinit` in `~/.zshrc`, and for bash
as `~/.local/share/bash-completion/completions/ws`. A saved copy drifts
when ws changes, so `ws check cli` compares a copy at either place with the
current script and reports a stale one, together with the command that
refreshes it:

```bash
ws completions zsh > ~/.zfunc/_ws
```

## What completes

The script keeps no lists of its own. On every tab it asks ws, which reads
its live command parser and the current workspace, so a renamed or removed
command leaves completion at the same moment it leaves the CLI, and a new
project or literature item completes as soon as it exists. Completion
covers:

- every command path, at any depth, and the page names after `ws help`;
- every flag of the command being typed, including the kind's own flags
  after `ws edit <kind>:<key>`;
- object REFs after `ws show`, `ws edit`, `ws delete`, `ws relate` and
  `ws unrelate`;
- the allowed values after `--type`, `--field`, `--subfield`, `--status`,
  `--variant` and `--sort`;
- project names, literature item keys, resource REFs, and the capability
  words of `ws projects install`.

Since each tab runs `ws`, the command must be on the shell's `PATH`.
