# Learning and using ws

`ws` manages projects, tasks, documents, literature and other records, plus the
relationships between them. This documentation explains how to use that model;
the installed CLI supplies the current command syntax.

## Start here: people and agents

1. **Set up:** [Getting started](../GETTING-STARTED.md) covers installation,
   initialisation and a small tutorial. An agent can follow the same file to
   assist setup. Defaults suffice; a personal profile and agent integration
   are optional.
2. **Understand the model:** [Workspace Concepts](concepts/workspace-concepts.html)
   explains objects, classifications, relationships and views visually. It is
   optional background. Text explanations cover
   [relationships](concepts/relationships.md),
   [document classification](concepts/document-classification.md) and
   [command categories](concepts/command-categories.md).
3. **Choose a task:** read one of the guides below. Use terminal help for exact
   syntax; examples in guides explain a workflow rather than list every flag.

## Usage guides

| Task | Guide |
|---|---|
| Create and organise a project | [Project setup](project-setup.md), [project workflows](projects.md) |
| Set up a project's environment or subproject | [Installing capabilities](project-install.md) |
| File and classify a document | [Documents](documents.md) |
| Keep a bundle of supporting files | [Resources](resources.md) |
| Find, import, read and connect papers/books | [Literature](literature.md) |
| Maintain career facts and generate a CV | [Profile and CVs](profile.md) |
| Search for context and connect records | [Relationships and retrieval](relationships.md) |
| Browse folders or change their arrangement | [Browsing](browsing.md) |
| Generate a Markdown wiki | [Wiki](visualization.md) |
| Inspect paths or optional settings | [Configuration](reference/configuration.md) |
| Learn commands, including tasks and contacts | [Command reference](reference/commands.md) |
| Enable terminal completion | [Shell completion](ws-completions.md) |

## Agent entry point and contributor entry point

Agents using ws start with [SKILL.md](../SKILL.md), the user's own instructions
and the current project's `AGENTS.md`. The skill gives operating habits and
routes to these same usage guides. [Workspace values](../agent/ws-values.md)
explain judgement calls. The concepts page is optional background for either reader.

People and agents **changing ws itself** start with the repository's
[AGENTS.md](../AGENTS.md) and relevant [contracts](../contracts/README.md).
Contracts state invariants, allowed extensions and compatibility requirements.
They are not a prerequisite for ordinary workspace use.

## Terminal help: one live command reference

| Question | Command |
|---|---|
| What does ws offer? | `ws --help` |
| What kinds of content can it hold? | `ws domains` |
| What can I do with documents? | `ws capabilities documents` |
| How do I type a command? | `ws help add document` or `ws add document --help` |
| Which guide applies, and what will it change or invoke? | `ws describe add document` |
| Is the workspace consistent? | `ws check` |

`ws capabilities --json` and `ws describe add document --json` expose discovery
information to programs and agents. Syntax comes from the parser; declared
effects, guide and contract pointers come from the command registry. Guide
paths in JSON are relative to the installed ws source/documentation root;
text output prints the guide’s full local path. A tutorial can
show a small worked example without duplicating the exhaustive reference.

## Where explanations and rules live

| Location | Purpose |
|---|---|
| `docs/concepts/` | Explain the model and why it is useful |
| Guides in `docs/`, such as `project-setup.md` | Walk through a task |
| `docs/reference/` | Explain configuration and command discovery |
| `docs/policies/` | State shared data-management policies |
| `contracts/` at the repository root | Specify invariants, extension rules and compatibility requirements |
| `templates/` at the repository root | Provide reusable starting files |

Keep usage guides here in `docs/` and governing rules in root `contracts/`.
[Architecture](architecture.md) and [layout](layout.md) orient contributors;
[the wiki plan](projects-wiki-plan.md) records design history rather than setup steps.

## What is shipped and what belongs to the user

The public repository contains the CLI, generic skill, templates, contracts,
documentation and tests. The private workspace contains the user's records,
taxonomies, folder anatomy and project instructions. Agent roles and personal
skills live in the user's agent configuration; credentials remain in provider
credential stores. Generated indexes and views are derived from private data
and should be treated as private too.

`ws init` creates a workspace README and agent orientation, preserving existing
files. Project creation generates a project `README.md`, `project.yaml`,
`AGENTS.md` and compatibility `CLAUDE.md`. Connecting the generic ws skill to an
agent is optional and uses the person's existing agent setup.
