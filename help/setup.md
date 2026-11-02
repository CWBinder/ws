# Setting up

```bash
ws setup
```

Setup prints the next unfinished step of getting started: what to explain,
what to ask, and which command to run with the answers. It is written for an
agent guiding a person, because an agent has no terminal for a wizard to ask
questions on: the program says what comes next, and the agent does the
talking. A person alone at a terminal can follow the same text.

To start, tell an agent: "run `ws setup` and guide me through it".

## The steps

```text
1  the workspace folder     ws init (ws help init)
2  the public identity      the profile's first object (ws help profile)
3  the private details      the person labelled owner (ws help owner)
```

Run it again after each step. When all three are done it prints what is now
in place and offers the optional next things: briefing every session
automatically, giving agents the manual, and trying one workflow.

Setup changes nothing itself; the commands it names do that. It reads its
progress from the workspace, whether the workspace, the identity and the owner
exist, and keeps no state of its own. So it can stop at any point, a new
session picks up where the last one stopped, and a workspace that already has
these records is simply told it is finished.

`--json` prints the same as `step`, `complete` and `text`; `step` is empty when
setup is complete.
