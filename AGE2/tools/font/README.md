# Font checks

The former `font_compat_zh.py` did **not** inspect a font. It performed a
lossy Simplified-Chinese-to-Japanese-glyph substitution and belonged to an
abandoned workaround. It has been removed so it cannot be mistaken for a
release gate.

Use the engine-neutral
[`localization/tools/font_coverage.py`](../../../localization/tools/font_coverage.py)
to compare a candidate font's Unicode cmap with one or more translation
tables. Coverage is only the first gate: line height, fallback, shaping,
clipping and runtime font selection still require in-game testing.
