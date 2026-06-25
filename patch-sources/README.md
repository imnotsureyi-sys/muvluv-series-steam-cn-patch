# Patch Sources

This directory contains the current TDA00-03 patch source tables.

These CSV files are the public source-of-truth tables for the released TDA
test patches. They preserve the JP source text and the current CN text together
with locator fields used by the tooling.

## Files

| File | Chapter | Rows | Purpose |
| --- | --- | ---: | --- |
| `tda00_jp_cn_compare.csv` | TDA00 | 3,713 | Current JP-CN source table for `tda00-beta0.1` |
| `tda01_jp_cn_compare.csv` | TDA01 | 8,565 | Current JP-CN source table for `tda01-beta0.2.2` |
| `tda02_jp_cn_compare.csv` | TDA02 | 6,589 | Current JP-CN source table for `tda02-beta0.1` |
| `tda03_jp_cn_compare.csv` | TDA03 | 6,913 | Current JP-CN source table for `tda03-beta0.1` |

## Schema

The important columns are:

- `call_order`: stable display/order index.
- `id`: game text id.
- `egpack`: source package/container.
- `scene`: scene or script locator.
- `speaker_jp`: original Japanese speaker field.
- `jp_text`: Japanese source text.
- `cn_text`: current Simplified Chinese text.
- `review_status`, `audit_flags`, `notes`: review and QA metadata when present.

## Rules

- Translation decisions must be based on `jp_text` and `speaker_jp`.
- Do not use English slots as translation source.
- Do not use old Chinese fallback or fuzzy matching fallback.
- Preserve control codes and display-related markers.
- After any source edit, run QA for empty text, Text ID Not Found, order
  mismatch, duplicate abnormal text, mojibake, English residue, and control
  code damage.
