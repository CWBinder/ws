Every briefing inside the workspace now names you, so an agent knows whose
workspace it is without running anything, and `ws owner` gives it your details.
To change a detail, run `ws edit` on the record: private facts go on your person
record, and what a CV may show on your identity.

Two more things make agents use all this. Both change your agent's own settings,
so setup shows them and leaves them to you.

BRIEF EVERY SESSION

An agent is only briefed if it runs `ws context` when a session starts. For
Claude Code, add this to `~/.claude/settings.json`:

    "hooks": {
      "SessionStart": [
        { "hooks": [ { "type": "command", "command": "{ws} context" } ] }
      ]
    }

`ws help context` shows how for other agents, under "Briefing every session
automatically".

GIVE AGENTS THE MANUAL

ws ships a skill that teaches agents its commands. For Claude Code:

    ln -s {system} ~/.claude/skills/ws

TRY ONE WORKFLOW

Make a project, file a document and connect them. `--mode copy` leaves the
original where it is, and adding links nothing by itself, which is what
`ws relate` is for.

    ws create project first-project --type other --non-interactive
    ws add document PATH --type report --mode copy --non-interactive
    ws relate document:KEY to project:first-project as belongs-to
    ws show project:first-project

LATER

Project and document types grow as you need them: the wizards offer to add a new
one. The `by-*` browse folders have sensible shapes already, and
`ws help rebuild views` explains changing them once there is something to
browse. From here on, `ws help` is the manual.
