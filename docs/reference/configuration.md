# Configuration

`ws init` saves the workspace location in a private, per-user file:

```text
~/.config/ws/config.yaml
```

For example:

```yaml
workspace_root: /path/to/my-workspace
```

ws consumes two settings: `workspace_root` and the optional `slides.themes`.
Other keys are preserved when initialisation updates the root. Override the
configuration file location with `WS_CONFIG`.

## Slide themes

The `slides` capability installs the brand-free `slide_factory` generator that
ships with ws. Branded themes (your institute's colours and logos) live in your
own theme packages, outside the ws repository. List them and ws installs them
next to the generator in every slides project:

```yaml
slides:
  themes: [project:my-slide-themes]
```

Entries are project REFs or filesystem paths to a package with a
`pyproject.toml`. A missing entry produces a warning and is skipped. The recipe
for writing a theme package is in `packages/slide_factory/README.md`.

## Path precedence

For the workspace root:

1. `ws init --root DIR`, during initialisation.
2. `WS_WORKSPACE_ROOT` in the current process environment.
3. `workspace_root` in the configuration file.
4. `~/workspace`.

Initialisation saves the effective root. Selecting another root does not move
existing content. The CLI derives its installation's code, templates and docs
locations automatically; do not copy the software into the data workspace.

Domain-specific environment overrides take precedence over root-derived paths:

```text
WS_PROJECTS_DIR       canonical projects store (normally projects/items)
WS_PROJECTS_DOMAIN    projects domain root
WS_TASKS_DIR
WS_LITERATURE_DIR
WS_DOCUMENTS_DIR
WS_RESOURCES_DIR
WS_LOGISTICS_DIR
WS_PROFILE_DIR
WS_RELATIONS_DIR
WS_SEARCH_DIR
WS_WIKI_DIR
```

`WS_PROJECTS_DIR` implies its parent as the projects domain unless
`WS_PROJECTS_DOMAIN` is set. Command-specific directory flags take precedence
where supported; consult that command's `--help`.

## Personal classifications and browsing

Defaults work without customisation. These workspace-local files can be changed
later:

- `projects/project-taxonomy.yaml`: project types and shared literature fields.
- `documents/document-taxonomy.yaml`: document types.
- `profile/profile-taxonomy.yaml`: profile types.
- `folder-anatomy.yaml`: generated browse-folder shapes.

Override the file locations with `WS_PROJECT_TAXONOMY`,
`WS_DOCUMENT_TAXONOMY`, `WS_PROFILE_TAXONOMY`, and `WS_FOLDER_ANATOMY` respectively.
Run `ws check` after changing them. See [Browsing](../browsing.md) for view
defaults, optional variations and rebuilding.

## Optional external tools

`WS_CONTACT_EMAIL` supplies the contact address used by literature providers
that require one, including Unpaywall. Credentials belong in provider-owned
private stores; never add tokens or passwords to workspace records or tracked
configuration. Roster and inbox are independent tools and are not needed to
initialise or operate the core workspace.

Older `WS_LIBRARY_DIR`, `WS_CAREER_DIR` and `WS_KNOWLEDGEBASE_DIR` environment
variables remain compatibility aliases. Advanced code/template overrides
`WS_CLI_ROOT` and `WS_SYSTEM_ROOT` are primarily for development.
