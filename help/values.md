# Judgement calls

The commands say how to change the workspace; this page says when, and
what deserves to change at all. It holds for people and agents alike.

## What deserves to become an object

- A **document** is one file important enough to address, classify and
  relate on its own: an invoice, a contract, a signed form, a slide deck,
  an abstract. One file, one record.
- A file inside a **resource** bundle is a supporting file with no
  identity of its own. One more receipt for an existing reimbursement is
  `ws add resource:<key> PATH`, not a new document.
- **Literature** is a bibliographic work with a stable identifier: a DOI,
  an arXiv ID or an ISBN. A paper is never a document.
- Most files deserve to be nothing. Do not promote every attachment or
  download into an object; when none of the above clearly applies, leave
  it alone and say so.

Adding changes the workspace, and `ws add document` moves the source file.
Do it when the request asks for that outcome or the task plainly needs it;
otherwise propose the command and stop.

## Relations

- Assert only what is stated or evident, never a connection that merely
  seems plausible.
- Reuse the vocabulary that `ws relations` lists before inventing a word,
  the same way round. Two spellings of one relation are worse than one
  slightly imperfect word.
- Sign what you know: `--source` for who or what asserted it,
  `--observed-at` for when.

## Classification

Pick classifier values from the kind's taxonomy, such as
`ws documents taxonomy` or `ws literature taxonomy`. Never extend a
taxonomy on your own: propose the new value and let the person approve it.

## Remembering

When the person asks you to remember something, it goes into the
workspace, where every later session finds it, never into notes of your
own:

```text
a fact about someone           their person record (ws edit person:<key>)
a fact about the person        their own person record, the one the briefing
  whose workspace this is      names as the owner
what their CV should say       their profile (ws help profile)
how to work in one place       that place's .context/instructions.md
something to do or attend      a task or an event
who is connected to what       a relation
```

A preference for one kind of work, such as how they write messages,
belongs in the skill for that work, outside the workspace.

## Deleting

`ws delete`, `--force`, and anything `ws describe` marks destructive run
only on explicit instruction, never as cleanup you decided on yourself.

## When unsure

Show the options with their consequences in a line or two each, and ask.
A wrong object in the graph costs more than a question.
