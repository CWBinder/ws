# Setting up

```bash
ws setup              # at a terminal, it asks the questions here
ws setup --web        # the same questions, in a browser
```

Setup creates the workspace and your first objects, which tell every later
agent who you are. Whichever way you take, your answers become ordinary ws
commands.

To have an agent guide you, tell it: "run `ws setup` and guide me through it".
An agent has no terminal to be asked on, so for it setup asks nothing: it prints
the next step, meaning what to explain, what to ask and which command to run with
the answers. The agent does the talking, runs that command and runs `ws setup`
again.

## Trying it first

```bash
ws setup --test
ws setup --web --test
```

`--test` goes through everything against a temporary workspace, deleted at the
end. Your own workspace and configuration are not touched, and neither is
anything else on your machine: whatever you answer about the location is
ignored. An agent cannot use it this way, because it needs someone to answer.

## The steps

```text
1  the workspace folder     ws init (ws help init)
2  your public identity     the profile's first object (ws help profile)
3  your private details     the person labelled owner (ws help owner)
```

Which of these comes next is read from the workspace, and setup keeps no state
of its own. So you can stop at any point, carry on later in another mode, and a
workspace that already has all three goes straight to the rest.

Two steps are then offered, and can be skipped or repeated: your fields and
subfields (`ws help projects taxonomy`), and a note for every briefing
(`ws help context`).

The closing page shows what agents will now find, and how to brief every session
automatically and give agents the manual. Those two change your agent's own
settings, so setup shows them and leaves them to you; it writes nothing outside
the workspace and its configuration.

Setup does not ask about project and document types, which grow as you need them,
or about browse folders, which are hard to choose before there is something to
browse (`ws help rebuild views`).

## The browser version

A page cannot write to disk by itself, so `--web` runs a small server for as long
as setup lasts. It listens on 127.0.0.1 only, and answers only requests carrying
the token in the address it prints. It stops when you press Finish, on Ctrl-C, or
after half an hour without a request. `--no-browser` prints the address instead of
opening it.

## For programs

`--non-interactive` prints the next step even at a terminal, and `--interactive`
asks even without one. `--json` prints `step`, `complete`, `root`, `name`, `owner`,
`fields`, `test` and `text`; `step` is empty when the required steps are done.
