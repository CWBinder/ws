# CLI contract

Usage: [Command reference](../docs/reference/commands.md).

- Canonical commands are verb-first: the universal verbs (`create`, `add`,
  `list`, `search`, `show`, `edit`, `delete`, `relate`, `unrelate`) come
  directly after `ws`, followed by a REF or a kind word.
- Every command has exactly one spelling. A verb that acts on objects of any
  kind lives only at the top level; a domain registers only the specialists
  that exist for its kind alone (`ws literature enrich`, `ws documents
  taxonomy`, `ws projects install`, `ws logistics people merge`).
- `create` mints what does not exist yet (`ws create task`, `ws create
  resource`, `ws create project`); `add` ingests what already does
  (`ws add document`, `ws add person`, `ws add literature`).
  A REF right after `add` targets the existing object it names:
  `ws add resource:<key> <path>` puts ordinary filesystem content into that
  bundle.
- Every global command belongs to exactly one of four categories, by what
  it does: **objects** (work on single objects and their edges — the CRUD
  verbs plus `relations`), **search** (collection queries and reference
  lookup — `list`, `search`, `id`), **maintenance** (keep the derived
  layers coherent — `index`, `wiki`, `check`), and **discovery**
  (learn the surface from the CLI — `help`, `capabilities`, `describe`,
  `completions`, `domains`). Domain specialists file under their domain.
  An uncategorised command is a defect in the model, not a harmless
  omission.
- Compatibility aliases must execute the same function as their canonical
  command and must not establish a second data store.
- Validation is spelled `check`, everywhere.
- Search accepts human discovery terms and returns canonical `kind:key` REFs.
  Any command acting on an existing object accepts only that full REF. Paths
  are operands only where the command explicitly reads or attaches a file.

## Discovery

Three surfaces, three questions, no overlap:

- `ws capabilities` — **which** commands exist. Derived from the parser:
  the global listing (one row per command, grouped under the four
  categories and then the domains), the kind-scoped view
  (`ws capabilities documents`), the category-scoped view
  (`ws capabilities maintenance`), or, with a longer path, the describe
  view of that one command.
- `ws <command> --help` (equally `ws help <command>`) — **how** to type this
  command now. Derived from the parser: the usage template, what each
  operand is, each flag's meaning, and for closed value sets the allowed
  values exactly once, with the extension route named.
- `ws describe <command>` — **what it does and touches**:
  the one-line purpose, the usage guide, the governing contract file, and the declared
  effects (reads, writes, external calls, destructive or not). Derived from
  the registry. Describe does not repeat flags — that is help's job.

Bare `ws`, `ws --help`, and bare `ws help` print the same overview, and it
is a map rather than a tutorial: what you can do (the four categories),
what the workspace holds (the domains and the relations layer), the three
grammars with one runnable example each, and how to find your way onward.
It reads no workspace state, so it prints identically in a broken or
absent workspace — live counts belong to the listings it points at. The
detail it does not carry is one command away: `ws capabilities <category>`
for a category's commands, `ws help <command>` for a command's flags,
`ws capabilities --all` for compatibility spellings.

The categories classify commands; two further listings name what the
workspace holds, and both are derived rather than hand-maintained:
`ws domains` (the homes that own objects) and `ws relations` (the graph
layer, listing the relation vocabulary actually in use). Category words
are operands of `capabilities`, not commands of their own. See
[Command categories](../docs/concepts/command-categories.md) for the model.

## Templates and placeholders

Usage templates use uppercase placeholders; prose and examples use angle
brackets. Both registers mean "replace this with your value":

- `REF` / `<kind>:<key>` — a full canonical reference, exactly as returned
  by `ws search`. Never a bare key, title, or path.
- `KIND` — a kind word (`document`, `person`, ...; plurals accepted).
- `NAME`, `TITLE` — human words; quotes optional, words are joined.
- `FILE`, `PATH` — a filesystem path; accepted only where the command
  explicitly ingests or reads a file.
- `QUERY`, `WORDS` — free text; quotes optional.
- `ID` — an internal identifier (relation id, message id) printed by a
  previous command.
- `[x]` optional, `...` repeatable.

A flag with the same name means the same thing on every command
(`--json`, `--dry-run`, `--ensure`, `--source`, `--observed-at`, ...);
the shared meanings are defined once in the registry and filled in
centrally.

## Where flags go

Flags belong to the command that declares them, so they follow the whole
command path and its operands:

```text
ws <verb> <kind> <operands> --flag value
```

Flags-last is the house style because it is the only ordering that always
parses. Three shapes break, and each fails for a structural reason:

- Before a kind word: `ws list --type abstract documents` — the kind word
  selects a subcommand, and a subcommand's flags cannot precede it. The kind
  is part of the command path, not an operand.
- Inside a multi-word operand: `ws search documents --type abstract siqew` —
  the remaining word is orphaned, because a repeatable operand stops at the
  first flag.
- Before a REF whose flags belong to the REF's kind:
  `ws edit --name X document:foo` — `edit` reads the kind from the REF, so
  the REF must come first.

The rule holds without exception, and is enforced before parsing: a flag may
not precede an operand even where argparse would have accepted it
(`ws add document --name X FILE` is refused). One rule with no exceptions is
learnable; a rule that holds "except where it happens to parse" teaches the
wrong habit and then breaks on the three shapes above. The refusal names the
offending word and prints the same command written correctly.

Enforcement is deliberately conservative: an option the resolved parser does
not know, or one of variable arity, ends the check rather than risk refusing
a working command.

## Help and describe content rules

Enforced by `ws check cli`:

- Every command has a one-line description saying what it does. Where a
  subcommand registration provides only a parent `help=` line, the
  description is inherited from it at build time.
- Every visible flag and positional has a help line. Shared flags inherit
  the registry's standard meaning; command-specific flags say what value
  they take, not just that they exist.
- Every positional shows a lexicon placeholder in the usage template,
  never an internal variable name.
- Every command resolves to a governing contract, and every writing
  command declares its own effects entry (the generic verb entry is not
  enough for a writer).

## Extension and compatibility rules

- Register new commands through the parser and registry, with a category,
  purpose, contract, usage-guide route and declared effects for writers.
- Preserve canonical verb/kind grammar and flags-last validation. New aliases
  must not fork the implementation or create another durable store.
- Discovery JSON may gain additive fields; preserve existing field meanings.
  Command removals or incompatible operand/output changes require the
  [shared compatibility process](README.md#changing-a-contract).
- Keep help generated from actual parser options. Verify the full command
  surface and affected execution behaviour when changing registration.
