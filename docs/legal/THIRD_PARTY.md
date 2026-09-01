# 第三方软件、前人工作与许可证边界

[返回文档中心](../README.md) · [贡献者与致谢](../project/CONTRIBUTORS.md) · [研究参考](../research/references.md)

本项目区分“学习设计”“依赖外部工具”和“复制代码”。除源码文件另行声明外，本仓库自写
代码按根目录 MIT License 维护；MIT 不自动覆盖翻译、游戏内容、字体、图片或发布包。

## 直接技术参考

| 项目 | 上游观察到的许可证 | 与本仓库的准确关系 |
| --- | --- | --- |
| [GARbro](https://github.com/morkt/GARbro/tree/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0) | MIT | `rUGP/tools/catalog/rio_inventory.py` 是 [`ArcFormats/rUGP/ArcRIO.cs`](https://github.com/morkt/GARbro/blob/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0/ArcFormats/rUGP/ArcRIO.cs) 的维护型 Python 移植；上游文件 SHA-256 为 `DEF71FDDD334C6DC2BD03671600A3F4C3987355CE9C2E579C32EF1F73FDB4AB5`，完整 morkt/MIT 声明保留在源码中。未附带 GARbro 二进制或游戏资源。 |
| [AFHook](https://github.com/eplightning/afhook/tree/3f613a097c07d3d9fb9969a130ea6d859b544f8a) | MIT | 提供 AGES/rUGP 制作端与游戏运行时分离的架构先例；Photon 运行时代码由本项目针对 PF/PM 独立实现并严格锁定版本。 |
| [rugptools](https://github.com/osmium76/rugptools/tree/3ff587416e41eeeee7122fb122c90f7a36c409dd) | README 对原始部分提及 GPL；未观察到清晰的全仓许可证文件 | 仅用于历史 rUGP/alterdec 行为和术语参考。因许可证边界不够明确，不复制源码。 |
| [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager/tree/080c2cac36391e2d2de473f8f8a841b08cf752dc) | MIT | AGE2 FPD v2 提取/实验性重封及 `Scrambler.cs` 密钥调度的主要参考。观察到的 `Scrambler.cs` SHA-256 为 `5AA8BCEFB9F2F1D14917FE11027B32FFFFD0A8C8C3F25C3AE8D690827EEAE33E`；本项目要求用户显式提供该上游文件，不复制第二份密钥表。 |

## 汉化思路来源

本项目最初参考了主任保护协会发布的
[Steam 版 Muv-Luv Alternative Total Eclipse 汉化补丁](https://www.moyu.moe/patch/5461/resource)
所展示的 AGES 汉化路线。根据项目发起者保存的沟通记录，对方允许发布本项目独立制作的
TDA 汉化，并要求在发布时致谢其提供汉化思路。该公开补丁页面同时禁止拆解、二次修改和
移植，因此本仓库不复制其补丁文件、译文、字体、图片或代码。

## 仓库与工作流参考

[thcrap](https://github.com/thpatch/thcrap)、
[07th-Mod python-patcher](https://github.com/07th-mod/python-patcher)、
[Committee of Zero SGHD Patch](https://github.com/CommitteeOfZero/sghd-patch)、
[Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation)、
[VNTranslationTools](https://github.com/arcusmaximus/VNTranslationTools) 和
[Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2) 被用于研究仓库边界与
维护方式，不是直接依赖。吸收的做法包括：玩家/开发者分层、语言层、输入哈希、插件与
格式边界、生成物排除，以及文本/图片/字体/构建逻辑分开。

## 构建依赖

- Python 依赖分别固定在 `AGE2/requirements.txt`、`rUGP/requirements.txt` 和
  `localization/requirements.txt`；根开发文件汇总三者。
- Photon 原生构建使用 [Zig](https://ziglang.org/) 0.16.0，不将编译器提交到仓库。
- GitHub Actions 在 `.github/workflows/quality.yml` 中锁定到不可变提交。
- 字体是带许可证的 Release 输入；当前 Git 不追踪字体二进制，详见
  [`localization/fonts/`](../../localization/fonts/README.md)。

新增依赖必须记录准确版本、上游 URL、许可证、是否复制代码/数据，以及采用它的可复现
或安全理由。

## English summary

The project distinguishes design study, external dependencies and copied code.
Direct relationships and pinned upstream revisions are documented above; no
upstream game assets or ambiguously licensed source are silently vendored.
