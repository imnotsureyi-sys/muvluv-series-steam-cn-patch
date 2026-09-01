# Retired glyph-substitution font workaround

## Failed approach

An early helper attempted to make Simplified Chinese display through a
Japanese-oriented font by replacing words and characters with visually related
Japanese/traditional glyphs. Examples included semantic rewrites as well as
single-character substitution.

This was not font support. It changed the translation itself, could alter
meaning and terminology, duplicated keys, could not prove full coverage, and
said nothing about family selection, metrics, wrapping, clipping or font
redistribution rights.

## Correction

The lossy helper was removed from the maintained tool tree. Current workflow:

1. keep the reviewed target text unchanged;
2. choose a font whose exact licensed face contains the required codepoints;
3. run the public cmap coverage gate against that face;
4. bind the font binary, family/config route and license in the package;
5. test line layout, clipping and representative UI roles in game.

## Production rule

Never repair missing glyphs by silently rewriting localized prose. A deliberate
orthographic editorial choice belongs in review history; a rendering problem
belongs in the font/runtime pipeline.

## Remaining boundary

The repository publishes the coverage checker and documented AGE2 font roles,
but the historical player ZIPs lack a uniform bundled-license notice and do not
yet satisfy the current release gate.
