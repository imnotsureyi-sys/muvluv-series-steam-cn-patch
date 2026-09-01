# TDA03 achievement mapping incident

Affected releases: TDA03 beta0.1 through beta0.1.5
Corrected release: TDA03 beta0.1.6

## Symptom

The loose overlay contained a readable and structurally valid `uistring.epk`,
but its chapter/achievement table belonged to TDA02. A file that opened and
displayed localized strings was therefore still wrong for the target game.

## Unsafe assumption

The build treated a same-named AGE2 resource from another episode as reusable.
Matching container format, field IDs or a few visible UI strings does not prove
game-specific semantic identity.

## Controlled comparison

The corrected audit decoded the candidate against the untouched TDA03 JP
resource and enumerated the complete achievement mapping. The required TDA03
set contains 16 entries, `achievement_0001` through `achievement_0016`. The
first maps to `2005年01月01日_02：オープニング.xml`; the last maps to
`2006年02月19日_01：白銀武.xml`. A scan of the repaired resource found zero
TDA02 script paths and zero `Text ID Not Found` values.

## Root cause and repair

The wrong episode's generated `uistring.epk` entered the packaging input. The
repair rebuilt from TDA03's own Japanese table, changed only the intended
localized values, and retained TDA03's 16-entry mapping. The beta0.1.6 payload
also retained `hiscore.conf`, `readme.txt` and `resident.list` when rebuilding
`data/root`, while excluding user progress such as `.hiscore` and
`udat_rel.bin`.

## Production rule

- Bind every generated resource to game ID, logical path, source SHA-256 and
  output SHA-256; a filename is not an identity.
- Never reuse a same-named EPK/EGPACK across episodes without a field-by-field
  equality proof.
- Verify the complete called achievement/chapter set, not one visible string.
- Package only from a game-scoped staging root and reject cross-game inputs.

## Remaining boundary

The historical beta0.1.6 ZIP predates the current repository Release gates: it
does not include the new complete install manifest/checksum/license bundle and
contains a diagnostic report with a developer path. The semantic fix is real,
but a future repack should also satisfy the current publication policy.
