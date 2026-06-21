# TDA00 Total Translation Audit

## Summary

- baseline_rows: 3713
- final_rows: 3713
- review_rows: 3713
- second_review_rows: 3713
- decision_rows: 0
- order_mismatches: 0
- missing_final_ids: 0
- extra_final_ids: 0
- empty_cn: 0
- control_damage: 0
- newline_damage: 0
- model_garbage: 0
- english_sentence_residual: 0
- kana_residual: 0
- ellipsis_punctuation_residual: 0
- quote_length_24_25_residual: 0
- fixed_term_bad_residual: 0
- duplicate_review_rows: 14
- batch_hard_issue_rows: 0
- batch_second_review_issue_rows: 0
- second_review_non_ok_rows: 0
- review_term_issue_flags: 0
- naturalness_change_report_rows: 214

## Gate Result

- PASS: JP baseline order, final rows, hard batch audits, JP-slot second reviews, naturalness checks, control checks, and quote-wrap boundary checks are clean.

## Notes

- Duplicate review rows are written to `chapters\TDA00\translation\tda00_total_duplicate_review.csv` for human inspection; repeated battle barks and acknowledgements can be legitimate.
- Kana/Japanese residual review rows are written to `chapters\TDA00\translation\tda00_total_jp_residual_review.csv`; shared CJK ideographs are not counted here.
- Final-CN newline damage rows are written to `chapters\TDA00\translation\tda00_total_newline_review.csv`; real newlines render as square glyphs in-game.
- Natural Chinese review changes are written to `chapters\TDA00\translation\tda00_natural_cn_review_changes_utf8bom.csv`.
- This audit does not apply any English-slot fallback and checks against the frozen JP call-order baseline.
