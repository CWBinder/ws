# Configuring ws

ws needs to know one thing to work: where the workspace is. Everything else
has a default that works without customisation.

## The configuration file

`ws init` saves the workspace location in a private, per-user file:

```text
~/.config/ws/config.yaml
```

```yaml
workspace_root: /path/to/my-workspace
slides:
  themes: [project:my-slide-themes]
```

ws reads two settings from it:

`workspace_root`
: The workspace directory. Written by `ws init`; it must be a non-empty
  path.

`slides.themes`
: Optional. Theme packages installed into every slides project, next to
  the deck generator (below).

Other keys are kept: when `ws init` updates the root it rewrites only that
line and preserves the rest, comments included. Set `WS_CONFIG` to keep the
file somewhere else.

## Where the workspace is

The first of these that is set wins:

```text
ws init --root DIR     for that run of init, which then saves it
WS_WORKSPACE_ROOT      the variable in the current environment
workspace_root         the saved setting
~/workspace            otherwise
```

Choosing another root changes where ws looks; it never moves existing
content. The ws software lives apart from the workspace: it finds its own
code, templates and manual from where it is installed, so never copy it into
the workspace. `ws init` refuses a workspace inside the ws checkout, and
refuses your home folder, `/` and `/workspace` as roots (`ws help init`).

## Moving one store

Each store normally sits under the root. An environment variable moves one
of them on its own, and takes precedence over the root:

```text
WS_PROJECTS_DIR       the projects store (normally projects/items)
WS_PROJECTS_DOMAIN    the projects domain: its by-* views and taxonomy
WS_TASKS_DIR          tasks
WS_LITERATURE_DIR     literature
WS_DOCUMENTS_DIR      documents
WS_RESOURCES_DIR      resources
WS_LOGISTICS_DIR      people, organisations and events
WS_PROFILE_DIR        profile
WS_RELATIONS_DIR      relations
WS_SEARCH_DIR         the search index folder (WS_INDEX_DIR also works)
WS_WIKI_DIR           the wiki folder
```

`WS_PROJECTS_DIR` makes its parent folder the projects domain, unless
`WS_PROJECTS_DOMAIN` is set too. A command's own directory flag, such as
`--in` on `ws create project`, beats both for that run; the command's
`--help` says where one exists.

## Classification and browse files

The defaults work without customisation. These workspace files hold your
own vocabulary and browse shapes, and each can be moved with a variable:

```text
projects/project-taxonomy.yaml     WS_PROJECT_TAXONOMY
documents/document-taxonomy.yaml   WS_DOCUMENT_TAXONOMY
profile/profile-taxonomy.yaml      WS_PROFILE_TAXONOMY
folder-anatomy.yaml                WS_FOLDER_ANATOMY
```

The project taxonomy holds project types and the fields and subfields that
projects and literature share (`ws help projects taxonomy`); the document
and profile taxonomies hold their kinds' types. `folder-anatomy.yaml`
shapes the `by-*` browse folders (`ws help rebuild views`). Run `ws check`
after changing any of them.

## Slide themes

The slides capability installs `slide_factory`, the deck generator that
ships with ws, and it is brand-free. Branded themes, with an institute's
colours and logos, live in your own theme packages outside the ws
repository. List them under `slides.themes`, and ws installs them next to
the generator into a project's `.venv` whenever it installs slides, at
creation or with `ws projects install` (`ws help projects install`):

```yaml
slides:
  themes: [project:my-slide-themes, ~/Projects/lab-theme]
```

An entry is a project REF or a path to a package with a `pyproject.toml`.
An entry that cannot be found is skipped with a warning. The
`slide_factory` package in the ws checkout describes how to write a theme.

## Other settings

`WS_CONTACT_EMAIL`
: The contact address sent to literature providers that ask for one,
  Unpaywall among them.

`WS_HOST`
: The host name ws records, for example as a project's default host and in
  log headings. Defaults to this machine's short name.

Credentials never go into workspace records or tracked configuration; they
belong in each provider's own private store. Other tools, such as roster or
the inbox, are independent of ws: neither is needed to set up or use the
workspace.

The older variables `WS_LIBRARY_DIR`, `WS_CAREER_DIR` and
`WS_KNOWLEDGEBASE_DIR` still work as aliases. `WS_CLI_ROOT` and
`WS_SYSTEM_ROOT` override where ws finds its own code and files; they are
meant for developing ws.
