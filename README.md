# Muv-Luv 系列 Steam 中文补丁

[English](docs/en/README.md) · [玩家指南](docs/player/README.md) · [本地化制作](localization/README.md) · [逆向研究](docs/research/README.md)

这是一个非官方、非商业的 Muv-Luv 系列本地化项目。仓库同时保存两类成果：给玩家使用的简体中文测试补丁，以及让其他语言团队能够复用的文本、术语、图片流程、字体检查、格式工具和逆向记录。

使用补丁必须拥有对应游戏正版。本仓库不提供游戏本体、破解、完整原始资源或 Steam 原始 `pack.bin`。

## 从这里开始

| 你的目的 | 入口 |
| --- | --- |
| 下载、安装或卸载中文补丁 | [玩家指南](docs/player/README.md) |
| 制作韩语、俄语等其他语言版本 | [本地化工作区](localization/README.md)与[新语言指南](localization/new-locale.md) |
| 查看 AGE2 的 FPD、EGPACK、WebP 与松散覆盖 | [AGE2](AGE2/README.md) |
| 查看 rUGP 的 ICI、RIO、RUO、CRsa、图片与运行时 | [rUGP](rUGP/README.md) |
| 了解 8311、CRip008、字体、shared/common 图片等问题怎样解决 | [逆向研究索引](docs/research/README.md) |

## 玩家下载

以下是迁移时保留的历史测试包。它们可以识别和安装，但早于现行发布标准，目前仍在补做字体许可、官方 UI 兜底资源、版本哈希与安全回滚审计，因此暂不标记为“推荐下载”。安装前务必阅读[玩家指南](docs/player/README.md)并备份对应游戏的 LocalAppData 覆盖目录；不要把 GitHub 的源码 ZIP 当作补丁。

| 游戏 | 当前保留版本 | 下载 |
| --- | --- | --- |
| THE DAY AFTER episode:00 | beta0.1 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1.zip) · [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1) |
| THE DAY AFTER episode:01 | beta0.2.2 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2.zip) · [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2) |
| THE DAY AFTER episode:02 | beta0.1 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1.zip) · [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1) |
| THE DAY AFTER episode:03 | beta0.1.6 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda03-beta0.1.6/MuvLuv_TDA03_CN_Patch_beta0.1.6_full_achievement_fix.zip) · [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1.6) |
| 帝都燃烧篇 | beta0.1 | [ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/imperial-capital-burns-beta0.1/MuvLuv_Imperial_Capital_Burns_CN_Patch_beta0.1.zip) · [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/imperial-capital-burns-beta0.1) |

Photon Flowers 与 Photon Melodies 目前只有制作资产、格式代码和候选运行时，**还没有玩家安装包**。

## 汉化内容放在哪里

| 内容 | 位置 | 当前公开状态 |
| --- | --- | --- |
| 正文、选项、说话人、UI 文本 | 各游戏的 `translations/`：[AGE2 游戏](AGE2/games/) · [Photon Flowers](rUGP/games/photonflowers/) · [Photon Melodies](rUGP/games/photonmelodies/) | 已公开可维护表；按游戏和语言分开保存 |
| 共用术语 | [Muv-Luv 总术语表](localization/glossaries/muv-luv.ja-zh-Hans.csv)与[术语维护规则](localization/standards/terminology.md) | 已公开；帝都燃烧篇另有[作内术语表](AGE2/games/imperial-capital-burns/translations/terminology.ja-zh-Hans.csv) |
| 图片文字与排版 | [帝都燃烧篇图片文案表](AGE2/games/imperial-capital-burns/images/copy/) · [Photon 1,490 图身份清单](rUGP/evidence/photon-images-v6/) · [通用图片流程](localization/image-workflow.md) | 文案、尺寸、哈希、路由和工具已公开；图片二进制仍在权利清理中 |
| 字体 | [字形覆盖检查](localization/tools/font_coverage.py) · [rUGP 字体问题复盘](rUGP/docs/postmortems/font-runtime.md) · [AGE2 旧方案复盘](AGE2/docs/postmortems/font-glyph-substitution-retired.md) | 方法、代码和故障经验已公开；字体文件须先确认再分发许可 |
| 构建与格式工具 | [AGE2 tools](AGE2/tools/) · [rUGP formats](rUGP/formats/) · [rUGP runtime](rUGP/runtime/) · [通用工具](localization/tools/) | 源码和合成测试已公开；生产构建仍需合法游戏输入与实机 QA |

这里刻意区分“可编辑的汉化资产”和“游戏原始资源”。无字底、成品图和字体只有在来源、修改关系与许可证都可说明时才会进入 Git；临时生成批次、失败图、解包原件和未审计字体不会混进主线。

## 两套互不混用的引擎体系

| 目录 | 游戏 | 主要补丁路线 |
| --- | --- | --- |
| [`AGE2/`](AGE2/README.md) | TDA00–03、帝都燃烧篇 | 从 FPD/`pack.bin` 定位资源，处理 EGPACK、WebP、UI 字符串，以 LocalAppData 松散文件覆盖 |
| [`rUGP/`](rUGP/README.md) | Photon Flowers、Photon Melodies | 从 ICI 定位 RIO 对象，处理 CRsa、Cr6Ti、CRip007/008、RUO；必要时使用严格绑定版本的运行时 |

两套引擎的代码、测试、打包与事故记录完全分开。只有翻译规范、术语、图片制作和字体覆盖等引擎无关内容放在 [`localization/`](localization/README.md)。

## 仓库层级

```text
AGE2/          AGE2 游戏资产、格式工具、测试和专项记录
rUGP/          rUGP 游戏资产、编解码器、运行时、打包和逆向证据
localization/  翻译、术语、图片、字体与新语言通用工作流
docs/          玩家、研究、项目维护、法律与英文文档
.github/       自动测试、Issue 与贡献模板
```

更细的导航见[文档中心](docs/README.md)。路线图、贡献规范、发布规则和第三方来源都收在 `docs/` 下，不再占满仓库首页。

## 反馈与许可

[提交程序/安装问题](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml) · [提交译文修正](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml) · [参与贡献](docs/project/CONTRIBUTING.md)

自写代码采用 [MIT License](LICENSE)。MIT 不自动覆盖游戏内容、翻译文本、字体、衍生图片、发布包或第三方组件；详见[内容与发布政策](docs/project/asset-and-release-policy.md)、[第三方来源](docs/legal/THIRD_PARTY.md)与[法律说明](docs/legal/NOTICE.md)。
