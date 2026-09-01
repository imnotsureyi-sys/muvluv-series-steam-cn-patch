# Muv-Luv 系列社区本地化补丁与工具

[English](README.md) · [玩家下载](#玩家下载) · [文档导航](docs/README.md) · [安装与还原](docs/player-guide.zh-CN.md) · [制作其他语言补丁](localization/new-locale.md) · [逆向研究索引](docs/research-index.md) · [参与贡献](CONTRIBUTING.md)

这是一个面向部分 Steam 版 Muv-Luv 作品的非官方、非商业本地化项目。目前发布简体中文**测试补丁**，同时保存可供其他语言团队复用的 AGE2 与旧 rUGP 研究成果。

使用补丁必须拥有对应游戏正版。本仓库不包含游戏本体、破解、完整原始资源或 Steam 原始 `pack.bin`。

## 先选择你的入口

| 我想…… | 从这里开始 | 目前实际可用的内容 |
| --- | --- | --- |
| 下载并游玩中文补丁 | [玩家下载](#玩家下载)，然后阅读[玩家指南](docs/player-guide.zh-CN.md) | 五个历史 AGE2 beta 包；Photon 暂无玩家安装包 |
| 制作韩语、俄语或其他语言补丁 | [新语言指南](localization/new-locale.md)，再选择 [AGE2](age2/README.md) 或[旧 rUGP](rugp/README.md) | 格式与工作流可复用，但端到端缺口已明确列出 |
| 研究 rUGP/AGES 或 AGE2 逆向 | [研究索引](docs/research-index.md)和 [rUGP 事故/逆向记录](rugp/docs/postmortems/README.md) | 有代码、测试、证据和失败假设；不是万能一键解包/封包器 |

## 玩家下载

以下均为 prerelease/测试包。请下载与你的游戏完全对应的 ZIP；**不要**把 GitHub 的仓库源码 ZIP 当成补丁。

**当前分发状态：**这些历史包技术上可安装，但因字体许可随包文件和部分官方 UI 兜底副本仍在整改，当前索引标记为“不推荐下载 / 未批准重新分发”。下方直链用于准确识别现存历史 Release；希望采用现行发布门槛的玩家应等待重建包。若仍自行测试，请先读完限制并备份。

**兼容性先决条件：**这五个历史包没有保存准确 Steam build/depot 或原始 `pack.bin` 哈希，所以当前 Steam 构建均属“未预验证”，不是已确认兼容。安装前必须备份该作自己的 LocalAppData 覆盖目录；复制成功也不等于版本验证通过。

| 游戏 | Windows 直接下载 | 版本说明与校验 |
| --- | --- | --- |
| THE DAY AFTER episode:00 | [TDA00 beta0.1 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1.zip) | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1_SHA256SUMS.txt) |
| THE DAY AFTER episode:01 | [TDA01 beta0.2.2 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2.zip) | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2_SHA256SUMS.txt) |
| THE DAY AFTER episode:02 | [TDA02 beta0.1 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1.zip) | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1_SHA256SUMS.txt) |
| THE DAY AFTER episode:03 | [TDA03 beta0.1.6 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda03-beta0.1.6/MuvLuv_TDA03_CN_Patch_beta0.1.6_full_achievement_fix.zip) | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1.6) · SHA-256 `4B6CA4A531E9D07315E84DC2E02D7D8008C9B78EA4466172B45CAD1CEBA5C67D` |
| The Imperial Capital Burns / 帝都燃烧篇 | [beta0.1 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/imperial-capital-burns-beta0.1/MuvLuv_Imperial_Capital_Burns_CN_Patch_beta0.1.zip) | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/imperial-capital-burns-beta0.1) · [SHA-256](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/imperial-capital-burns-beta0.1/MuvLuv_Imperial_Capital_Burns_CN_Patch_beta0.1_SHA256SUMS.txt) |

只使用表中的版本。`tda01-beta0.1`、`tda01-beta0.2`、`tda01-beta0.2.1` 与 `tda03-beta0.1` 已被后续版本取代，不再推荐；其中 TDA01 beta0.2 有 603 个不可见正文槽，TDA03 beta0.1 后续确认误用了 TDA02 的 UI/成就映射。

完全退出游戏，解压整个 ZIP，阅读包内 `README.txt`，再运行 `install.bat`。五个游戏的准确 LocalAppData 路径、校验命令、回滚边界和反馈方式见[玩家指南](docs/player-guide.zh-CN.md)；每个发布资产的准确哈希和历史包事实另见[机器可读发布索引](docs/release-index.json)。

Photon Flowers 与 Photon Melodies 目前只有源表、格式代码、运行时源码和图片证据，**没有可供玩家安装的完整补丁**。[1,490 张 Photon 图片 Release](rugp/evidence/photon-images-v6/README.md) 完成的是技术/本地化身份审核，不是安装包；其中 19 张与官方来源字节相同，公开分发整改尚未完成。

### 历史 beta 的限制

