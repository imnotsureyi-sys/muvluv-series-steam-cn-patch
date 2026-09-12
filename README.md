# Muv-Luv 系列 Steam 中文补丁

<p align="center">
  <strong><a href="#游戏下载">游戏下载</a></strong> ·
  <a href="docs/player/README.md">安装、卸载与排错</a> ·
  <a href="#research">制作与研究 / Research · English</a> ·
  <a href="#问题反馈">问题反馈</a>
</p>

这是一个非官方、非商业的 Muv-Luv 系列 Steam 简体中文补丁项目。

> [!IMPORTANT]
> 使用补丁必须拥有对应游戏正版。本仓库不提供游戏本体、破解或完整原始资源。
> 下列 AGE2 补丁是保留的历史测试版，尚未达到现行发布标准；安装前请阅读
> [完整玩家指南](docs/player/README.md)，并备份对应游戏的 LocalAppData 覆盖目录。

## 第一部分 · 玩家下载与反馈

### 游戏下载

请选择与你拥有的游戏完全对应的补丁。**下载名为“补丁 ZIP”的文件，不要下载 GitHub
自动生成的 Source code ZIP。**

| 游戏 | 当前公开版本 | 下载与说明 |
| --- | --- | --- |
| TDA00 | 历史测试版 beta0.1 | **[下载补丁 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1.zip)** · [发布说明](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1) |
| TDA01 | 历史测试版 beta0.2.2 | **[下载补丁 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2.zip)** · [发布说明](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2) |
| TDA02 | 历史测试版 beta0.1 | **[下载补丁 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1.zip)** · [发布说明](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1) |
| TDA03 | 历史测试版 beta0.1.6 | **[下载补丁 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda03-beta0.1.6/MuvLuv_TDA03_CN_Patch_beta0.1.6_full_achievement_fix.zip)** · [发布说明](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1.6) |
| 帝都燃烧篇 | 历史测试版 beta0.1 | **[下载补丁 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/imperial-capital-burns-beta0.1/MuvLuv_Imperial_Capital_Burns_CN_Patch_beta0.1.zip)** · [发布说明](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/imperial-capital-burns-beta0.1) |
| photonflowers（PF） | **BETA 0.1** | **[下载补丁 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/pf-BETA-0.1/MuvLuv_PF_CN_Patch_BETA_0.1.zip)** · [发布说明](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/pf-BETA-0.1) |
| photonmelodies（PM） | **BETA 0.1.1** | **[下载补丁 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/pm-BETA-0.1.1/MuvLuv_PM_CN_Patch_BETA_0.1.1.zip)** · [发布说明](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/pm-BETA-0.1.1) |

### PF / PM 安装

Steam 语言设为 **English（英语）**，等待下载完成并退出游戏。解压对应 ZIP，双击 EXE，点击“安装汉化”。无需先安装旧补丁。

PF、PM 均不创建备份、不附卸载器。恢复原版时保留存档，通过 Steam 卸载、清除对应游戏目录的汉化残留，再重新下载；不要清空整个 Steam 目录。详见[玩家指南](docs/player/README.md)。

### AGE2 历史包安装、卸载和注意事项

1. 确认 Steam 已安装对应游戏，至少启动过一次，然后完全退出游戏。
2. 下载上表中对应游戏的补丁 ZIP，完整解压，阅读包内说明和玩家指南。
3. 先备份该游戏准确的 LocalAppData 覆盖目录，再运行安装脚本。不同作品的文件不能混用。
4. Steam 的“验证游戏文件完整性”不会删除 LocalAppData 中的补丁文件，不能当作卸载方法。

历史包在安装清单、版本哈希、字体许可和安全回滚方面仍有待补审。准确目标路径、校验方法、
旧版本风险及恢复步骤都集中在 **[玩家下载、安装、卸载与排错指南](docs/player/README.md)**。

### 项目状态

PF／PM 的技术来源分类、上游版本、82 项技术职责与完整路线演变，详细请见 **[技术来源分类与完整蓝图](docs/research/photon/README.md)**。

