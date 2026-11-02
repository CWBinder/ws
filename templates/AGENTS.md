# AGENTS — <project-name>

Read first:
- README.md
- LOG.md (newest entries first; read until you know the current state)
- project.yaml
- this file
- <ws-root>/SKILL.md when operating on workspace records
- `ws help` for usage workflows
- <ws-root>/contracts/README.md when changing ws or checking an implementation guarantee

Folders:
- in/: inputs the work consumes (device designs, external data, parameters)
- data/: intermediate results
- out/: finished outputs (final figures, tables, results to hand on)
- code/, paper/, slides/: source code, manuscript, deck build scripts and built decks
- docs/: stable documentation; refs/: small local references; tmp/: disposable scratch
- put material in the folder that fits; add a new top-level folder only when none does, and record it with the reason in LOG.md

Log:
- before ending a working session, add an entry at the top of LOG.md: date, host, what you did, what was decided and why, what comes next

Rules:
- ask before destructive changes

Agent instructions:
- this file is project-wide context
- do not store agent memory or session state in this file; that goes in LOG.md
