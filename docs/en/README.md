# Muv-Luv Series Steam Community Localization

[简体中文](../../README.md) · [Player guide](player-guide.md) · [Build another locale](../../localization/new-locale.md) · [Research index](research-index.md)

This is an unofficial, non-commercial localization project for selected Steam Muv-Luv titles. It preserves Simplified Chinese test patches and reusable text, terminology, image, font, format and reverse-engineering work for other language teams.

You must own the matching game. This repository does not provide the games, cracks, complete original assets or an original Steam `pack.bin`.

## Start here

| Goal | Entry |
| --- | --- |
| Install or remove a Chinese patch | [Player guide](player-guide.md) |
| Build Korean, Russian or another locale | [Localization workspace](../../localization/README.md) and [new-locale guide](../../localization/new-locale.md) |
| Work with FPD, EGPACK, WebP and loose overlays | [AGE2](../../AGE2/README.md) |
| Work with ICI, RIO, RUO, CRsa, image records and the runtime | [rUGP](../../rUGP/README.md) |
| Review evidence and solved/failed investigations | [Research index](research-index.md) |

## Player downloads

These historical prereleases were preserved during the repository migration. They predate the current release gate and remain under font-license, official-fallback-resource, input-version and rollback remediation, so they are not currently marked as recommended downloads. Read the [player guide](player-guide.md) and back up the exact LocalAppData overlay first. Do not use GitHub's source-code ZIP as a patch.

| Game | Preserved version | Download |
| --- | --- | --- |
| THE DAY AFTER episode:00 | beta0.1 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1.zip) · [release](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1) |
| THE DAY AFTER episode:01 | beta0.2.2 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2.zip) · [release](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2) |
| THE DAY AFTER episode:02 | beta0.1 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1.zip) · [release](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1) |
| THE DAY AFTER episode:03 | beta0.1.6 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda03-beta0.1.6/MuvLuv_TDA03_CN_Patch_beta0.1.6_full_achievement_fix.zip) · [release](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1.6) |
| The Imperial Capital Burns | beta0.1 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/imperial-capital-burns-beta0.1/MuvLuv_Imperial_Capital_Burns_CN_Patch_beta0.1.zip) · [release](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/imperial-capital-burns-beta0.1) |

Photon Flowers and Photon Melodies do not yet have player-ready installers.

## Where the localization assets live

| Asset | Location |
| --- | --- |
| Dialogue, choices, speakers and UI strings | Per-game `translations/` under [AGE2 games](../../AGE2/games/), [Photon Flowers](../../rUGP/games/photonflowers/) and [Photon Melodies](../../rUGP/games/photonmelodies/) |
| Shared terminology | [Muv-Luv glossary](../../localization/glossaries/muv-luv.ja-zh-Hans.csv) and [terminology policy](../../localization/standards/terminology.md) |
| Image copy, layout and identity | [Imperial image-copy tables](../../AGE2/games/imperial-capital-burns/images/copy/), [Photon image authority](../../rUGP/evidence/photon-images-v6/) and the [image workflow](../../localization/image-workflow.md) |
| Fonts | [Coverage tool](../../localization/tools/font_coverage.py), [rUGP runtime postmortem](../../rUGP/docs/postmortems/font-runtime.md) and [AGE2 retired-workaround record](../../AGE2/docs/postmortems/font-glyph-substitution-retired.md) |
| Engine tooling | [AGE2 tools](../../AGE2/tools/), [rUGP formats](../../rUGP/formats/), [rUGP runtime](../../rUGP/runtime/) and [shared localization tools](../../localization/tools/) |

Editable tables, image identity/copy/layout data, deterministic tooling and technical conclusions are public. Image and font binaries enter Git only after their provenance and redistribution terms are clear; extracted originals, failed batches and unreviewed fonts stay outside the public tree.

## Repository layers

```text
AGE2/          AGE2 game assets, format tools, tests and incident records
rUGP/          rUGP game assets, codecs, runtime, packaging and evidence
localization/  engine-neutral translation, terminology, image and font workflow
docs/          player, research, project, legal and English documentation
.github/       CI and contribution templates
```

AGE2 and rUGP are independent implementations and must not import each other.

## License and contribution

[Contributing](../project/CONTRIBUTING.md) · [Asset and release policy](../project/asset-and-release-policy.md) · [Third-party work](../legal/THIRD_PARTY.md) · [Notices](../legal/NOTICE.md)

Original project code is under the [MIT License](../../LICENSE). That license does not grant rights to game content, translations, fonts, derived images, release payloads or third-party components.
