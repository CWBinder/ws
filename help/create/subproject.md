# Creating a subproject

A subproject is a working area inside a project that shares the parent's
`.venv`, and with it everything installed there. Use one for a study that
runs on the parent's code but deserves its own record, log and history.

```bash
ws create subproject analysis-study
ws create subproject studies/analysis-study --project project:<parent-key>
```

Run from inside the parent, the subproject lands in the current folder; run
from a grouping folder, it lands there. With `--project` it can be created
from anywhere, directly under the parent's root; a path such as
`studies/analysis-study` puts it into a grouping folder, which is created
if missing.

There is no wizard: type and classification come from the parent. ws
creates `in/`, `code/`, `data/` and `out/`, a `subproject.yaml`, a README, a
log and a `.gitignore`. It runs `git init` in the subproject and adds the
subproject's path to the parent's `.gitignore`, so the parent's history
stays free of it.

Its REF is `project:<parent-key>/<subproject-path>`, and it is related like
any project. `ws show project:<parent-key>` lists a project's subprojects.
Running `ws projects install` from a subproject sets up its parent.

Subprojects do not nest, and a standard content folder such as `code/` or
`data/` cannot serve as a grouping folder.
