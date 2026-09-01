# AGE2 incident index

These notes preserve failures that changed the production rules. They are not
bug anecdotes: each entry names the wrong assumption, evidence, repair,
regression gate and remaining boundary.

- [`tda03-achievement-uistring.md`](tda03-achievement-uistring.md): a TDA02
  `uistring.epk` was accidentally shipped in TDA03 beta0.1–beta0.1.5, breaking
  chapter/achievement mappings; fixed in beta0.1.6.
- [`loose-overlay-boundary.md`](loose-overlay-boundary.md): why LocalAppData
  `data/root` is a higher-priority loose namespace, not an automatic full
  extraction of `pack.bin`, and why whole-directory rollback is unsafe.
- [`structural-empty-records.md`](structural-empty-records.md): five verified
  empty bookkeeping slots became explicit no-op records instead of apparent
  missing translations or silent row deletions.
- [`font-glyph-substitution-retired.md`](font-glyph-substitution-retired.md):
  the lossy character-replacement workaround was removed in favor of real font
  coverage, routing, metrics and license checks.
- [`public-snapshot-release-alignment.md`](public-snapshot-release-alignment.md):
  a maintained translation table, runtime authority and historical ZIP are
  separate claims; the current AGE2 end-to-end rebuild remains partial.

New notes should use the same structure: symptom, unsafe assumption, controlled
comparison, root cause, correction, automated check, in-game check and limits.
