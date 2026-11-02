The person's workspace and owner are in place. If you have been guiding them
through setup, finish with this; there is no need to run `ws setup` again.

SHOW THEM

    ws owner
    ws context

Explain that every briefing inside the workspace now names them, so an agent
knows whose workspace it is without running anything, and tells it to run
`ws owner` when it needs their details. To change a detail later, run
`ws edit` on the record. To add a fact about them, it goes on their person
record if it is private and on their identity if a CV should show it.

OFFER, and do only what they accept

- Brief every session automatically. An agent is only briefed if its harness
  runs `ws context` when a session starts. `ws help context` shows how for
  each harness, under "Briefing every session automatically". This changes the
  harness's settings, so show them the change first.
- Give agents the manual. {system}/SKILL.md is a skill their agents can load;
  how to install it depends on the harness.
- Try one workflow: make a project, file a document and connect them.

      ws create project first-project --type other --non-interactive
      ws add document PATH --type report --mode copy --non-interactive
      ws relate document:KEY to project:first-project as belongs-to
      ws show project:first-project

  `--mode copy` leaves the original where it is. Adding links nothing by
  itself, which is what `ws relate` is for. These become their real records;
  nothing cleans them up afterwards.

From here on, `ws help` is the manual.
