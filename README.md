<p align="right">
  <a href="README.md"><img alt="简体中文" src="https://img.shields.io/badge/%E7%AE%80%E4%BD%93%E4%B8%AD%E6%96%87-%E5%BD%93%E5%89%8D-C62828?style=for-the-badge"></a>
  <a href="docs/en/README.md"><img alt="English" src="https://img.shields.io/badge/English-Read-2F81F7?style=for-the-badge"></a>
</p>

# Muv-Luv 系列 Steam 中文补丁

这是一个非官方、非商业的 Muv-Luv 系列本地化项目。仓库既保存面向玩家的简体中文
测试补丁，也公开让其他语言团队能够复用的翻译、术语、图片、字体、格式工具和逆向
经验。

使用补丁必须拥有对应游戏正版。本仓库不提供游戏本体、破解、完整原始资源或 Steam
原始 `pack.bin`。

## 请选择入口

| **普通玩家** | **本地化制作者与技术研究者** |
| --- | --- |
| **[下载、安装、卸载与排错](docs/player/README.md)** | **[文本、图片、字体、工具与逆向研究](docs/research/README.md)** |
| 只保留玩家真正需要的版本状态、下载地址和安全操作。 | 从资产地图进入多语言工作流、AGE2、rUGP 和故障复盘。 |

英文读者可直接进入 [English overview](docs/en/README.md)、
[Player guide](docs/en/player-guide.md) 或
[Research and localization index](docs/en/research-index.md)。

## 当前状态

| 范围 | 玩家状态 | 公开的制作与研究成果 |
| --- | --- | --- |
| TDA00–03、帝都燃烧篇 | 保留历史 AGE2 测试包；仍在补做版本、字体许可、官方 UI 兜底资源和安全回滚审计 | 五作可维护文本、730 个历史 WebP 路径清单、帝都图片文案、FPD/EGPACK 工具与松散覆盖经验 |
| photonflowers、photonmelodies | 暂无玩家安装包 | 可维护文本、PF/PM 1,490 图权威与路由、ICI/RIO/CRsa/RUO/Cr6Ti/CRip 工具、受保护运行时与故障复盘 |

历史包可以识别和安装，但在现行发布门完成前不标记为推荐版本；以
[玩家指南](docs/player/README.md)中的状态和警告为准。Photon 的 1,490 图 Release 是
研究/制作资产，不是补丁安装器。

## 内容放在哪里

| 目录 | 职责 |
| --- | --- |
| [`localization/`](localization/README.md) | 跨引擎的两轮翻译、术语、图片制作、字体检查与新语言工作流 |
| [`AGE2/`](AGE2/README.md) | TDA／帝都的游戏专属文本和图片身份、FPD、EGPACK、WebP、松散覆盖、测试与复盘 |
| [`rUGP/`](rUGP/README.md) | Photon 的游戏专属文本和图片身份、ICI、RIO、CRsa、RUO、Cr6Ti、CRip、运行时与复盘 |
| [`docs/`](docs/README.md) | 玩家说明、研究索引、项目维护、法律与英文文档 |

完整的归类规则与实际数量见
**[文本、术语、图片与字体资产地图](docs/research/asset-map.md)**。原则很简单：
跨游戏、跨引擎的方法放 `localization/`；绑定具体游戏资源 ID、语言槽、路径或编码的内容
放对应的 `AGE2/games/` 或 `rUGP/games/`；完整官方原始资源只从贡献者自己的合法安装
提取，不进入公开仓库。

## 本地化工作流

本项目采用“剧情与术语基线 → 第一次翻译 → 第二次独立
`keep/revise/question` 审核 → 技术写回 → 实机 QA → 玩家反馈回流”的完整流程。

- [中文完整工作流](localization/workflow.md)
- [English workflow](localization/workflow.en.md)
- [制作韩语、俄语等新语言](localization/new-locale.md)
- [图片本地化与 Image 2 经验](localization/image-workflow.md)

## 致谢与参与

致谢“主任保护协会”提供了 AGES 引擎的汉化思路，并感谢他让我们开始了汉化补丁制作
之路。GARbro、AFHook、rugptools、FatePackageManager 以及其他成熟补丁项目为本项目
提供了明确标注的技术先例；详见[贡献者与致谢](docs/project/CONTRIBUTORS.md)和
[参考项目比较](docs/research/references.md)。

[提交程序或安装问题](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)
· [提交译文修正](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml)
· [参与贡献](docs/project/CONTRIBUTING.md)

自写代码采用 [MIT License](LICENSE)。MIT 不自动覆盖游戏内容、翻译文本、字体、衍生
图片、发布包或第三方组件；详见[内容与发布政策](docs/project/asset-and-release-policy.md)、
[第三方来源](docs/legal/THIRD_PARTY.md)与[法律说明](docs/legal/NOTICE.md)。
