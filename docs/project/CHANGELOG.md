# 变更记录 / Changelog

This file records repository and public-patch changes. Downloadable packages and their checksums remain attached to [GitHub Releases](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases).

## Unreleased — repository architecture

- 建立中文优先的四类入口：玩家、AGE2 研究者、rUGP 研究者和其他语言本地化制作者。
- 为七部游戏加入统一 `project.toml`，明确引擎、Steam App ID、文本、图片与字体权威。
- 从五个 AGE2 历史 Release 机械生成 730 个 WebP 路径的可复核清单；PF/PM 继续分别索引 636/854 项共用 Photon 图片权威。
- 公开“剧情与术语 → 第一次翻译 → 第二次 `keep/revise/question` 审核 → 技术写回 → 实机与玩家反馈”的完整工作流。
- 新增贡献者与具体致谢页，记录人类维护责任、OpenAI Codex 的受监督辅助，以及主任保护协会、GARbro、AFHook、rugptools 与 FatePackageManager 的准确贡献边界。
- 将活动证据目录改为稳定语义路径，版本留在 schema、Git 历史和 Release tag 中。
- 规定新表的规范字段，同时保留已有哈希封存表的历史表头，避免为表面统一破坏来源证明。

- Split the unrelated AGE2 and legacy rUGP implementations into independent top-level systems.
- Promoted stable translation tables, format libraries, runtime source, packaging code, tests, and release evidence; removed one-off workstation probes from the public tool surface.
- Added English and Chinese player/developer entry points, rights boundaries, provenance guidance, and reusable image-localization documentation.
- Added direct player-package links, exact LocalAppData destinations, checksum instructions and explicit rollback/Steam Verify boundaries for all five historical AGE2 betas.
- Published 57,547 reviewed Photon dialogue rows without the complete official Japanese dialogue, together with stable IDs, exact source-field hashes and reproducible export evidence.
- Added the read-only GARbro-derived ICI/RIO catalogue, conservative CRsa extraction CLI, and synthetic regressions without redistributing game archives.
- Added a safe first-image decoder that turns one exact catalogued Cr6Ti/CRip007/CRip008 extent into a review PNG and path-redacted report without modifying the RIO.
- Added the 1,490-entry Photon locale-route authority and verifier, distinguishing 1,448 translation peers from 42 proven shared/common endpoints.
- Added fail-closed, reproducible Photon runtime builds and a hash-locked package assembler for already sealed roots; the clean-install-to-sealed-root pipeline remains incomplete.
- Documented rUGP investigations including AGES Internal Error 8311, RUO overlays, Cr6Ti, CRip007, CRip008, CRsa, fonts, and shared/common image routing.
- Preserved the ICI duplicate-size/outer-header metadata failure and the native/RUO/runtime image-transport failure chain as bounded postmortems rather than publishing data-specific repair probes.
- Replaced bulk Japanese AGE2 dialogue fields with source hashes while preserving stable context and Chinese work; added provenance reports and an open historical-Release alignment audit.
- Added explicit `text`/`structural_empty` AGE2 record kinds so five legal engine bookkeeping slots round-trip through the public exporter and are verified no-ops, plus a 246-identity text-free manual review ledger for symbol/quotation findings.
- Fixed the Imperial phase-one builder's previously unreachable installer path and made a valid font-license input mandatory when packaging its font.
- Added a strict local-source-to-EGPACK change builder, portable AGE2 text exporter, engine-neutral locale-template generator, font coverage audit, deterministic image authoring tools and tests.
- Added a read-only, synthetic-tested Steam depot-manifest content checker so AGE2 and rUGP builders can bind selected legal local inputs to a reviewed file/chunk map without publishing workstation paths.
- Added a strict PF/PM Steam locale preflight with app-ID, dual-language-field and apply-time manifest-seal checks for future Photon installers; other rUGP games remain fail-closed.
- Added an exact machine-readable index for all five historical player ZIPs and the reviewed Photon image asset, including hashes, sizes, install roots and known safety limitations.
- Hardened public artifact writers, the Photon runtime builder, Imperial image routes and rUGP evidence exporters against partial output, overwrite races, path escape, target swaps, malformed identities and case-insensitive collisions.
- Removed the obsolete lossy Chinese-to-Japanese glyph substitution helper rather than presenting it as font support.
- Expanded Windows/Linux CI to run AGE2, rUGP and engine-neutral localization suites plus source compilation, repository-policy checks and pinned Zig runtime builds.
- Added a `docs/` audience hub and clarified the repository-vs-Release checksum names, file-size thresholds and sanitized historical-package caveats.
- Audited every public Release asset and synchronized the root guides, machine-readable index, and Release-page warnings: known-bad versions are visibly superseded, current historical packages are marked rights-remediation pending, and the Photon V6 asset is explicitly a non-installer research artifact.
- Replaced Imperial telop and event-card Japanese prose with exact source hashes and line-count evidence while retaining stable resource identities and localized copy.
- Made Photon package timestamps explicit, recorded the Python/NumPy/zlib build environment, and added CI smoke tests for every documented public CLI entry point.
- Hardened repository policy against force-added local/generated roots, binary payloads, symlinks, unsafe Release identifiers, hidden download links, workstation paths, and high-confidence credential patterns.
- Retired obsolete public development branches after preserving a verified local recovery bundle; historical Release tags and hidden pull-request refs still require a separately authorized migration/purge.

## Published Simplified Chinese test patches

| Release | Notable scope |
| --- | --- |
| The Imperial Capital Burns beta0.1 | Dialogue, speakers, choices, system UI, image text, name/date/location cards, font and loose-overlay installer |
| TDA03 beta0.1.6 | Current TDA03 package, including achievement-related fixes |
| TDA02 beta0.1 | Dialogue, visible UI, subtitle/name images and font |
| TDA01 beta0.2.2 | Consolidated dialogue, terminology, image and display feedback fixes |
| TDA00 beta0.1 | JP-baseline workflow with speaker, ruby and XML-call-order auditing |

Older test versions remain visible on the Releases page for provenance and are now marked superseded or do-not-install. Even the latest historical packages remain distribution-remediation pending and are not recommended as new policy-compliant builds.
