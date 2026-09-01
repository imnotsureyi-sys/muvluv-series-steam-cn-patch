# Muv-Luv community localization patches and tooling

[简体中文](README.zh-CN.md) · [Player downloads](#player-downloads) · [Documentation hub](docs/README.md) · [Player guide](docs/player-guide.md) · [Start another locale](localization/new-locale.md) · [Research index](docs/research-index.md) · [Contributing](CONTRIBUTING.md)

This is an unofficial, non-commercial localization project for selected Steam releases in the Muv-Luv series. It currently publishes Simplified Chinese **test patches** and preserves reusable AGE2 and legacy rUGP research for other localization teams.

You need a legally purchased copy of each game. This repository does not contain the games, cracks, complete original archives, or Steam's original `pack.bin` files.

## Choose your path

| I want to… | Start here | What is available now |
| --- | --- | --- |
| Install and play a Chinese patch | [Player downloads](#player-downloads), then the [player guide](docs/player-guide.md) | Five historical AGE2 beta packages; Photon has no player installer yet |
| Build Korean, Russian, or another locale | [New-locale guide](localization/new-locale.md), then choose [AGE2](age2/README.md) or [legacy rUGP](rugp/README.md) | Reusable formats and workflow, with important end-to-end gaps recorded below |
| Study rUGP/AGES or AGE2 reverse engineering | [Research index](docs/research-index.md) and [rUGP postmortems](rugp/docs/postmortems/README.md) | Code, tests, evidence and failed hypotheses; not a universal one-click unpacker/repacker |

## Player downloads

These are prerelease/test packages. Download the ZIP for the exact game; do **not** use GitHub's repository source ZIP as a patch.

**Current distribution status:** these historical packages are technically installable, but the index marks them “not recommended / not distribution-approved” while bundled font notices and copied official UI fallbacks are remediated. The direct links below identify the existing historical Releases accurately. Players who require today's release gate should wait for rebuilt packages; anyone still testing must read the limitations and back up first.

**Compatibility prerequisite:** none of these five historical packages preserves an exact Steam build/depot identity or original `pack.bin` hash. Every current Steam build is therefore “not pre-verified,” not confirmed compatible. Back up that game's own LocalAppData overlay before installation; a successful copy is not a version check.

| Game | Direct Windows ZIP | Release notes and checksum |
| --- | --- | --- |
| THE DAY AFTER episode:00 | [TDA00 beta0.1 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1.zip) | [Release page](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1_SHA256SUMS.txt) |
| THE DAY AFTER episode:01 | [TDA01 beta0.2.2 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2.zip) | [Release page](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2_SHA256SUMS.txt) |
| THE DAY AFTER episode:02 | [TDA02 beta0.1 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1.zip) | [Release page](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1_SHA256SUMS.txt) |
| THE DAY AFTER episode:03 | [TDA03 beta0.1.6 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda03-beta0.1.6/MuvLuv_TDA03_CN_Patch_beta0.1.6_full_achievement_fix.zip) | [Release page](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1.6) · SHA-256 `4B6CA4A531E9D07315E84DC2E02D7D8008C9B78EA4466172B45CAD1CEBA5C67D` |
| The Imperial Capital Burns | [beta0.1 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/imperial-capital-burns-beta0.1/MuvLuv_Imperial_Capital_Burns_CN_Patch_beta0.1.zip) | [Release page](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/imperial-capital-burns-beta0.1) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/imperial-capital-burns-beta0.1/MuvLuv_Imperial_Capital_Burns_CN_Patch_beta0.1_SHA256SUMS.txt) |

Use only the versions in this table. `tda01-beta0.1`, `tda01-beta0.2`, `tda01-beta0.2.1`, and `tda03-beta0.1` are superseded and no longer recommended. TDA01 beta0.2 has 603 invisible dialogue slots; TDA03 beta0.1 was later found to carry TDA02's UI/achievement mapping.

Close the game, extract the entire ZIP, read its `README.txt`, and run `install.bat`. The exact LocalAppData paths, checksum command, rollback limits and reporting instructions are in the [player guide](docs/player-guide.md). Exact asset identities and historical package facts are also preserved in the [machine-readable release index](docs/release-index.json).

Photon Flowers and Photon Melodies currently have source, format code, runtime code and image evidence, but **no player-ready patch**. The [1,490-image Photon Release](rugp/evidence/photon-images-v6/README.md) completed technical/localization identity review, not distribution clearance, and is not an installer; 19 images are byte-identical to official sources and still require redistribution remediation.

### Historical beta limitation

The five packages above predate the repository's current release gate. They do not consistently contain an install manifest, input-version hash gate, uniform rollback tool, or bundled font-license notice. Their font-license bundling and redistribution boundary for copied official UI fallbacks are also under renewed audit, so they must not be represented as new packages that pass today's policy. The machine-readable index records this as `pending-remediation`; until replacement packages remove restricted originals and carry the required font notices, the direct links are accurate pointers to historical Releases, not a compliance endorsement. TDA03 beta0.1.6 lacks a separate checksum attachment, so its GitHub-recorded asset digest is written directly above. Package READMEs remain useful for their installation layout, but the current central player guide overrides unsafe historical rollback advice: in particular, do **not** follow TDA01 beta0.2.2's instruction to delete the whole `...\tda01\data` directory. Never delete `data\user` or save/progress data.

## What can actually be reproduced today

| Scope | Public player result | Public maintained inputs | Rebuild status from a legal clean game |
| --- | --- | --- | --- |
| TDA00–03 (AGE2) | Chinese beta packages published | Dialogue tables, a strict local-source-to-EGPACK join, and shared FPD/EGPACK/UI helpers | **Partial:** historical Release alignment remains under audit, and no complete per-game image/font/build manifest or final-package command exists |
| The Imperial Capital Burns (AGE2) | Chinese beta package published | Text tables, image copy/layout tables, initial inventory and a phase-one builder | **Partial:** historical Release alignment remains under audit; `build_phase1.py` does not reproduce the later full dialogue package by itself, and external FSNr/font inputs remain required |
| Photon Flowers / Photon Melodies (legacy rUGP) | No player package | [57,547 reviewed dialogue rows](rugp/evidence/photon-reviewed-text-v1/README.md), separate 69/151-row exact runtime contracts, a read-only ICI/RIO catalogue and CRsa extractor, a 1,490-image V6 authority and route closure, codecs, runtime source and package builder | **Partial:** no complete clean-install → every payload binding → final approved builder-root pipeline exists yet |

Synthetic Python tests work from a clean source checkout after installing the pinned requirements; native Photon runtime builds additionally require Zig 0.16.0. Production patch reproduction still requires legally obtained game inputs, exact hashes, redistribution-compatible fonts/assets, and manual in-game QA. See the [research index](docs/research-index.md) for the boundary of each claim.

## Two independent engine families

| Area | Games in this repository | Patch model | Start here |
| --- | --- | --- | --- |
| AGE2 | TDA00–03, The Imperial Capital Burns | FPD inspection, EGPACK/WebP localization, loose-file overlay | [`age2/`](age2/README.md) |
| legacy rUGP/AGES | Photon Flowers, Photon Melodies | ICI/RIO/RUO records plus a version-pinned runtime where static replacement is insufficient | [`rugp/`](rugp/README.md) |

The repository uses **AGE2** as its label for the newer FPD/EGPACK-based ports and **legacy rUGP** for the older RIO family. The two implementations do not import each other. Engine-neutral translation, terminology, review and image-authoring practices live under [`localization/`](localization/README.md).

## Repository map

```text
localization/  translation/review policy, glossary, image workflow and new-locale guide
age2/          AGE2 game tables, FPD/EGPACK tools and synthetic tests
rugp/          rUGP codecs, runtime, packaging, evidence, tests and postmortems
docs/          player, research, architecture, rights and release documentation
.github/       CI and contribution templates
```

For the intended boundaries between these directories, current priorities and
notable repository changes, see the [repository architecture](docs/repository-architecture.md),
[roadmap](ROADMAP.md), and [changelog](CHANGELOG.md).

Extracted games, private audit roots, model scratch output, local caches, generated DLLs, patch ZIPs and rejected image candidates are intentionally absent from Git history.

## Tests, feedback and safety

Development checks are documented in [CONTRIBUTING.md](CONTRIBUTING.md). Passing synthetic tests exercises the covered parser/writer branches; it does not replace a clean install, rollback test or full-route game test.

For a patch/runtime problem, [open a bug report](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml). For a translation correction, [open a source-backed translation report](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml).

AGE2 patches are loose files under a per-user LocalAppData tree. Steam verification does **not** remove those files; follow the [rollback instructions](docs/player-guide.md#restore-and-rollback) before using Steam verification to repair Steam-managed originals.

## Credits, license and rights

The project builds on documented ideas and independently verified behavior from the visual-novel tooling community. See [Third-party software](THIRD_PARTY.md), [research references](docs/references.md), and the [research index](docs/research-index.md) for the difference between prior art and this project's PF/PM-specific work.

Special thanks to 主任保护协会 for sharing practical AGES localization experience, to 子冰 for TDA01 testing feedback, and to everyone who supplied screenshots, terminology review and full-route testing.

Original project code is licensed under the [MIT License](LICENSE). That license does **not** grant rights to Muv-Luv game content, translations, fonts, derived images, release payloads, or third-party components. See [NOTICE](NOTICE.md) and the [asset and release policy](docs/asset-and-release-policy.md).
