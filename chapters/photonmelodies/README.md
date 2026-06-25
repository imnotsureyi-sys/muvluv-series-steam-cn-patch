# photonmelodies

## Status

- Branch: `chapter/photonmelodies`
- Current public version: not released
- Release: none
- Native rows: 40,541
- Patch state: translation/writeback workflow stage

## Scope

This workstream covers native `Muv-Luv photonmelodies` Steam resources.

The current workflow has already proven RIO/CRsa extraction, JP text worklist
generation, Chinese writeback testing, and byte-patch package generation. It is
not yet a public release.

## Current Evidence

- A native worklist exists in the local chapter worktree.
- Every retained native row should have stable locator fields such as chapter,
  csv_row, stable_id, egpack, scene, and jp_text.
- Writeback work must preserve control codes and locate rows by stable ID and
  payload offset.

## Maintenance Focus

- Continue translation and QA from JP source text only.
- Keep generated repack/test outputs out of Git history.
- Publish only byte patches or release packages, never complete RIO resources.

## Related Files

- Worktree: `C:\Users\Administrator\.codex\worktrees\babb\Muv-LuvSeries汉化`
- Extraction notes, writeback tests, and intermediate tables are local-only
  until a public patch source table is ready.
