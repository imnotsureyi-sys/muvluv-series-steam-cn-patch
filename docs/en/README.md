# Muv-Luv Series Steam Community Localization

[简体中文](../../README.md) · [Player guide](player-guide.md) · [Contributors and acknowledgments](../project/CONTRIBUTORS.md) · [Documentation index](../README.md)

This is an unofficial, non-commercial localization project for selected Steam Muv-Luv titles. It preserves Simplified Chinese test patches and reusable text, terminology, image, font, format and reverse-engineering work for other language teams.

You must own the matching game. This repository does not provide the games, cracks, complete original assets or an original Steam `pack.bin`.

## Choose an entry point

GitHub automatically presents the repository README and license as tabs; it
does not support arbitrary extra README tabs. These four maintained pages are
the stable entry points for different audiences:

| Audience | Entry | Contents |
| --- | --- | --- |
| Players installing or removing the Chinese patch | **[Player guide](player-guide.md)** | Downloads, verification, installation, removal, compatibility and reporting |
| AGE2 / TDA / Imperial Capital Burns researchers | **[AGE2](../../AGE2/README.md)** | FPD, EGPACK, WebP, fonts, loose overlays, per-game assets and tests |
| rUGP / AGES / Photon researchers | **[rUGP](../../rUGP/README.md)** | ICI, RIO, CRsa, RUO, Cr6Ti, CRip, Hook, error 8311 and runtime behavior |
| Korean, Russian and other localization teams | **[Localization workspace](../../localization/README.md)** | Two-pass translation, terminology, images, fonts, new-locale setup, QA and player feedback |

For investigations organized by problem and evidence, use the
[research index](research-index.md).

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
| Image copy, layout and identity | [730 WebP paths across TDA00–03 and Imperial Capital Burns](../../AGE2/games/README.md), [Imperial image-copy tables](../../AGE2/games/imperial-capital-burns/images/copy/), [1,490 Photon entries](../../rUGP/evidence/photon/images/) and the [image workflow](../../localization/image-workflow.md) |
| Fonts | [Font asset and licensing policy](../../localization/fonts/README.md), [coverage tool](../../localization/tools/font_coverage.py), [rUGP runtime postmortem](../../rUGP/docs/postmortems/font-runtime.md) and [AGE2 retired-workaround record](../../AGE2/docs/postmortems/font-glyph-substitution-retired.md) |
| Translation and review | [Complete workflow](../../localization/workflow.md), [first-pass standard](../../localization/standards/translation.md) and [independent review standard](../../localization/standards/review.md) |
| Engine tooling | [AGE2 tools](../../AGE2/tools/), [rUGP formats](../../rUGP/formats/), [rUGP runtime](../../rUGP/runtime/) and [shared localization tools](../../localization/tools/) |

Editable tables, image identity/copy/layout data, deterministic tooling and technical conclusions are public. Image and font binaries enter Git only after their provenance and redistribution terms are clear; extracted originals, failed batches and unreviewed fonts stay outside the public tree.

The maintained localization loop is: understand the story and establish
terminology; create the first translation by complete scene; independently
review each row as `keep`, `revise` or `question`; resolve open questions;
perform engine-specific writeback and automated/in-game QA; and feed player
reports back into the maintained source. It is documented in the
[complete workflow](../../localization/workflow.md) so another language team
can reuse the method without copying the Chinese wording.

## Repository layers

```text
AGE2/          AGE2 game assets, format tools, tests and incident records
rUGP/          rUGP game assets, codecs, runtime, packaging and evidence
localization/  engine-neutral translation, terminology, image and font workflow
docs/          player, research, project, legal and English documentation
.github/       CI and contribution templates
```

AGE2 and rUGP are independent implementations and must not import each other.

## License, contribution and acknowledgments

[Contributing](../project/CONTRIBUTING.md) · [Contributors and acknowledgments](../project/CONTRIBUTORS.md) · [Asset and release policy](../project/asset-and-release-policy.md) · [Third-party work](../legal/THIRD_PARTY.md) · [Notices](../legal/NOTICE.md)

Original project code is under the [MIT License](../../LICENSE). That license does not grant rights to game content, translations, fonts, derived images, release payloads or third-party components.
