# Documentation hub

[Repository home](../README.md) · [简体中文首页](../README.zh-CN.md)

This directory has three entry points. Choose the one that matches what you
are trying to do; a published beta, a reproducible research artifact and a
complete end-to-end patch builder are not the same thing.

## Players

Start with the [English player guide](player-guide.md) or the
[简体中文玩家指南](player-guide.zh-CN.md). They lead to the exact historical
AGE2 release ZIPs and explain installation, SHA-256 checks, compatibility,
rollback and bug reports. Do not download GitHub's repository source ZIP as a
patch. Photon Flowers / Photon Melodies do not yet have a player-ready package.

The machine-readable [release index](release-index.json) preserves the exact
asset name, byte count, SHA-256, install target and known historical caveats
for every currently listed player package.

## Localization teams

Begin with the [new-locale guide](../localization/new-locale.md), then use the
engine-neutral [localization workflow](../localization/README.md). It covers
stable source identity, translation/review tables, terminology, font coverage,
image authoring and tests. Continue through either the independent
[AGE2 workflow](../age2/docs/workflow.md) or
[legacy rUGP workflow](../rugp/docs/workflow.md); their formats and builders
must not be mixed.

Before publishing, read the [release process](release-process.md) and
[asset/release policy](asset-and-release-policy.md). A production build still
requires legally obtained game inputs, approved redistributable fonts/assets
and in-game QA; synthetic tests cannot supply those inputs.

## rUGP/AGE researchers

Use the [research index](research-index.md) as the claim-and-evidence map. It
links format code, fixtures, tests, provenance boundaries, prior art and the
[rUGP postmortems](../rugp/docs/postmortems/README.md), including failed
hypotheses and the 8311, CRsa, RUO, Cr6Ti, CRip007/008, font and shared/common
image investigations, plus the ICI-resize and image-transport/runtime failure
chains. The [repository architecture](repository-architecture.md)
explains why durable tools, evidence and postmortems are public while extracted
games, temporary probes and rejected/generated scratch output stay outside
Git.

The code documents only behavior demonstrated for the stated game/build and
fixture. It is not a universal one-click rUGP unpacker/repacker, and a reader
that can decode one record kind does not imply a complete writer for it.

## Reference and project policy

- [References and prior art](references.md)
- [Repository architecture](repository-architecture.md)
- [Release process](release-process.md)
- [Asset and release policy](asset-and-release-policy.md)
- [Contribution guide](../CONTRIBUTING.md)
- [Roadmap](../ROADMAP.md) and [changelog](../CHANGELOG.md)