- **TDA00—03、帝都燃烧篇：**已有上述历史测试包，正在整理可维护文本、版本校验、字体和
  安全回滚，为后续更新做准备。
- **photonflowers、photonmelodies：**已正式公开发布 **BETA 0.1**，PF、PM 各有独立安装包。旧 Photon 图片研究资产仍不是游戏安装包。

### 问题反馈

安装遇到问题、发现错字或想交流，欢迎加入 **QQ 交流群：273626767**。
不熟悉 GitHub 也可以直接进群反馈，尽量附上游戏名、补丁版本、截图和前后台词。

- [报告安装、启动、文本、图片或字体问题](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)
- [提交有日文原文依据的翻译修正](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml)
- [查看参与方式、贡献者与致谢](.github/CONTRIBUTING.md)

### 关于 AI 翻译与人工校对

**本项目各作的汉化文本均有 AI 参与翻译，但不是 AI 直出。**
我们先以日文原文为依据，通读剧情、梳理人物关系并建立术语基线，再按场景初译；
随后独立进行第二轮日文对照复核，记录保留、修改和待确认项，解决疑点、统一术语，
随后进行资源写回、技术检查和实机验证；**制作流程的最后一步是由我人工检查、修改发现的
错误，确认修改结果后再发布对应版本。** AI 复核与人工审核分别记录，不能互相替代。

**玩家目前下载到的补丁，已经包含我在相应版本发布前参与审核、确认并落实的修改。**
从译文措辞、人物称谓和术语取舍，到文本缺漏、换行排版、图片文字和游戏内显示问题，
我在制作和测试过程中结合原文依据、校对意见与实际反馈检查问题，提出修改要求、确认
采用方案，并跟进修正结果，再将修改纳入对应发布包。AI 协助分析与执行，具体取舍和
最终发布由我负责；发布后也会继续收集反馈、修正问题。

这些修改已有发布记录：
[TDA01 beta0.2.2](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2)
已收录实机游玩反馈修复；
[TDA02 beta0.1](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1)
已包含说话人军衔、台词错位、术语及部分语序修正；
[TDA00 beta0.1](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1)
的下载包已更新说话人中文名称。

详细步骤见 **[按顺序阅读的翻译规范](localization/standards/README.md)** 和
[完整工作流](localization/workflow.md)。这些是制作流程，不代表每个历史测试包都已完成
全文人工校对或全路线验证，译文仍可能存在错误。

TDA 的部分文本已经过人工校对。已发布版本包含上述审核与修正；此后新增的校对和修改
会继续同步到可维护文本中，是否进入某个下载包以对应发布说明为准。
感谢 ScRemilia、Tsubaki-G、X1AOFEI 及其他参与校对的朋友。
**《樱花盛开之前》的部分文本由“红桃皇后假说”提供，在此诚挚致谢。**

### 欢迎加入 ParaTranz 校对

**ParaTranz 主要用于发布后的协作校对与持续修订。** 通常先完成上述制作流程并发布补丁，
再由愿意参与的朋友加入项目、对照日文提出校对和修改；经维护者确认、检查后纳入后续版本。
这与发布前由我完成的人工检查和修正是两个阶段。ParaTranz 上的改文或同步到仓库的改文，
不会自动更新玩家已经下载的补丁。在制作品也可提前开放协作，开放项目不代表已有安装包。

如果你看得懂日语，愿意对照原文校对、修改译文或讨论术语，诚挚欢迎加入以下项目。
可以从熟悉的一句台词或一个场景开始，不必一次承担整章。
即使不懂日语，也欢迎反馈错字、语句不通顺、显示异常或游玩中遇到的问题；
可以加入 **QQ 群：273626767**，和我们交流、帮助补丁逐步完善。

