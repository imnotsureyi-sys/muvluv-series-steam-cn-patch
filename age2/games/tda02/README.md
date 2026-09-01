# THE DAY AFTER episode:02

- Player release: [TDA02 beta0.1](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1)
- Locale: Simplified Chinese (`zh-Hans`)
- Portable maintained snapshot: [`translations/ja-zh-Hans.csv`](translations/ja-zh-Hans.csv), 6,589 data rows

The release covers dialogue, visible UI, subtitle/name images, fonts, and installer assets. Existing review work includes rank/name consistency, alignment fixes, and military terminology.

The CSV keeps the localized text and Japanese source-field SHA-256; exact
official text comes from the contributor's legal extraction through
[`build_changes.py`](../../tools/egpack/build_changes.py). Generated resources
live in the Release package. Cross-branch/Release alignment remains open, so
changes must retain stable identity and controls and be tested in the calling
scene.
