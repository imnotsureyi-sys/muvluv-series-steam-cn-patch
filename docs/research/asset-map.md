# 文本、术语、图片与字体资产地图

[返回研究入口](README.md) · [English](../en/asset-map.md) ·
[通用本地化工作区](../../localization/README.md) ·
[内容与发布政策](../project/asset-and-release-policy.md)

本页回答两个问题：项目真正可维护的文字、图片和字体资料在哪里，以及为什么它们没有
全部堆进 `localization/`。

## 归类规则

| 内容 | 公开位置 | 原因 |
| --- | --- | --- |
| 两轮翻译方法、审核状态、语言命名、共用术语、图片与字体通用工具 | `localization/` | 不依赖某个引擎或某个资源槽，可由其他语言和其他游戏复用 |
| 某作正文、选项、说话人、UI 译文和作内术语 | `AGE2/games/<game>/` 或 `rUGP/games/<game>/` | 稳定 ID、源哈希、场景、语言槽和写回契约都绑定具体游戏 |
| 某作图片文案、路径、尺寸、源图锁和成品身份 | 对应游戏的 `images/`；跨 PF/PM 的联合权威放 `rUGP/evidence/photon/` | 图片是否显示由游戏路径、父对象、语言端点和编码共同决定，不能脱离引擎保存 |
| FPD、EGPACK、ICI、RIO、CRsa、RUO、Cr6Ti、CRip 和 Hook | 对应的 `AGE2/` 或 `rUGP/` | 这些是完全不同的格式与运行时体系 |
| 大型、已审核且允许分发的成品图片或玩家包 | 同一 GitHub 仓库的 Releases，并在 Git 中保存 manifest、哈希和来源说明 | 避免数千个二进制膨胀 Git 历史，同时保持版本、下载和源码集中在一个仓库 |
| 完整官方原文、原始图片、游戏容器、临时候选、失败批次、模型原始响应 | 贡献者本地、受 `.gitignore` 保护的 `work/` 等目录 | 合法输入和制作中间物不是公开项目资产；可复现结论应提升为工具、清单、配方或复盘 |

因此，**原始日文文本和原始图片不应搬进 `localization/`**。公开表使用稳定 ID 和源字段
SHA-256；制作者从自己合法拥有的游戏重新提取日文/源图，在本地按哈希连接。这样既能
复现工作，也不会把公开仓库变成游戏原始资源镜像。

## 当前公开文字

| 游戏 | 可维护文字入口 | 当前规模与用途 |
| --- | --- | --- |
| TDA00 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda00/translations/ja-zh-Hans.csv) | 3,713 行，含稳定 ID、场景、说话人、源哈希、中文与审核状态 |
| TDA01 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda01/translations/ja-zh-Hans.csv) | 8,565 行 |
| TDA02 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda02/translations/ja-zh-Hans.csv) | 6,589 行 |
| TDA03 | [`translations/ja-zh-Hans.csv`](../../AGE2/games/tda03/translations/ja-zh-Hans.csv) | 6,913 行 |
| 帝都燃烧篇 | [`translations/`](../../AGE2/games/imperial-capital-burns/translations/) | 5,564 行正文，另有 21 行辅助文字、18 个选项、91 个说话人和 UI 字符串表 |
| photonflowers | [`translations/`](../../rUGP/games/photonflowers/translations/) | 12,964 行 reviewed 文本；另有 69 行精确运行时绑定表，不把二者冒充成同一写入权威 |
| photonmelodies | [`translations/`](../../rUGP/games/photonmelodies/translations/) | 44,583 行 reviewed 文本；另有 151 行精确运行时绑定表 |

这些计数描述公开表中的记录，不自动等于“独立台词数”“全部已实机通过”或“可直接
写回”。每个游戏 README 会说明其表是审校来源、精确 writer 输入还是历史快照。

共用系列术语放在
[`localization/glossaries/muv-luv.ja-zh-Hans.csv`](../../localization/glossaries/muv-luv.ja-zh-Hans.csv)；
只在单作成立的术语跟随游戏，例如
[帝都燃烧篇术语](../../AGE2/games/imperial-capital-burns/terminology/ja-zh-Hans.csv)。

## 当前公开图片资料

| 游戏/集合 | 公开身份 | 二进制位置 | 说明 |
| --- | ---: | --- | --- |
| TDA00 | 70 个 WebP 路径、59 份唯一内容 | 历史玩家 Release | [逐项清单](../../AGE2/games/tda00/images/) |
| TDA01 | 93 个路径、71 份唯一内容 | 历史玩家 Release | [逐项清单](../../AGE2/games/tda01/images/) |
| TDA02 | 100 个路径、80 份唯一内容 | 历史玩家 Release | [逐项清单](../../AGE2/games/tda02/images/) |
| TDA03 | 152 个路径、90 份唯一内容 | 历史玩家 Release | [逐项清单](../../AGE2/games/tda03/images/) |
| 帝都燃烧篇 | 315 个路径、232 份唯一内容 | 历史玩家 Release | [逐项清单与可维护文案](../../AGE2/games/imperial-capital-burns/images/) |
| photonflowers | 636 项权威 | Photon V6 研究 Release | [图片权威](../../rUGP/evidence/photon/images/)与[游戏入口](../../rUGP/games/photonflowers/images/) |
| photonmelodies | 854 项权威 | Photon V6 研究 Release | [图片权威](../../rUGP/evidence/photon/images/)与[游戏入口](../../rUGP/games/photonmelodies/images/) |

五个 AGE2 历史包合计 **730 个 WebP 路径**；PF/PM 合计 **1,490 项**。路径数不等于
独立绘制数：同一内容可能服务多个语言后缀或状态，也可能是官方 fallback。Photon V6
目前还包含 19 张与官方源文件字节完全相同的 PNG，因此保持“研究资产、整改中”，不能
当成可自由镜像的玩家补丁。

图片制作的长期可维护内容不是某次批次目录，而是：资源身份、源哈希、中文文案、无字底
权威、字体和排版参数、允许变化区域、输出哈希与审核结论。完整方法见
[图片本地化工作流](../../localization/image-workflow.md)。

## 字体

字体的共用选择、许可证、来源和字形覆盖规则放在
[`localization/fonts/`](../../localization/fonts/README.md)。具体游戏如何选中字体仍属于
引擎层：AGE2 要验证松散路径和配置，rUGP 要验证注册、家族替换、GDI 请求和版本门。

仓库不收来源不明的字体二进制。允许再分发的字体应连同完整许可证、上游版本、SHA-256、
修改/子集化命令和覆盖报告一起进入 Release。

## 新语言从哪里开始

1. 阅读[完整工作流](../../localization/workflow.md)或
   [English workflow](../../localization/workflow.en.md)。
2. 按[新语言指南](../../localization/new-locale.md)建立 `ko`、`ru` 等独立目标。
3. 从合法游戏本地提取源文字/源图并按公开哈希连接，不把中文改名成新语言源表。
4. 把目标语言译文和作内图片文案放回对应游戏目录；把可跨游戏复用的新规则或工具贡献到
   `localization/`。
