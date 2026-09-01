# rUGP 游戏项目

[返回 rUGP](../README.md) · [完整本地化工作流](../../localization/workflow.md) · [Photon 图片证据](../evidence/photon/README.md)

PF 与 PM 使用同一套经审查格式和运行时，但仍是两个独立游戏项目。每部游戏都有自己的
Steam App ID、文本表、输入哈希、运行时配置、打包结果和实机 QA；一作通过不能自动
授权另一作。

| 游戏 | App ID | 已审校文本 | 当前精确绑定 | 图片权威 | 玩家状态 |
| --- | ---: | ---: | ---: | ---: | --- |
| [Photon Flowers](photonflowers/) | 889700 | 12,964 行 | 69 行 | [636 项](photonflowers/images/) | 尚无玩家包 |
| [Photon Melodies](photonmelodies/) | 889710 | 44,583 行 | 151 行 | [854 项](photonmelodies/images/) | 尚无玩家包 |

两作合计 1,490 项图片，其中有 1,448 个 translation peer 和 42 个经过认证的
shared/common 端点。完整清单保持共用，以免复制后漂移；每个游戏的 `images/README.md`
提供自己的筛选入口和状态说明。
