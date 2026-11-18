# Installing project capabilities

Install makes a project's folder match what its `project.yaml` records,
extending the record first when asked. Inside a project you may omit its
REF; if the project's name is also a capability word, give the full REF.

## Add a capability

```bash
ws projects install project:<key> venv
```

The capabilities are `code`, `paper`, `data`, `python`, `venv` and `slides`.
Each is recorded in `project.yaml` and materialized: venv implies Python,
which implies code. Slides implies venv and installs the `slide_factory`
deck generator that ships with ws, followed by any theme packages listed
under `slides.themes` in the ws configuration (`ws help configuration`).
The shipped generator is brand-free.

Install adds capabilities; it never removes recorded ones.

## Replay the recorded setup

```bash
ws projects install project:<key>
```

With no capability words, install reruns everything the record holds:
useful after a clone, after recreating `.venv`, or after editing
`project.yaml`. Every run also brings the standard layout up to date: it
adds `.context/log.md` and `.context/purpose.md` where a project has none,
missing standard folders, the ignore rules for `out/` and built decks, and
the context rules in `AGENTS.md`. It never moves or deletes anything; a log
or purpose in an older place is moved by `ws projects migrate`
(`ws help projects migrate`).

## Install another workspace project as a package

```bash
ws projects install project:<consumer-key> --use-project project:<dependency-key>
```

This records a package dependency, creates its `depends-on` edge, and
installs it into the consumer's own `.venv`. Repeat `--use-project` for more
packages. The full value is `project:<key>[:package[:path]]`, where the
optional path selects the dependency's installable subfolder. Recorded
entries are skipped, and a dependency that cannot be resolved fails before
anything is written.

A plain `depends-on` relation installs nothing. Use `ws relate` for
conceptual connections with no installation recipe.

## Declare a custom build recipe

When a dependency needs more than an editable pip install, put a
`package_install` list in that dependency's `project.yaml`:

```yaml
package_install:
  - "{python} -m pip install scikit-build-core pybind11 ninja cmake"
  - "{python} -m pip install -e {path} --no-build-isolation"
```

The consumer runs these steps in order instead of the default editable
install. `{python}` is the consumer's venv interpreter and `{path}` the
dependency's installable path. A failed step aborts that dependency's
install with a warning. Review a dependency's recipe before running it.

## Check the result

```bash
ws show project:<key>
ws projects check
```
