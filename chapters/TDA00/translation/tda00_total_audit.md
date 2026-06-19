# TDA00 Total Translation Audit

## Scope

- JP baseline rows: 3713
- DeepSeek raw rows: 3713
- Codex review rows: 3713
- CN final rows: 3713
- speaker table rows: 21
- ruby table rows: 75
- baseline ruby references in called text: 75
- review ruby references in called text: 75

## Hard Checks

- alignment_issue: 0
- empty_cn: 0
- text_id_not_found: 0
- duplicate_cn_abnormal: 0
- term_issue: 0
- speaker_name_body: 0
- english_sentence_residual: 0
- kana_residual: 0
- slash_residual: 0
- jp_prefix_residual: 0
- json_placeholder_garbage: 0
- control_damage: 0
- speaker_mismatch: 0
- ruby_ref_mismatch: 0
- traditional_or_jp_kanji_residual heuristic: 0
- user_decisions_needed rows: 2

## Notes

- JP baseline remains the alignment source; final CSV order is checked against call_order/id/egpack/xml/message position/text_attr/JP/speaker.
- English slots were not used by the batch translation script.
- `\w` was stripped before model input and is not kept in final CN.
- Heuristic traditional/Japanese-kanji hits are listed in the issue CSV for manual inspection; kana/control/slash residuals are hard failures.

## Issue CSV

- `chapters\TDA00\translation\tda00_total_audit_issues.csv`
