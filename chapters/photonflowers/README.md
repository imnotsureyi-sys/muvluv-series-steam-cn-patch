# photonflowers

## Status

- Branch: `chapter/photonflowers`
- Current public version: not released
- Release: none
- Native rows: 5,510
- Patch state: extraction and audit stage

## Scope

This workstream covers native `Muv-Luv photonflowers` Steam resources.

The current work is resource/text extraction and audit. It is not a released
translation patch.

## Current Evidence

- Native RIO/CRsa extraction is available.
- The v5 native table has 5,510 rows:
  - 5,322 high-confidence rows.
  - 188 recovered short JP rows from the wide audit layer.
- Bilibili text is used only as an audit/alignment reference and must not be
  imported as translation.

## Maintenance Focus

- Keep native JP text, stable IDs, scene locators, and control codes intact.
- Do not use English fallback, old Chinese fallback, or fuzzy matching.
- Before translation or writeback work, confirm the row source layer and audit
  confidence.

## Related Files

- Worktree: `C:\Users\Administrator\.codex\worktrees\4d5b\Muv-LuvSeries汉化`
- Extraction notes and intermediate tables are local-only until a public patch
  source table is ready.
