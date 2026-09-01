# 参考项目：采用的优点与主动改进的缺点

[返回研究索引](README.md) · [资产地图](asset-map.md) ·
[贡献者与致谢](../project/CONTRIBUTORS.md) ·
[第三方许可证](../legal/THIRD_PARTY.md)

参考对象按它解决的问题选择，而不是只看会变化的 star 数。这里记录“学到了什么”以及
“为什么没有照搬”，具体代码复用则在第三方说明中固定提交、许可证与哈希。

## rUGP／AGES 与 AGE2 工具

| 项目 | 值得采用 | 本项目主动补足 |
| --- | --- | --- |
| [GARbro](https://github.com/morkt/GARbro) | 首页先给下载和 GUI 操作；`ArcFormats/` 与界面分层；RIO/ICI 目录读取和具体资源解码分开 | GARbro 不是 Photon 万能重封器。本项目把 PF/PM 目录读取移植来源隔离并保留 MIT 声明，再增加严格 extent、卷、父引用、稳定身份、清单和合成测试 |
| [AFHook](https://github.com/eplightning/afhook) | `editor/` 与 `plugin/` 直接体现“制作端”和“游戏运行端”是两件事 | 上游文档很少且不覆盖当前 PF/PM 版本。本项目补上准确构建哈希、失败关闭、字体/图片路由、可复现构建、遥测和逐问题复盘 |
| [rugptools](https://github.com/osmium76/rugptools) | GUI 与 `.rio` 访问库分层，并诚实声明只支持特定 MLA DVD 版本、对象反序列化仍不完整 | 历史 alterdec 转录部分的许可证边界需谨慎，因此只研究行为，不复制不清楚的源码；当前实现以独立样本、测试和来源说明重新建立 |
| alterdec／RioX 历史资料 | 保存了早期 rUGP 对象和图片行为的关键术语与先例 | 它们不是现代 PF/PM 的完整制作、测试和发布链；本项目明确区分历史线索、独立验证和当前可发布能力 |
| [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager) | 小而聚焦的 FPD v2 `pack.bin` 提取/实验性重封实现，格式字段和 `Scrambler.cs` 易于追踪 | 上游几乎没有玩家/研究文档，源码全铺在根目录。本项目把严格读取、筛选提取和测试放入 `AGE2/tools/fpd/`，并诚实声明当前发布路线是 LocalAppData 松散覆盖，不冒充通用 `pack.bin` 重封 |

## 成熟补丁与翻译仓库

| 项目 | 值得采用 | 本项目主动补足或避免 |
| --- | --- | --- |
| [thcrap](https://github.com/thpatch/thcrap) | 多语言补丁数据与运行时分层、模块化、更新与文档体系 | 大型运行时仓库对普通玩家入口较重；本项目首页只分流，AGE2 不因为 rUGP 需要 Hook 就继承 Hook |
| [07th-Mod python-patcher](https://github.com/07th-mod/python-patcher) | 玩家安装体验、游戏扫描、配置数据、校验与安装器测试优先 | 安装器源码不能代替翻译/图片权威；本项目在同一仓库继续保存游戏专属可维护表、资产身份和发布门 |
| [Committee of Zero SGHD Patch](https://github.com/CommitteeOfZero/sghd-patch) | `content/`、installer、launcher、字体工具和 edited-images 边界可见 | 其 README 明确是开发者构建页且有资产被移除；本项目额外维护独立玩家页、公开/本地/Release 三层资产政策和缺失复现步骤 |
| [Tsukihimates Tsukihime Translation](https://github.com/Tsukihimates/Tsukihime-Translation) | `script/`、`images/`、`system_strings/`、工具和最终补丁入口简单直观，完整翻译活动可持续维护 | 单作仓库可以平铺，七作双引擎仓库不能。本项目把游戏资产放进各自引擎/游戏目录，并用 manifest/Release 管理大型二进制；“公开可见”不自动等于权利已解决 |
| [VNTranslationTools](https://github.com/arcusmaximus/VNTranslationTools) | 提取、可编辑中间表与写回是独立阶段，格式工具可跨项目复用 | 本项目再增加源哈希、语言身份、游戏版本和发布状态，避免把任意表当作授权 writer 输入 |
| [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2) | archive、image、text、font 插件边界清楚 | 本项目不会为了统一界面把 AGE2/rUGP 强塞进一个抽象；跨引擎只共享真正中立的翻译、图片和字体方法 |

## 最终形成的仓库原则

1. **首页只分流：**玩家与研究/制作是两个独立 README，不在同一页混合安装细节和格式
   论文；中文与英文用可见按钮切换。
2. **引擎彻底分开：**AGE2 与 rUGP 各自拥有游戏、工具、测试和复盘，互不 import。
3. **方法与游戏资产分开：**`localization/` 保存可跨引擎复用的方法；具体文本、图片身份
   和写回契约跟随游戏。
4. **制作资产与运行载荷分开：**可维护表、文案、manifest 和源码进入 Git；大型审核二进制
   和玩家包进入同一仓库的 Releases；官方源和临时批次留在本地。
5. **结论与证据一起公开：**成功代码之外还保存 8311、字体、CRip008、shared/common、
   图片传输等失败假设、决定性实验、适用边界和回归测试。
6. **不夸大复现程度：**组件测试、独立回读、实机成功和可发布是四种不同结论。

## 来源与致谢边界

没有导入其他项目的游戏译文或图片。GARbro 的直接移植被隔离、注明并保留 MIT 声明；
许可证不清楚的仓库不复制源码。哈希门、manifest、语言层、玩家/开发者分离等通用做法
仍由本项目针对目标游戏重新实现和测试，不能用“别人也这样做”代替证据。

## English summary

The project adopts focused user entry points, editor/runtime separation,
game-bound asset ownership, reusable format-tool boundaries, manifests, tests,
and reproducible releases from the projects above. It deliberately improves on
sparse documentation, unclear provenance, developer-only home pages, mixed
engine trees, and claims that blur component success with end-to-end release
readiness. No other project's game translation or image assets were imported.
