CHANGING IT

Each part of the briefing is labelled with where it comes from. `[workspace · ws]`
ships with ws. A path, such as `.context/whereami.md`, is a note of yours in plain
Markdown, which you can edit whenever you like. To change a detail about yourself, run
`ws edit` on the record: private facts go on your person record, and what a CV may
show on your identity.

Change these with care. An agent takes what the briefing says as fact, so one wrong
line misleads every session after it, and every line is read every time. Keep notes
short and true, and remove what has gone stale.

BRIEF EVERY SESSION

An agent is only briefed if it runs `ws context` when a session starts. Making that
automatic changes your agent's own settings, so setup shows how and leaves it to you.
For Claude Code, add this to `~/.claude/settings.json`:

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

LATER

Project and document types grow as you need them: the wizards offer to add a new
one. The `by-*` browse folders have sensible shapes already, and
`ws help rebuild views` explains changing them once there is something to
browse. From here on, `ws help` is the manual.
