# Tools

This directory keeps small reusable helpers that are safe to publish with the
patch repository.

Current public tool scope:

- `extract_egpack_text.py`: extract text from AGES egpack-style script data.
- `repack_egpack_with_csv.py`: rebuild text payloads from reviewed CSV data.
- `extract_fpd_filtered.py`, `probe_fpd.py`, `diagnose_fpd_keys.py`: inspect
  FPD/resource containers.
- `font_compat_zh.py`: check simplified Chinese glyph coverage for font work.

Internal one-off audits, Codex handoff prompts, local branch scripts, AI
translation helpers, and release-operation notes are kept locally and are not
part of the public GitHub tree.
