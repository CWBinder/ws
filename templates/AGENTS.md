# AGENTS — <project-name>

Read first:
- README.md
- .context/purpose.md (what this project is for; it belongs to the person)
- .context/log.md (newest entries first; read until you know the current state)
- `ws context project:<project-name>` for the full briefing
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
- put material in the folder that fits; add a new top-level folder only when none does, and record it with the reason in .context/log.md

Context:
- .context/purpose.md says what the project is for, in the person's words: fill or change it only from what they said, or ask them; never invent it
- after each piece of work, add an entry at the top of .context/log.md: date, host, what you did, what was decided and why, what comes next

Rules:
- ask before destructive changes

Agent instructions:
- this file is project-wide context
- do not store agent memory or session state in this file; that goes in .context/log.md
