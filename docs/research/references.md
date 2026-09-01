# Research references and adopted lessons

References are selected by the problem they solve, not by star count alone. Stars below are intentionally omitted because they change; upstream repository and license state should be rechecked before any code reuse.

## rUGP and AGES formats

- [GARbro](https://github.com/morkt/GARbro): demonstrated that archive navigation and individual format handlers should remain separate. Its MIT-licensed rUGP object-directory reader is the declared source of the maintained Python port in `rUGP/tools/catalog/rio_inventory.py`; GARbro is still not a Photon repacker.
- [AFHook](https://github.com/eplightning/afhook): demonstrated the editor/runtime split for an AGES/rUGP patch. It is the closest conceptual predecessor to the Photon hook route.
- [rugptools](https://github.com/osmium76/rugptools): preserves useful rUGP and alterdec terminology/behavior. Because the repository-wide license boundary is unclear, this project studies observable behavior and does not copy its source.
- alterdec/RioX material referenced by the above projects: historical confirmation for resource decoding concepts, not a complete modern build/release workflow.

## AGE2 packages

- [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager): the principal public reference for FPD v2 (`pack.bin`) structure, key scheduling, extraction, and work-in-progress repacking. Our AGE2 FPD reader requires its `Scrambler.cs` as an explicit input and adds strict range/path/hash checks for this workflow.

## Mature patch structures

- [thcrap](https://github.com/thpatch/thcrap): layered locales, patch data separate from runtime, version checks, update/config boundaries.
- [07th-Mod python-patcher](https://github.com/07th-mod/python-patcher): player-first installation with developer implementation kept behind it.
- [Committee of Zero SGHD Patch](https://github.com/CommitteeOfZero/sghd-patch): visible separation of patch content, installer, launcher, and generated assets.
- [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation): practical `script/`, `images/`, system strings, and tools separation; also a reminder that a clear repository structure does not by itself settle asset rights.
- [VNTranslationTools](https://github.com/arcusmaximus/VNTranslationTools): explicit extraction/insertion boundary and reusable format tooling.
- [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2): plugin boundaries between archives, images, text, and fonts.

## What was not copied

No upstream game's translation or image assets were imported. The direct GARbro port is isolated, attributed, and carries its complete MIT notice; no code was copied from a repository without a sufficiently clear compatible license. General workflow ideas—hash gating, manifests, layered languages, player/developer separation—are not treated as a substitute for independently testing this repository's target games.
