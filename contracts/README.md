# Workspace Contracts

This is the index for stable workspace contracts.

Use this file to choose the smallest relevant contract file instead of loading every rule into context.

## Contract Files

Core contracts cover the CLI, workspace, projects, tasks,
documents, resources, literature, logistics, profile, relations, search,
check, wiki, and statuses. Agent-role management belongs to the independent
roster tool.

Contracts state invariants. Start with [Getting started](../GETTING-STARTED.md)
for setup and the [documentation index](../docs/README.md) for explanations.
Use the CLI help for exact command syntax.

## Template Authority

Templates live in:

```text
~/Projects/ws/templates/
```

`ws` should generate files from those templates and the relevant contract file.

## Read Guidance

- The universal object model (ref, key, internal id, kind, name, aliases):
  read `objects.md` first.
- Creating or validating the workspace root: read `workspace.md`.
- Creating or validating a project: read `project.md` and `statuses.md`.
- Creating or validating literature items: read `library.md`.
- Working on the career folder or CV generation: read `career.md`.
- Creating objects or cross-domain relationships: read `relations.md`.
- Updating status fields: read `statuses.md`.

## General Rules

- Prefer plain Markdown and YAML.
- Keep machine-readable identity/state in YAML.
- Keep human-readable instructions and notes in Markdown.
- Do not duplicate the same durable fact across multiple files unless one file is a generated copy for tool compatibility.
- Add local sections when needed, but do not rename or remove required keys without updating the relevant contract.
