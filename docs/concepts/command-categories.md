# Command categories

Two axes describe the whole CLI. The first classifies what you can *do* —
every global command belongs to exactly one of four categories, by intent.
The second names what the workspace *holds* — the domains that own objects
and the relations layer that owns edges. A command that fits no category is
a defect in the model, not a harmless omission (contracts/cli.md).

## What you can do: four categories

**objects** — work on single objects and their edges: the CRUD verbs.
`create` mints what does not exist yet, `add` ingests what already does,
`show` renders, `edit` changes, `delete` removes, and `relate` asserts an
edge. Show, edit and delete also take an edge's own REF, `relation:<id>`.
Bare `ws relations` files here too: edges are object-layer work. These are
verbs, not places — they come directly after `ws` and never appear behind a
domain word.

**search** — find things. Where the objects verbs take one object by its
REF, these take a kind or a bag of words and hand REFs back: `ws list
<kind>` enumerates a collection, `ws search <words>` queries the derived
index, and `ws id resolve`/`ws id show` turn a reference into the object
it names. Different inputs, different outputs — which is why CRUD's
per-record R does not cover them.

**maintenance** — initialise the workspace and maintain derived state:
`ws init` creates missing infrastructure and saves the root; `ws rebuild`
regenerates the derived layers from the canonical stores (the browse views,
the search cache, the Obsidian wiki and the dashboard, or one of them by name:
`ws rebuild wiki`); and `ws check` validates state against the contracts.
Initialisation preserves existing canonical settings and local instructions.


**discovery** — learn the command surface from the CLI itself: `ws help`
(how to type one command), `ws capabilities` (which commands exist),
`ws describe` (what one does and touches), `ws completions` (the same
knowledge, delivered while typing), and `ws domains` (the listing below).

The categories are also how the listings are organised: bare
`ws capabilities` groups every command under these four headings and then
the domains, and a category word scopes it (`ws capabilities
maintenance`). Category words are operands of `capabilities`, not commands
of their own.

Note that the category tells you the *shape* of the command too. Objects
and search commands are verb-first, followed by a REF or a kind word.
Maintenance and discovery commands are verb-first as well, but what follows
names a part of the workspace or of the CLI rather than an object: a derived
layer (`ws rebuild wiki`), an area (`ws check anatomy`), or a command path
(`ws describe add document`). Bare, `ws rebuild` and `ws check` cover every
layer and area.

## What the workspace holds: domains and relations

**Domains** own the objects. There are seven domains holding nine kinds;
`logistics` holds person, organisation and event. The others each hold one kind.
Agent roles and skills belong to the independent roster tool. Delete a
canonical domain store and its objects are gone.
A domain word hosts only the specialists that exist for its kind alone:

```bash
ws literature enrich literature:<key>     arXiv identity for one item
ws documents types add <type>             extend the document taxonomy
ws projects install <name>                (re)run recorded installs
ws logistics people merge person:<key>    fold a duplicate into a canonical
ws profile make-cv                        render the CV
```

`ws domains` lists them: `projects`, `tasks`, `literature`,
`documents`, `resources`, `logistics`, `profile`.

**Relations** is the edge layer. It owns every edge between objects — and
unlike everything maintenance rebuilds, a
hand-asserted edge exists nowhere else and can never be regenerated. Edges
are asserted with `ws relate` and listed under both endpoints by `ws show
REF`, each by its own REF; `ws show`, `ws edit` and `ws delete` take that
`relation:<id>` like any other REF. Bare `ws relations` lists the relation
vocabulary actually in use: each word, the number of edges carrying it, and
the kinds it connects, subject first.

## Ownership, in one question

What is lost if the store is deleted? A domain loses its objects; the
relations layer loses edges that cannot be re-derived from anything. The index and generated wiki lose only caches you rebuild. The category verbs themselves own nothing.
That question decides what gets backed up; the four categories decide how
the surface is presented and guessed.

## Grammar

Commands are verb-first. The verb comes directly after `ws`, followed by
either a REF (which names its own kind) or a kind word:

```bash
ws create task "Draft the appendix"
ws add person "Maria Schwarz"
ws show document:some-receipt
ws list projects --status active
ws search organisations ExampleCo
```

The two creation verbs describe the shape of what enters the workspace:

- `create` mints something that did not exist yet, scaffolding its
  structure (a project, a task, a resource bundle, a profile entry).
- `add` ingests something that already exists — a person you met, a file on
  disk, a paper with a DOI — identifying, normalising, and placing it.

## One spelling per command

A verb that works on any kind lives at the top level and nowhere else;
domain words host only their own specialists. So there is exactly one way
to write any given command, and the domain word appears only where the
operation genuinely belongs to that domain. `ws capabilities` lists every
command; `ws describe <path>` explains one.
