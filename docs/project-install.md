# Installing project capabilities

This guide assumes ws is installed and a managed project exists. Start with
[Project setup](project-setup.md) to create one. Installing ws itself is covered
in [Getting started](../GETTING-STARTED.md).

## Add a capability after creation

```bash
ws projects install project:<key> venv
```

Use the project's actual REF. Capabilities are `code`, `paper`, `data`,
`python`, `venv` and `slides`. Each records its requirements in `project.yaml`
and materializes them: venv implies Python, which implies code. Slides implies
venv and installs the `slide_factory` deck generator that ships with ws
(`packages/slide_factory/`), followed by any theme packages listed under
`slides.themes` in your ws configuration. The shipped generator is brand-free;
see [Configuration](reference/configuration.md) for adding your own themes.

With no capability words, replay the recorded setup:

```bash
ws projects install project:<key>
```

This is useful after a clone, recreating `.venv`, or editing `project.yaml`.
Inside a project you may omit its REF. If its name is also a capability word,
use the full REF to disambiguate. Install adds and materializes capabilities;
it does not remove previously recorded ones.

## Install another local project as a package

```bash
ws projects install project:<consumer-key> --use-project project:<dependency-key>
```

This records a package dependency, creates its `depends-on` edge and installs
it into the consumer's own `.venv`. Repeat `--use-project` for more packages.
The extended value is `project:<key>[:package[:path]]`, where the optional path
selects the dependency's installable subdirectory. Already recorded entries
are skipped; an unresolvable dependency fails before anything is written.

An ordinary `depends-on` relationship does not install software. Use
`ws relate` for conceptual connections that have no installation recipe.

## Declare a custom build recipe

When a dependency needs more than an editable pip install, put a
`package_install` list in that dependency's `project.yaml`:

```yaml
package_install:
  - "{python} -m pip install scikit-build-core pybind11 ninja cmake"
  - "{python} -m pip install -e {path} --no-build-isolation"
```

The consumer executes these steps in order in place of the default editable
install. `{python}` is the consumer's venv interpreter and `{path}` is the
dependency's installable path. A failed step aborts that dependency's install
with a warning. Review a dependency's recipe before running its setup.

## Share an environment with a subproject

A subproject sits inside a parent project and uses the parent's `.venv`.
It has its own Git repository, `subproject.yaml`, and code/data/results
folders. The parent ignores the nested repository.

From inside the parent project:

```bash
ws create subproject analysis-study
```

Grouping paths such as `studies/analysis-study` are accepted; missing grouping
folders are created. Subprojects cannot nest within subprojects or use standard
content folders such as `code/` as grouping folders. The REF is
`project:<parent-key>/<subproject-path>`. `ws show project:<parent-key>` lists
them. Running `ws projects install` from a subproject sets up its parent.

## Inspect the result

```bash
ws show project:<key>
ws projects check
```

For exact options and external effects, use `ws help projects install` and
`ws describe projects install`. Maintainer rules live in the
[project contract](../contracts/project.md).