上述五个包早于本仓库现在的发布门槛，尚未统一包含安装清单、输入版本哈希门、回滚工具和随字体附带的许可证说明；其中还在重新审计字体许可证随包义务与官方 UI 兜底资源的再分发边界，因此不能视为符合当前发布政策的新包。机器可读索引把这项状态明确标为 `pending-remediation`；在生成去除受限原件并补齐字体许可的新包前，直接下载入口只是对现存历史 Release 的准确指向，不是合规背书。TDA03 beta0.1.6 没有单独的校验附件，所以上表直接列出 GitHub 记录的资产摘要。包内 README 可用于确认当时的安装结构，但当前中央玩家指南优先于不安全的旧回滚文字：尤其**不要**照 TDA01 beta0.2.2 的说明删除整个 `...\tda01\data`，也绝不能删除 `data\user` 或存档/进度数据。

## 现在究竟能复现到哪一步

| 范围 | 玩家结果 | 已公开的维护输入 | 从合法干净游戏重建的现状 |
| --- | --- | --- | --- |
| TDA00–03（AGE2） | 已发布中文 beta | 正文表、严格连接本机原文与 EGPACK 的工具，以及共用 FPD/EGPACK/UI 工具 | **部分可复现：**历史 Release 对齐仍在审计，且缺少完整的逐作图片/字体/build manifest 和最终打包命令 |
| 帝都燃烧篇（AGE2） | 已发布中文 beta | 文本表、图片文字/布局表、初始盘点和第一阶段 builder | **部分可复现：**历史 Release 对齐仍在审计；`build_phase1.py` 本身不能重建后来加入完整正文的发布包，并仍需外部 FSNr/字体输入 |
| Photon Flowers / Photon Melodies（旧 rUGP） | 尚无玩家包 | [57,547 条审校台词记录](rugp/evidence/photon-reviewed-text-v1/README.md)、独立的 69/151 条精确运行时合约、只读 ICI/RIO 目录与 CRsa 提取器、1,490 图 V6 权威与路由闭环、编解码器、运行时和打包器 | **部分可复现：**尚缺“干净安装 → 全部 payload 绑定 → 最终批准 builder root”完整链路 |

安装锁定依赖后，无版权 Python 合成测试可在干净源码克隆中完成；原生 Photon 运行时编译还需要 Zig 0.16.0。真正生产补丁仍需要正版游戏输入、准确哈希、允许再分发的字体/资源和人工实机 QA。每项结论的证据边界见[研究索引](docs/research-index.md)。

## 两套完全独立的引擎体系

| 体系 | 本仓库对应游戏 | 补丁方式 | 入口 |
| --- | --- | --- | --- |
| AGE2 | TDA00–03、帝都燃烧篇 | 检查 FPD，处理 EGPACK/WebP，以松散文件后置覆盖 | [`age2/`](age2/README.md) |
| 旧 rUGP/AGES | Photon Flowers、Photon Melodies | 处理 ICI/RIO/RUO；静态替换不足时使用严格锁定版本的运行时 | [`rugp/`](rugp/README.md) |

本仓库用 **AGE2** 指代较新的 FPD/EGPACK 移植体系，用**旧 rUGP**指代 RIO 体系。二者不互相导入引擎工具；只有翻译、术语、审核和图片制作等引擎无关工作放在 [`localization/`](localization/README.md)。

## 项目结构

```text
localization/  翻译/审核规范、术语表、图片流程和新语言指南
age2/          AGE2 游戏源表、FPD/EGPACK 工具与合成测试
rugp/          rUGP 编解码、运行时、打包、证据、测试与事故记录
docs/          玩家、研究、架构、权利和发布文档
.github/       自动测试与贡献模板
```

各目录的职责边界、当前优先事项和重要仓库变更分别见[仓库架构](docs/repository-architecture.md)、
[路线图](ROADMAP.md)和[变更记录](CHANGELOG.md)。

游戏解包目录、私有审计根目录、模型临时输出、缓存、编译 DLL、发布 ZIP 和失败候选图不会进入 Git 历史。

## 测试、反馈与安全

开发检查见 [CONTRIBUTING.md](CONTRIBUTING.md)。合成测试通过只证明被覆盖的解析/写入分支，不代替干净安装、回滚测试和完整路线实机测试。

补丁或运行时问题请[提交 Bug](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)；译文修正请[提交带日文依据的翻译反馈](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml)。

AGE2 补丁是用户 LocalAppData 下的松散文件。Steam“验证游戏文件完整性”**不会**删除它们；必须先按[回滚说明](docs/player-guide.zh-CN.md#卸载与回滚)处理松散覆盖，再用 Steam 验证修复 Steam 管理的原始文件。

## 致谢、许可证与内容权利

本项目参考了视觉小说工具社区的公开思路，并针对 PF/PM 独立验证了具体行为。前人工作与本项目新增内容的边界见 [`THIRD_PARTY.md`](THIRD_PARTY.md)、[参考项目](docs/references.md)和[研究索引](docs/research-index.md)。

感谢主任保护协会分享 AGES 本地化经验，感谢子冰提供 TDA01 实机反馈，也感谢所有参与截图反馈、术语讨论和完整路线测试的玩家。

本项目自写代码使用 [MIT License](LICENSE)。该许可证不自动覆盖 Muv-Luv 原始内容、翻译文本、字体、衍生图片、发布包或第三方组件；详情见 [`NOTICE.md`](NOTICE.md)与[资产和发布政策](docs/asset-and-release-policy.md)。
