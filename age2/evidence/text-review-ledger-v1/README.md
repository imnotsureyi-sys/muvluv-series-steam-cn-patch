# AGE2 text-review ledger v1

`pending.csv` is a text-free review queue derived from two private source/translation comparison audits. It contains stable game/resource identities, the already-public source hash, finding categories and review state. It deliberately contains neither official source lines nor localized lines.

The initial ledger has 246 unique pending identities: TDA00 72, TDA01 67, TDA02 77 and TDA03 30. A row can carry more than one semicolon-separated category. Categories are search leads, not automatic corrections: quotation marks can intentionally change with sentence structure, so a human must inspect the legally held source and game context before changing a reviewed translation.

`manifest.json` binds the exact public authorities and private audit inputs that produced the ledger. Rebuild it with [`build_review_ledger.py`](../../tools/text/build_review_ledger.py), using `--translation GAME=PATH` for each portable public table and `--audit KIND=PATH` for each private audit. Every audit row, including a known non-actionable finding excluded from the pending queue, is bound before filtering. The command refuses malformed/ambiguous CSV, source/hash/translation drift and prior output overwrite. Its two output files are individually create-only/atomic with ordinary-error rollback, not a crash-atomic pair.

This queue is a maintenance artifact, not a release blocker by itself. Change `review_status` only through a reviewed follow-up ledger or regenerate a new version; do not silently edit v1 evidence in place.
