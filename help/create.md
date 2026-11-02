# Creating objects

`ws create` mints something that does not exist yet: a project, a
subproject, a task, a resource bundle or a profile item. Its sibling
`ws add` brings in something that already exists elsewhere, such as a
person, a file or a paper (`ws help add`).

The kind comes first, then its operands, then flags:

```bash
ws create task Book meeting room --due 2026-09-15
```

Search before you create; a duplicate is worse than a gap. `--ensure`,
where a kind offers it, reuses the matching object instead of making a
second one.

On a terminal, a bare command opens a wizard that asks for what is
missing. Without a terminal, as when an agent runs ws, the wizard never
starts and nothing waits for input: pass everything as flags, and what you
leave out stays empty.

Creating an object relates it to nothing. When a new object belongs to a
project or concerns a person, relate it right after with the REF the
command printed (`ws help relate`).
