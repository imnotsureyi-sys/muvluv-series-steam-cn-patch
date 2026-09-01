# THE DAY AFTER episode:01

- Player release: [TDA01 beta0.2.2](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2)
- Locale: Simplified Chinese (`zh-Hans`)
- Portable maintained snapshot: [`translations/ja-zh-Hans.csv`](translations/ja-zh-Hans.csv), 8,565 data rows

The current release consolidates multiple rounds of in-game feedback across dialogue, terminology, image text, fonts, and display behavior. The Japanese source field and stable resource identity remain authoritative.

The CSV stores a source-field SHA-256 instead of mirroring every official
Japanese line. Join it to a legal local export with
[`build_changes.py`](../../tools/egpack/build_changes.py). It is source data
rather than an installer, and its historical Release alignment is still under
audit. Future corrections should preserve IDs/order/controls and scene
context; do not keep a fix only in a generated EGPACK.
