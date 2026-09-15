# `ws` Shell Completions

`ws` supports dynamic tab completion for bash and zsh.

The completion scripts call the shared completion endpoints:

```text
ws __complete <kind>
ws __complete-path <command> [<subcommand> ...]
ws __complete-flags <command> [<subcommand> ...]
```

This keeps platform-specific shell code small. Subcommands and flags are read
from the live parser, so a renamed or removed command disappears from
completion at the same moment it leaves the CLI; the shell scripts hold no
command or flag lists of their own. Dynamic values such as literature item
keys and project names are read from the current workspace each time
completion runs.

## zsh

Use on macOS or Linux when the login shell is zsh:

```zsh
autoload -Uz compinit
compinit
eval "$(ws completions zsh)"
```

## bash

Use on Linux, or any host where the login shell is bash:

```bash
eval "$(ws completions bash)"
```

## Current Coverage

Completion currently covers:

- every command path in the parser, at any depth
- every flag of the command being typed, including the kind-specific flags of
  `ws edit <kind>:<key>`
- object REFs after `ws show`, `ws edit`, `ws delete`, `ws relate`, `ws unrelate`
- controlled vocabularies behind `--type`, `--field`, `--subfield`,
  `--status`, `--variant`, `--depth`, `--account`, `--sort`
- literature item keys, project names, resource objects, agent roles

Subcommands and flags are discovered automatically. Add a specialised
`completion_values()` kind only for dynamic values such as project names.
