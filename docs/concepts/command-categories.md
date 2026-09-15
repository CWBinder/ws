# Command categories

Two axes describe the whole CLI. The first classifies what you can *do* —
every global command belongs to exactly one of five categories, by intent.
The second names what the workspace *holds* — the domains that own objects
and the relations layer that owns edges. A command that fits no category is
a defect in the model, not a harmless omission (contracts/cli.md).

## What you can do: five categories

**objects** — work on single objects and their edges: the CRUD verbs.
`create` mints what does not exist yet, `add` ingests what already does,
`show` renders, `edit` changes, `delete` removes, and `relate`/`unrelate`
assert and retract edges. `ws relations` and `ws relations edit` file here
too: edges are object-layer work. These are verbs, not places — they come
directly after `ws` and never appear behind a domain word.

**search** — find things. Where the objects verbs take one object by its
REF, these take a kind or a bag of words and hand REFs back: `ws list
<kind>` enumerates a collection, `ws search <words>` queries the derived
index, and `ws id resolve`/`ws id show` turn a reference into the object
it names. Different inputs, different outputs — which is why CRUD's
per-record R does not cover them.

**maintenance** — keep the derived layers coherent: `ws index rebuild`
(the search cache), `ws wiki build` (the Obsidian view), and `ws check`
(validate state against the contracts). Everything maintenance touches can
be regenerated from the canonical stores.


**discovery** — learn the command surface from the CLI itself: `ws help`
(how to type one command), `ws capabilities` (which commands exist),
`ws describe` (what one does and touches), `ws completions` (the same
knowledge, delivered while typing), and `ws domains` (the listing below).

The categories are also how the listings are organised: bare
`ws capabilities` groups every command under these five headings and then
the domains, and a category word scopes it (`ws capabilities
maintenance`). Category words are operands of `capabilities`, not commands
of their own.

Note that the category tells you the *shape* of the command too. Objects
and search commands are verb-first, followed by a REF or a kind word;
maintenance and discovery commands are namespace-first
(`ws index rebuild`, `ws wiki build`).

## What the workspace holds: domains and relations

**Domains** own the objects. Each is the home of a kind — things with
`kind:key` REFs that can be shown, related, and deleted. There are eight,
holding nine kinds: most host exactly one, `logistics` hosts three (person,
organisation, event), and `agents` is the special case — it owns a canonical
store of hand-authored roles and skills, but those are tooling configuration
rather than workspace objects, so it hosts no kind and its contents carry
names instead of REFs. Delete a domain's store and objects are gone.
A domain word hosts only the specialists that exist for its kind alone:

```bash
ws literature enrich literature:<key>     arXiv identity for one item
ws documents types add <type>             extend the document taxonomy
ws projects install <name>                (re)run recorded installs
ws logistics people merge person:<key>    fold a duplicate into a canonical
ws profile make-cv                        render the CV
```

`ws domains` lists them: `projects`, `agents`, `tasks`, `literature`,
`documents`, `resources`, `logistics`, `profile`.

**Relations** is the edge layer. It owns every edge between objects — and
unlike everything maintenance rebuilds, a
hand-asserted edge exists nowhere else and can never be regenerated. Edges
are written only by `ws relate` and `ws unrelate`, and read with
`ws show relations of REF`. Bare `ws relations` lists the relation
vocabulary actually in use, with the number of edges carrying each word.

## Ownership, in one question

What is lost if the store is deleted? A domain loses its objects; the
relations layer loses edges that cannot be re-derived from anything. The
maintenance targets lose only caches you rebuild.
sessions you re-authenticate. The category verbs themselves own nothing.
That question decides what gets backed up; the five categories decide how
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
