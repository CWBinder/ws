# Projects, Sync, and Wiki — Rollout Plan

Followable, check-off rollout for: project tooling hardening, git/sync hygiene, and the Obsidian wiki/visualization layer.

Companion docs:
- `visualization.md` — the Obsidian wiki/visualization design.
- `contracts/project.md` — project contract, including the Git Boundary and Sync model.
- `contracts/agent.md` — agent files, including the `CLAUDE.md` symlink convention.

## Guiding principles

- **Canonical YAML → generated Markdown.** Project/agent state lives in `project.yaml`/`agent.yaml`; Obsidian notes are a generated view, never a second source of truth.
- **Minimal, modular, extendible.** Prefer data-driven config and small modules over inline growth in `ws`.
- **Lightweight in git; heavy via rsync.** Git tracks the small editable layer; heavy data and generated outputs are gitignored and moved by rsync.

## Locked decisions

- Visualization: **Obsidian only** (static HTML deferred), **single workspace vault** rooted at `~/workspace`, hub in `wiki/`.
- `CLAUDE.md`: **symlink → `AGENTS.md`** on macOS/Linux (`@AGENTS.md` import on Windows). Decided and documented in `contracts/agent.md`.
- Hosts in scope: the local workstation host under `system/hosts/<host>/` (macOS). No Windows.
- `data/` gitignore pattern (no broad CSV allowlist):
  ```gitignore
  data/**
  !data/
  !data/README.md
  !data/**/*.md
  !data/**/.gitkeep
  ```
- Sync schema (minimal, host-oriented):
  ```yaml
  sync:
    primary_host: mac
    remotes: []
    git: []
    data: []
  ```
- Nested repos (e.g. `paper/` from Overleaf, `code/` on GitHub): parent repo **ignores** their paths; each sub-repo manages its own history/remote. Submodules only if deliberate version pinning is wanted.
- Heavy-data tripwire: `ws check` warns on tracked/working files > 5 MB.

## Phases

MVP = Phases 0, 2, 1, 4, 5, 7a (in that order).

### Phase 0 — Docs/design  ✅
- [x] 0.1 `visualization.md` (Obsidian wiki model).
- [x] 0.2 "Git Boundary and Sync" section in `contracts/project.md`.
- [x] 0.3 This rollout plan.
- [x] 0.4 `architecture.md` future directions marked in-progress.
- [x] (prior) `CLAUDE.md` symlink convention decided and documented in `contracts/agent.md`.

### Phase 2 — Modularize  ✅
- [x] 2.1 Create `ws_lib/project.py`; move project functions out of `ws`; wire `project.add_parser(sub)` (mirrors `literature`).
- [x] 2.2 No behavior change; smoke-tested `ws new-project` (and taxonomy/check/completions); `ws` 1025->688 lines.

### Phase 1 — Git hygiene  ✅
- [x] 1.1 Update project `templates/gitignore`: ignore `.codex/`/`.claude/` (match at any depth, so nested `code/.claude/` is covered too — no `**/` needed); add the `data/**` allowlist (with `!data/**/` so nested `*.md` re-inclusion works); keep `out/`, `tmp/`.
- [x] Verified with `git check-ignore` and a fresh `ws new-project`: agent sessions and heavy data are ignored; `data/README.md`, nested `*.md`, and `.gitkeep` are tracked.

### Phase 3 — CLAUDE.md generation  ✅
- [x] 3.1 `new-project` and `new-agent` create `CLAUDE.md` via shared `project.write_claude_md` (symlink → `AGENTS.md`, with an `@AGENTS.md` import fallback on platforms without symlink support). Replaced the old stub writer. Documented in `contracts/project.md`, `projects.md`, `project-setup.md`. Verified git stores mode `120000`.

### Phase 4 — Cross-ref + sync metadata  ✅
- [x] 4.1 `sync:` block (`primary_host`/`remotes`/`git`/`data`) added to the `project.yaml` template and generator; `primary_host` defaults to the first host.
- [x] 4.2 `depends_on` warns and `related` notes (softer, since it may be a paper/dataset/external) when not an existing project; both non-blocking.
- [x] 4.3 Documented in `project-setup.md` and `contracts/project.md`.

### Phase 5 — `ws check` (read-only)  ✅
- [x] 5.1 `ws check` scans each project: missing required files, no git repo, dangling `depends_on` (problem) / non-project `related` (note), malformed `sync:`, and a pruned tree walk that flags only not-ignored nested repos, agent sessions, and files > 5 MB. Exits nonzero on problems; verified across all cases.

### Phase 7a — Generated wiki Markdown  ✅
- [x] 7a.1 `ws wiki build` (in `ws_lib/wiki.py`) generates the `generated/` layer (project/agent/field node-notes + `Workspace`/`Projects`/`Agents`/`Fields` MOCs) from canonical YAML into `wiki/generated/`.
- [x] 7a.2 Each note has a "generated — do not edit" callout; the layer is cleared and rebuilt each run (idempotent). Tags (`type/*`, `field/*`, `tag/*`, `status/*`) drive graph grouping; free-form project keywords are displayed as metadata; `depends_on`/`related`/agent links drive edges. Verified with sample projects + a project agent.

## Deferred (post-MVP)

- `ws sync <project> [--pull|--push]` — git push/pull the parent repo and any nested repos (auto-discovered as ignored `.git` dirs, or listed in `sync.git`), then rsync `sync.data` with `--exclude .git`; `--dry-run` first.
- Phase 7b — optional minimal `.obsidian/` config (graph groups by tag).
- `ws viz --html` — static, app-free graph export, only if needed.

Decided against a dedicated `link-repo`/`attach-repo` command: creating a nested repo is plain git, and the only non-obvious step (ignore its path in the parent) is one line that `ws check` already verifies. Documented as a recipe in `project-setup.md` "Nested Repositories".

## Verification

- [x] Sandbox sample projects; ran `ws check`, `ws wiki build`, nested-repo checks, `CLAUDE.md` checks, and block-list YAML checks.
- [ ] Open the vault in Obsidian.
- [x] Commit per phase through the MVP rollout.
