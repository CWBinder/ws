# Learning and using ws

`ws` manages projects, tasks, documents, literature and other records, plus the
relationships between them. This documentation explains how to use that model;
the installed CLI supplies the current command syntax.

## For people

1. **Understand the model:** open [Workspace Concepts](concepts/workspace-concepts.html)
   in a browser. It explains objects, classifications, relationships and derived
   views using fictional examples. It is optional learning material, not a
   required agent prompt or the complete command reference.
2. **Set up:** follow [Getting started](../GETTING-STARTED.md) to install with
   a local `.venv` and initialise a workspace with `ws init`. Defaults are enough
   to start; no agent tools or personal profile are required.
3. **Do a first task:** follow [Project Setup](project-setup.md) to create a
   project. This guide assumes the CLI is already available. Use `ws help add
   document` or `ws help create task` for other starting points.
4. **Learn as needed:** use [project workflows](projects.md),
   [views and the wiki](visualization.md), and [configuration](reference/configuration.md).

## For agents using ws

Start with the shipped [ws skill](../SKILL.md), plus the user's own agent
instructions and the current project's `AGENTS.md`. The skill explains the
operating procedure; [workspace values](../agent/ws-values.md) explain judgement
calls. Discover commands through the CLI and read only the relevant
[contract](../contracts/README.md) when deeper rules are needed.

The repository's root [AGENTS.md](../AGENTS.md) is contributor orientation for
working on ws itself. It is not a person's workspace profile. The concepts
page is not something every agent needs to load.

## Terminal help: one live command reference

| Question | Command |
|---|---|
| What does ws offer? | `ws --help` |
| What kinds of content can it hold? | `ws domains` |
| What can I do with documents? | `ws capabilities documents` |
| How do I type a command? | `ws help add document` or `ws add document --help` |
| What will it read, change or invoke? | `ws describe add document` |
| Is the workspace consistent? | `ws check` |

`ws capabilities --json` and `ws describe add document --json` expose discovery
information to programs and agents. Syntax comes from the parser; declared
effects and contract pointers come from the command registry. A tutorial can
show a small worked example without duplicating the exhaustive reference.

## Where explanations and rules live

| Location | Purpose |
|---|---|
| `docs/concepts/` | Explain the model and why it is useful |
| Guides in `docs/`, such as `project-setup.md` | Walk through a task |
| `docs/reference/` | Explain configuration and command discovery |
| `docs/policies/` | State shared data-management policies |
| `contracts/` at the repository root | Specify data invariants and required behaviour |
| `templates/` at the repository root | Provide reusable starting files |

Contracts primarily serve maintainers, validators and agents resolving detailed
questions. They are not a beginner reading list. There is currently no
`docs/guides/` or `docs/contracts/` directory.

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
