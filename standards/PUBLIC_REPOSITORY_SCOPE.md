# Public Repository Scope

The public GitHub repository should contain only the assets needed by users,
testers, and contributors.

## Keep Public

- Root `README.md` with download links and feedback instructions.
- `patch-sources/`: current TDA00-03 JP-CN patch source tables.
- `tools/`: small reusable extraction/repack/font-check tools.
- `glossary/`: shared JP-CN terminology.
- `standards/`: public translation, source-table, and repository-scope rules.
- `chapters/`: short chapter/workstream status cards.

## Keep Local

- Internal Codex handoff prompts.
- Local branch/worktree procedures.
- Commit-message templates and release-operation notes.
- ATE/reference patch research notes.
- One-off audit scripts and generated reports.
- Old AI translation batches and intermediate output tables.
- Full game resources, RIO/egpack repack output, caches, and test installs.

## Release Assets

Patch zip files belong on GitHub Releases. They should not be committed to the
repository tree.