| 校对范围 | 在线项目 |
| --- | --- |
| TDA00—03 | [加入 TDA 校对](https://paratranz.cn/projects/19505) |
| 帝都燃烧篇 | [加入帝都燃烧篇校对](https://paratranz.cn/projects/20659) |
| photonflowers | [加入 photonflowers 校对](https://paratranz.cn/projects/20660) |
| photonmelodies | [加入 photonmelodies 校对](https://paratranz.cn/projects/20661) |

---

<a name="research"></a>

## 第二部分 · 制作与研究 / Localization & Research

本仓库同时公开可复用的翻译、术语、图片、字体、工具和逆向研究，方便其他汉化者、
开发者和其他语言团队继续维护：

| 内容 | 入口 |
| --- | --- |
| 全部公开成果与研究索引 | **[制作与研究入口](docs/research/README.md)** |
| 翻译规则、术语、图片和字体流程 | [通用本地化工作区](localization/README.md) |
| TDA／帝都的 AGE2、FPD、EGPACK 与松散覆盖 | [AGE2 工作区](AGE2/README.md) |
| Photon 的 RIO、RUO、CRsa、图片和运行时 | [rUGP 工作区](rUGP/README.md) |
| 文本、图片、字体和工具的具体位置 | [资产地图](docs/research/asset-map.md) |

<details>
<summary><strong>English · Tools, localization workflow and research — expand here</strong></summary>

### What you can reuse

This repository publishes localization tools, maintained translation tables, terminology,
image and font workflows, and reverse-engineering findings for the Muv-Luv series.
The Chinese player downloads are listed in the first part of this README.

| Topic | English-friendly starting point |
| --- | --- |
| Public results and current limitations | [Research index](docs/en/research-index.md) |
| Text, image, font and tool locations | [Asset map](docs/en/asset-map.md) |
| Translation and independent review | [Complete English workflow](localization/workflow.en.md) |
| Korean, Russian or another target language | [Starting a new language](localization/new-locale.md) |
| Ordered standards | [Standards and reading order](localization/standards/README.md) |
| TDA / Imperial: FPD, EGPACK and loose overlays | [AGE2 workspace](AGE2/README.md) |
| Photon: ICI, RIO, RUO and runtime tooling | [rUGP workspace](rUGP/README.md) |
| Proofreading synchronization | [ParaTranz workflow](localization/paratranz/README.md) |

AI participates in translation across the project. The workflow establishes Japanese story context
and terminology before a first translation, then independently reviews each candidate, resolves
questions, and performs engine-specific checks. AI review is not human proofreading or proof of
full-route in-game validation. Some TDA passages have been human-proofread; some text in
*Before the Cherry Blossoms Bloom* was provided by 红桃皇后假说.

To work on another language, reconstruct Japanese source from your own lawful game copy, preserve
stable identities and source hashes, and create separate target-language files. The current tools
are reusable components; they do not yet provide a universal one-command finished patch pipeline.

</details>

## 贡献者与致谢

项目由 [imnotsureyi-sys](https://github.com/imnotsureyi-sys)／Yi Shen 发起和维护。
我们从“主任保护协会”那里学到了 **通过松散文件结构覆盖游戏资源的方法**。
正是这份启发，让我们迈出了汉化的第一步，对此我们由衷感谢。
后续资源提取、翻译、工具开发与补丁制作由本项目自行完成；具体技术参考与历史对照记录另行列明。
感谢 GARbro、AFHook／AFEditor、rugptools、alterdec、RioX、FatePackageManager
及其他成熟补丁项目提供公开技术先例。OpenAI Codex 和图像模型
在维护者指挥与审核下参与了部分代码、文档、分析、检查和图片工作。

完整贡献范围、责任边界与参考项目见 **[贡献者与致谢](docs/project/CONTRIBUTORS.md)** 和
[研究参考](docs/research/references.md)。

## 许可与内容边界

自写代码采用 [MIT License](LICENSE)。MIT 不自动覆盖游戏内容、翻译文本、字体、衍生图片、
发布包或第三方组件；详见[内容与发布政策](docs/project/asset-and-release-policy.md)、
[第三方来源](docs/legal/THIRD_PARTY.md)与[法律说明](docs/legal/NOTICE.md)。
