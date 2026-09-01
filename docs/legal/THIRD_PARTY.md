# Third-party software and prior work

This project distinguishes learning from a design, depending on a tool, and copying its code. Unless a source file explicitly says otherwise, the code in this repository is independently maintained under the root MIT license.

## Direct technical references

| Project | License observed upstream | How it relates to this repository |
| --- | --- | --- |
| [GARbro](https://github.com/morkt/GARbro/tree/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0) | MIT | `rUGP/tools/catalog/rio_inventory.py` contains a maintained Python port of [`ArcFormats/rUGP/ArcRIO.cs`](https://github.com/morkt/GARbro/blob/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0/ArcFormats/rUGP/ArcRIO.cs) (upstream file SHA-256 `DEF71FDDD334C6DC2BD03671600A3F4C3987355CE9C2E579C32EF1F73FDB4AB5`). The complete morkt copyright/MIT notice is retained in that source file. No GARbro binary or game asset is vendored. |
| [AFHook](https://github.com/eplightning/afhook/tree/3f613a097c07d3d9fb9969a130ea6d859b544f8a) | MIT | Separates an authoring editor from the in-game rUGP/AGES runtime plugin. It informed the authoring/runtime boundary; this project's Photon runtime is independently version-gated for its own targets and does not copy AFHook code. |
| [rugptools](https://github.com/osmium76/rugptools/tree/3ff587416e41eeeee7122fb122c90f7a36c409dd) | GPL notice in README for original portions; no clear repository-wide license file observed | Historical rUGP/alterdec behavior and terminology reference only. No code is copied because the licensing boundary is not sufficiently clear. |
| [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager/tree/080c2cac36391e2d2de473f8f8a841b08cf752dc) | MIT | Primary reference implementation for AGE2 FPD v2 extraction/repacking and the `Scrambler.cs` key schedule (observed file SHA-256 `5AA8BCEFB9F2F1D14917FE11027B32FFFFD0A8C8C3F25C3AE8D690827EEAE33E`). This repository derives keys from a user-supplied upstream file instead of maintaining a second copied table. |

## Repository and workflow references

The following projects were studied for boundaries and maintenance practices, not treated as drop-in dependencies: [thcrap](https://github.com/thpatch/thcrap), [07th-Mod python-patcher](https://github.com/07th-mod/python-patcher), [Committee of Zero SGHD Patch](https://github.com/CommitteeOfZero/sghd-patch), [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation), [VNTranslationTools](https://github.com/arcusmaximus/VNTranslationTools), and [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2).

The useful patterns were player/developer separation, language layers, input hashes, plugin/format boundaries, generated-release exclusion, and keeping scripts/images/fonts/build logic visibly distinct. Their licenses do not automatically apply here, and their game assets are not reused.

## Build dependencies

- Python dependencies are declared per boundary in `AGE2/requirements.txt`, `rUGP/requirements.txt`, and `localization/requirements.txt`; the root development file installs all three. They retain their upstream licenses.
- Photon native builds use [Zig](https://ziglang.org/) 0.16.0; Zig is not vendored.
- CI actions are pinned to immutable commits in `.github/workflows/quality.yml`.
- Fonts are release-time inputs. A font and its license must be distributed together; font binaries are not tracked in this Git tree.

For any new dependency, record the exact version, upstream URL, license, whether code or data is copied, and the reproducibility/security reason for using it.
