<p align="right">
  <a href="../../README.md"><img alt="简体中文" src="https://img.shields.io/badge/%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-%E9%98%85%E8%AF%BB-C62828?style=for-the-badge"></a>
  <a href="README.md"><img alt="English" src="https://img.shields.io/badge/English-Current-2F81F7?style=for-the-badge"></a>
</p>

# Muv-Luv Series Steam Community Localization

This is an unofficial, non-commercial localization project for selected Steam
Muv-Luv titles. It preserves Simplified Chinese test patches and publishes the
translation, terminology, image, font, format-tooling, and reverse-engineering
work needed by other language teams.

You must own the matching game. This repository does not provide the games,
cracks, complete original assets, or an original Steam `pack.bin`.

## Choose one entry

| **Players** | **Localizers and researchers** |
| --- | --- |
| **[Download, install, restore, and troubleshoot](player-guide.md)** | **[Texts, images, fonts, tools, and research](research-index.md)** |
| Only the package status, links, and safety information players need. | The asset map, multilingual workflow, AGE2, rUGP, and incident records. |

## Current status

| Scope | Player status | Public production/research material |
| --- | --- | --- |
| TDA00–03 and The Imperial Capital Burns | Historical AGE2 test packages are preserved; version, font-license, official-fallback, and rollback remediation remains | Maintained text, inventories for 730 historical WebP paths, Imperial image copy, FPD/EGPACK tools, and loose-overlay findings |
| photonflowers and photonmelodies | No player installer yet | Maintained text, a 1,490-image PF/PM authority and route map, ICI/RIO/CRsa/RUO/Cr6Ti/CRip tools, guarded runtime components, and postmortems |

The historical packages are identifiable and installable, but they are not
marked recommended until the present release gate is satisfied. Follow the
[player guide](player-guide.md). The 1,490-image Photon Release is a research and
localization asset, not an installer.

## Repository map

| Directory | Responsibility |
| --- | --- |
| [`localization/`](../../localization/README.md) | Engine-neutral two-pass translation, terminology, image production, font checks, and new-locale workflow |
| [`AGE2/`](../../AGE2/README.md) | TDA/Imperial game-bound text and image identities, FPD, EGPACK, WebP, loose overlays, tests, and postmortems |
| [`rUGP/`](../../rUGP/README.md) | Photon game-bound text and image identities, ICI, RIO, CRsa, RUO, Cr6Ti, CRip, runtime, and postmortems |
| [`docs/`](../README.md) | Player, research, maintenance, legal, and English documentation |

See the **[text, terminology, image, and font asset map](asset-map.md)** for
actual counts and placement rules. Engine-neutral methods live in
`localization/`; anything bound to a game resource ID, locale slot, path, or
codec lives under that game's `AGE2/games/` or `rUGP/games/` directory. Complete
official source assets are extracted locally from a contributor's lawful copy
and are never committed.

## Localization workflow

The maintained process is: establish story context and terminology; produce a
first translation; independently classify every row as
`keep`/`revise`/`question`; resolve questions; bind through the correct engine;
run in-game QA; and feed player reports back into maintained source.

- [Complete English workflow](../../localization/workflow.en.md)
- [Start Korean, Russian, or another locale](../../localization/new-locale.md)
- [Localized image and Image 2 workflow](../../localization/image-workflow.md)
- [Chinese workflow](../../localization/workflow.md)

## Credits and participation

The project thanks 主任保护协会 for the original AGES localization approach
that started this patch-making effort. GARbro, AFHook, rugptools,
FatePackageManager, and mature patch projects supplied narrowly attributed
technical precedents. See [contributors and acknowledgments](../project/CONTRIBUTORS.md)
and the [reference comparison](../research/references.md).

[Report a patch/runtime problem](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)
· [Suggest a translation correction](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml)
· [Contribute](../project/CONTRIBUTING.md)

Original code is under the [MIT License](../../LICENSE). MIT does not
automatically license game content, translation text, fonts, derivative images,
release packages, or third-party components. See the
[asset and release policy](../project/asset-and-release-policy.md),
[third-party notices](../legal/THIRD_PARTY.md), and [legal notice](../legal/NOTICE.md).
