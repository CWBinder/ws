# Setting up

```bash
ws setup              # at a terminal, it asks the questions here
ws setup --web        # the same questions, in a browser
```

Setup explains what the workspace is, goes through what it holds, one kind at a
time, and ends on your first knowledge graph and what an agent will read. Along the
way it creates the workspace and whatever you offer. Whichever way you take, your
answers become ordinary ws commands.

To have an agent guide you, tell it: "run `ws setup` and guide me through it".
An agent has no terminal to be asked on, so for it setup asks nothing. `ws setup`
prints the list of steps, and `ws setup --step NAME` prints one: what to explain,
what to ask, which command to run with the answers, and which step comes next. The
agent does the talking and runs the commands.

## Trying it first

```bash
ws setup --test
ws setup --web --test
```

`--test` goes through everything against a temporary workspace, deleted at the
end. Your own workspace and configuration are not touched, and neither is
anything else on your machine: whatever you answer about the location is
ignored. Searching arXiv and fetching papers do use the network, but what they
fetch goes in the temporary folder too. An agent cannot use it this way, because
it needs someone to answer.

## The steps

```text
the idea
  brain         a second brain: a knowledge graph, kept in order by one CLI
  objects       the nine kinds, REFs, relations, and the verbs they share
  finding       search, walking along relations, and where to find every command
  workspace     where the folder lives (ws help init)

what it holds
  projects      fields, subfields and types; your first project and its purpose
  literature    your papers: it searches arXiv under the name you give, and adds
                only the ones you pick
  documents     document types; a first file
  resources     a first resource
  tasks         a first task
  identity      your public side (ws help profile)
  person        your private side, labelled owner (ws help owner)
  people        the organisations and people closest to you
  relations     your first relations, proposed from your answers; you keep the true ones

how it reaches your agent
  agent         what makes an agent yours, and how the briefing does it
  briefing      your goals, how agents should work with you, and a note for all of them
```

It ends on your first knowledge graph: your corner of it in words, and the whole of
it as the dashboard (`ws help rebuild dashboard`), inside the page with `--web`. Then
it shows what an agent actually reads (`ws help context`), and where you can change
it, carefully, since agents take it as fact.

The closing page also shows how to brief every session automatically and give agents
the manual. Those two change your agent's own settings, so setup shows them and leaves
them to you; it writes nothing outside the workspace and its configuration.

Only `workspace`, `identity` and `person` are required. Whether they are done is read
from the workspace, and setup keeps no state of its own, so you can stop at any point
and carry on later in another mode. A workspace that has them is not asked again.
Everything else can be skipped or repeated: skipping to the end still asks whatever
is required, and a later run starts again from the top, so skip what you have seen.

Setup does not ask about browse folders, which are hard to choose before there is
something to browse (`ws help rebuild views`).

## The browser version

A page cannot write to disk by itself, so `--web` runs a small server for as long
as setup lasts. It listens on 127.0.0.1 only, and answers only requests carrying
the token in the address it prints. It stops when you press Finish, on Ctrl-C, or
after half an hour without a request. `--no-browser` prints the address instead of
opening it.

## For programs

`--non-interactive` prints the steps even at a terminal, and `--interactive`
asks even without one. `--json` prints `step`, `complete`, `root`, `name`, `owner`,
`fields`, `project_types`, `document_types`, `test` and `text`; `step` is the first
required step not done, and empty when all are.
