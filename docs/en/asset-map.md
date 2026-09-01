# Text, terminology, image, and font asset map

[English overview](README.md) · [Research index](research-index.md) ·
[中文](../research/asset-map.md) ·
[asset and release policy](../project/asset-and-release-policy.md)

This page identifies the maintained localization assets and explains why they
do not all belong in `localization/`.

## Placement rule

| Material | Public location | Reason |
| --- | --- | --- |
| Two-pass method, review states, locale naming, shared terminology, generic image/font tools | `localization/` | Reusable without a particular engine or resource slot |
| A game's dialogue, choices, speakers, UI translation, and game-only terms | `AGE2/games/<game>/` or `rUGP/games/<game>/` | Stable IDs, hashes, scenes, locale slots, and writer contracts are game-bound |
| Image copy, paths, dimensions, source locks, and localized identities | The game's `images/`; joint PF/PM authority under `rUGP/evidence/photon/` | Display depends on game paths, parents, locale endpoints, and codecs |
| FPD, EGPACK, ICI, RIO, CRsa, RUO, Cr6Ti, CRip, and Hook code | The corresponding `AGE2/` or `rUGP/` tree | They are unrelated format/runtime families |
| Large approved redistributable image bundles and player packages | This repository's Releases, with manifests/hashes in Git | Keeps versioning and downloads in one project without bloating Git history with thousands of binaries |
| Complete official text/images, containers, temporary candidates, failed batches, raw model responses | Ignored local work directories | Lawful inputs and scratch output are not public project assets; durable results become tools, manifests, recipes, or postmortems |

Complete Japanese scripts and original images therefore do **not** move into
`localization/`. Public tables retain stable IDs and source-field SHA-256 values.
A localizer extracts the source from a lawfully owned copy and joins it locally
by identity and hash.

## Maintained text

| Game | Public source | Current scale |
| --- | --- | ---: |
| TDA00 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda00/translations/ja-zh-Hans.csv) | 3,713 rows |
| TDA01 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda01/translations/ja-zh-Hans.csv) | 8,565 rows |
| TDA02 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda02/translations/ja-zh-Hans.csv) | 6,589 rows |
| TDA03 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda03/translations/ja-zh-Hans.csv) | 6,913 rows |
| The Imperial Capital Burns | [`translations/`](../../AGE2/games/imperial-capital-burns/translations/) | 5,564 main rows, plus auxiliary, choice, speaker, and UI tables |
| photonflowers | [`translations/`](../../rUGP/games/photonflowers/translations/) | 12,964 reviewed rows plus a separate 69-row exact runtime-bound table |
| photonmelodies | [`translations/`](../../rUGP/games/photonmelodies/translations/) | 44,583 reviewed rows plus a separate 151-row exact runtime-bound table |

Counts describe public records, not unique spoken lines, full in-game approval,
or automatic writer authorization. Each game README states whether a table is a
review source, an exact writer input, or a historical snapshot.

Shared series terminology lives in the
[Muv-Luv glossary](../../localization/glossaries/muv-luv.ja-zh-Hans.csv).
Game-only terms remain with that game.

## Image material

| Game/set | Public identity | Binary location |
| --- | ---: | --- |
| TDA00 | 70 WebP paths / 59 unique byte contents | Historical player Release and [manifest](../../AGE2/games/tda00/images/) |
| TDA01 | 93 / 71 | Historical player Release and [manifest](../../AGE2/games/tda01/images/) |
| TDA02 | 100 / 80 | Historical player Release and [manifest](../../AGE2/games/tda02/images/) |
| TDA03 | 152 / 90 | Historical player Release and [manifest](../../AGE2/games/tda03/images/) |
| The Imperial Capital Burns | 315 / 232 | Historical player Release plus [manifest and maintained copy](../../AGE2/games/imperial-capital-burns/images/) |
| photonflowers | 636 authorities | Photon V6 research Release and [manifest](../../rUGP/evidence/photon/images/) |
| photonmelodies | 854 authorities | Photon V6 research Release and [manifest](../../rUGP/evidence/photon/images/) |

The five AGE2 packages contain 730 historical WebP paths; PF/PM contain 1,490
image authorities. A path count is not a count of independently redrawn images:
multiple locale suffixes or states may share content, and some entries are
official fallbacks. Photon V6 still contains 19 PNGs byte-identical to official
source files, so it remains a remediation-pending research asset, not a freely
mirrorable player patch.

A maintainable image record consists of resource identity, source hash,
localized copy, approved textless authority, font/layout parameters,
allowed-change region, output hash, and review result. See the
[localized-image workflow](../../localization/image-workflow.md).

## Fonts and a new locale

Shared font provenance, licensing, and glyph-coverage rules live under
[`localization/fonts/`](../../localization/fonts/README.md). Actual selection is
engine-specific: AGE2 must verify loose paths/configuration, while rUGP must
verify registration, family substitution, GDI requests, and the build gate.

Start with the [complete English workflow](../../localization/workflow.en.md)
and [new-locale guide](../../localization/new-locale.md). Extract lawful source
locally, join it by public identities and hashes, keep target text and game-bound
image copy with the relevant game, and contribute only genuinely engine-neutral
rules or tools back to `localization/`.
