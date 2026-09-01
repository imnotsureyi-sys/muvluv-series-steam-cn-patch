# AGE2 translation-authority alignment audit

Status: **open; do not solve by replacing a whole table with one old branch.**

The 2026-09-01 repository audit compared the current public snapshots with
`chapter/tda00`, `chapter/tda01`, `chapter/tda02`, `chapter/tda03`,
`fix/post-release`, `codex/paratranz` and `codex/astrbot-feedback`.

Those labels name local historical work only. They are intentionally not a
public reconstruction contract: several histories contain complete official
source fields and were removed from ordinary remote refs. Their exact private
input bytes are kept outside the public tree. The observations below are a
triage record; a conflict becomes public review evidence only after it is
projected to stable IDs and hashes without official text.

| Game | Confirmed historical difference from current snapshot |
| --- | ---: |
| TDA00 | 3,713 dialogue identities in both; about 232 localized values differ |
| TDA01 | historical source includes 82 additional speaker records; about 570 dialogue values differ |
| TDA02 | historical source includes 111 additional speaker records; about 358 dialogue values differ |
| TDA03 | historical source includes 133 additional speaker records; at least 40 dialogue values differ, with another later branch differing in about 228 values |

Spot checks found both likely regressions in the current tree and mistakes that
were corrected only in later branches. Examples include truncated sentences,
`克莱因立鸡群` versus `鹤立鸡群`, an untranslated `Ah...`, and the later
correction of `波宁公司` to `波音公司`. Therefore commit date alone is not a
safe winner.

## Required resolution procedure

1. Download the exact player Release and record its package hash.
2. Extract its changed EGPACK fields without treating the Release as the
   original Japanese source.
3. Join current and historical rows by `(relative_path, id, slot)`.
4. Classify dialogue, speaker, ruby, choice and other records separately.
5. Resolve every conflict using Japanese source, in-game context, review notes
   and the actually shipped value.
6. Emit a new portable table and a manifest naming the Release tag/package
   hash it represents.
7. Rebuild, run structural tests and complete scene/full-route QA.

Until that procedure is complete, the tables are valuable maintained
translation snapshots, not a claim that a clean clone can reproduce the five
historical beta ZIPs byte for byte.

The separate [text-free review ledger](../review-ledger/README.md)
demonstrates the required publication pattern for symbol/quotation findings.
It does not resolve or replace this wider historical-Release alignment audit.
