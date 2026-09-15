# Projects

Projects live in the flat canonical store at the projects domain root:

```text
~/workspace/projects/
  items/<project>/            the store: one folder per project
  by-type/  by-field/  by-status/  by-organisation/  by-event/   derived browse views
  project-taxonomy.yaml
```

`ws create project` resolves the store in this order:

```text
--in DIR
WS_PROJECTS_DIR
<resolved-workspace-root>/projects/items
```

That means `ws create project test project` creates `items/test-project/` unless
you pass `--in` or configure a default. In an interactive terminal, a bare
project name opens the setup wizard; pass `--non-interactive` for the
minimal/default scaffold without prompts.

**The store is flat.** A project's **identity is its folder name**, which must
be unique, and that is what `ws list projects`, `show`, and cross-references
use. Path names are refused (`ws create project exampleco-simulations/shuttling`
fails): grouping is expressed with `fields`, `keywords`, and relation edges,
and browsed through the derived `by-*` trees, where reorganising never
changes a project's identity. The tree shapes are declared in
`folder-anatomy.yaml` in the workspace (see [Browsing](browsing.md)).
Creating a project from inside an existing project is refused (discovery
would hide it).

Mandatory files:

```text
project.yaml
README.md
AGENTS.md
CLAUDE.md
.gitignore
```

Allowed optional folders:

```text
code/
paper/
data/
docs/
refs/
notes/
out/
tmp/
```

`ws create project` creates `code/`, `paper/`, and `data/` only with their corresponding capability flags. `--python` creates Python project metadata and implies `--has-code`; `--venv` creates `.venv` and implies `--python`. Other folders are created when first needed. Git does not preserve empty directories in a clone, and `out/` and `tmp/` are intentionally ignored.

Follow [Project setup](project-setup.md) for creation, [Installing capabilities](project-install.md)
for environments and subprojects, and [Configuration](reference/configuration.md)
for root selection. `ws create project` uses the shipped templates.

Maintainers extending the scaffold should read the [project contract](../contracts/project.md).
