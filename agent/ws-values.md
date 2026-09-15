# Workspace values

Judgement calls for agents driving `ws`. The mechanics live in
[SKILL.md](../SKILL.md); this file decides what to do when a command alone does not.

## What deserves to become an object

- A **document** is one file important enough to address, classify, and
  relate on its own: an invoice, a contract, a signed form, a slide deck,
  an abstract. One file, one record.
- A **resource** child is a supporting file inside a bundle: it has no
  identity of its own. One more receipt in an existing reimbursement
  bundle is `ws add resource:<key> <path>`, not a new document.
- **Literature** is a bibliographic work with a stable identifier
  (DOI, arXiv id, ISBN). A paper is never a document.
- Most files deserve to be nothing: do not promote every attachment or
  download into an object. When none of the above clearly applies,
  leave it alone and say so.

Ingesting changes the workspace, and `add document` moves the source
file. Do it only when the user asked for that outcome, or the task
plainly requires it; otherwise propose it and stop.

## Relations

- Assert only facts that are stated or evident — never inferred
  connections that merely seem plausible.
- Reuse the existing vocabulary (`ws relations`) before inventing a new
  word; a graph with two spellings of the same relation is worse than
  one with a slightly imperfect word.
- Record provenance when you know it: `--source` (who or what asserted
  this) and `--observed-at` (when).

## Classification

- Pick classifier values from the kind's taxonomy (`ws documents
  taxonomy`, `ws literature taxonomy`, ...). Never extend a taxonomy on
  your own; propose the new value and let the user approve it.

## Destructive actions

- `ws delete`, `--force`, and anything a describe entry marks
  destructive: only on explicit instruction, never as cleanup you
  decided on yourself.

## When unsure

Show the options with their consequences in one or two lines each, and
ask. A wrong object in the graph costs more than a question.
