# AGE2 quality gates

These gates define acceptance for a new build; they are not a retroactive claim about the five historical beta packages. Their known manifest, checksum, rollback and license-notice limitations are listed in the [player guide](../../docs/player/README.md).

## Structural

- The complete source `pack.bin` matches the approved SHA-256 (and reviewed Steam depot content map where available); FPD header/index/path/offset/stored-length/output-length checks pass. FPD v2 exposes no per-file CRC field.
- EGPACK records have the expected field set and order; output reparses.
- Only explicitly authorized `(relative_path, id, slot)` values change.
- WebP dimensions, mode, transparency, and expected source/output hashes match.
- Loose paths are relative, traversal-free, and scoped to one game.

## Text

- no empty required translation, `Text ID Not Found`, row drift, garbled UTF-8, unintended English fallback, or damaged `\p`/`\w`/`\f` controls;
- speaker, ruby, voice, XML call order, rank/name and terminology are checked in context;
- line breaks are tested in-engine rather than mechanically copied from Japanese.

## Player build

- supported original `pack.bin` hash is checked before installation;
- no original archive/executable/save is modified;
- font binary and license are paired;
- install manifest is complete and restore instructions are tested;
- the downloaded Release asset is reinstalled onto a clean game after publishing.

## CI platform boundary

Archive, text, manifest, path and non-font image tests run on both Windows and
Linux. Four unit-level pixel-geometry tests use the locally installed
`msyhbd.ttc` fixture and run only when that test font is available. They prove
rendering mechanics, not the metrics or pixels of the shipped Source Han Sans
font; Linux reports them as explicit skips instead of silently substituting
another font. A release candidate still requires a separate integration build
with the hash-locked `SourceHanSansSC-Bold.otf`, its license, generated contact
sheets, and in-game review. CI must not be described as that release-font gate.
