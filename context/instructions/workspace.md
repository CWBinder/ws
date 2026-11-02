These rules are for the session the person is talking to. If another
session started you as a helper, report back to it and leave the log alone.

Records change only through `ws`: read the ws skill ({system}/SKILL.md)
before changing one. Reading is free: search, show, follow relations, and
read the files `ws show` points to. The .context/ notes (whereami.md,
instructions.md, purpose.md, log.md) are plain Markdown, edited directly.
Add no top-level folders to the workspace root.

The log. The object you work in keeps a log, newest entry first, at the path
this briefing names (normally .context/log.md; create it when there is none).
Add an entry after each finished piece of work or decision, at milestones in
a long session, and always before you stop:

    ## YYYY-MM-DD · host
    - Did: what changed
    - Decided: what was decided, and why
    - Next: what is open

When the log grows long, fold the oldest entries into one entry headed
"Summary of <period>". Never drop a decision silently.

The purpose belongs to the person. When the work shows that it is wrong,
vague, reached or has shifted, propose new wording with your reason; write
it only after their yes, and log the change. When it is reached, propose
closing the object.

The graph. Change records when the task asks for that outcome; otherwise
propose the command. Assert only connections that are stated or evident,
with --source and --observed-at, and never delete unless asked. Judgement
calls: `ws help values`.

Remembering. Asked to remember something, file it where it belongs, never
in notes of your own. A fact about someone goes on their person record, and
that includes the person whose workspace this is: their record is the one
WHERE YOU ARE names as the owner. Their CV identity changes only when their
CV should. Where each other kind of fact goes is in `ws help values`.

Boundaries. Working in a project or resource, change only its folder. The
others have their own agents: propose changes to them, or hand the work
over, rather than editing their files from here.
