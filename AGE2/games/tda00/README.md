# THE DAY AFTER episode:00

- Player release: [TDA00 beta0.1](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1)
- Locale: Simplified Chinese (`zh-Hans`)
- Portable maintained snapshot: [`translations/ja-zh-Hans.csv`](translations/ja-zh-Hans.csv), 3,713 data rows

The patch uses the frozen Japanese EGPACK fields as authority and includes localized dialogue, UI/image/video text, fonts, and installer assets in the Release package. Speaker, ruby, XML call order, control sequences, and visible slot selection were audited separately from prose review.

The complete official Japanese strings are not mirrored: each row keeps a
source-field SHA-256 and is joined to a legal local extraction with
[`build_changes.py`](../../tools/egpack/build_changes.py). This is maintained
source data, not a ready-to-install payload. The cross-branch/Release
alignment audit is still open; see
[`authority-alignment-audit.md`](../../evidence/translation-snapshots-v1/authority-alignment-audit.md).
TDA00 has less full-route player feedback than TDA01–03; corrections should
include a screenshot and surrounding Japanese context.
