# Photon font runtime: from static routes to a guarded proxy

## Why copying a font was insufficient

PF/PM use several AGES registry font routes and also create fonts through the host's GDI import. First launch can rewrite route values, different routes can name different families, Windows may resolve a colliding installed family, and a correct font file does not affect text already rasterized into images.

This produced apparently inconsistent outcomes: Chinese worked in one surface but fell back elsewhere; a route looked correct before launch but changed; an old RUO caused an unrelated Internal Error and contaminated a font test.

## Investigative stages

1. Audit all four PF and four PM route values and the actual GDI family requested by the 32-bit process.
2. Build a uniquely named OFL font rather than relying on a common system family.
3. Add the zero-width `U+2060` glyph required by the explicitly capacity-padded runtime text and test it through FreeType plus 32-bit GDI.
4. Install/rollback the font and registry routes transactionally, keeping an exact ledger and refusing mixed unknown states.
5. Isolate font tests from both old RUOs; the known PM RUO independently reproduced the error and was not evidence against the font.
6. Integrate the proven behavior into the production `Ages3ResT.dll` proxy so the package is self-contained and version-gated.

## Current solution

The PF/PM-specific proxy verifies the host executable, private original plugin and `PhotonR2-Regular.ttf` by hash. On the first official plugin call it privately loads the font, writes all four game routes to the unique `PhotonR2` family, forwards the original exports, and replaces the host's single `CreateFontIndirectW` import with a narrow face-name rewrite. A guardian observes route changes and exposes status telemetry.

`DllMain` remains inert to avoid loader-lock work. Unknown hashes, missing dependencies, wrong architecture, multiple/unexpected imports, or failed initialization stop the route instead of falling back silently.

## Lessons

- Font coverage, family selection, GDI request interception, text capacity and rasterized UI are separate layers.
- Test one transaction at a time on a clean baseline.
- A global/system font replacement is unnecessary and unsafe; use a private unique family scoped to the exact game.
- A font fix needs observable runtime evidence and rollback, not just a screenshot where one line happened to render.
