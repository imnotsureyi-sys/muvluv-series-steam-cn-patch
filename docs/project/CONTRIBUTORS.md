# 贡献者与致谢

[返回项目首页](../../README.md) · [参与贡献](CONTRIBUTING.md) · [第三方来源与许可证](../legal/THIRD_PARTY.md) · [研究参考](../research/references.md)

本页区分三件事：直接维护本项目的人、使用 AI 工具完成的受监督工作，以及提供公开技术
先例或汉化思路的前人项目。被致谢不等于其作者审核、认可或共同发布了本补丁。

## 项目维护

| 名称 | 贡献 |
| --- | --- |
| [imnotsureyi-sys](https://github.com/imnotsureyi-sys)／Yi Shen | 项目发起、翻译与术语决策、实机验证、资源整理、Release 发布，以及对所有公开内容的最终审核与责任 |

## AI 辅助贡献

| 工具 | 贡献范围 | 责任边界 |
| --- | --- | --- |
| [OpenAI Codex](https://developers.openai.com/codex/) | 在维护者指挥下协助仓库架构、代码实现、格式分析、测试、文档、清单生成、故障复盘与重复性检查 | 不是独立维护者，不代替日文理解、实机验证、版权判断或发布批准；所有结果由人类维护者审核并负责 |
| OpenAI 图像模型／GPT Image 系列 | 在部分图片工作中辅助生成无字底或候选视觉修改 | 仅是图片制作的一步；文案、布局、身份、像素检查和最终入包仍须人工审核，具体可复现边界见[图片工作流](../../localization/image-workflow.md) |

GitHub 的贡献图由提交作者以及可验证的 `Co-authored-by` 身份生成。GitHub 要求共同作者
邮箱关联到其真实账号；Codex 没有一个可以由本项目冒用的个人 GitHub 邮箱，因此本项目
不会伪造账号或邮箱。AI 辅助通过本页和提交中的 `Assisted-by: OpenAI Codex` 说明记录；
真实人类共同作者则使用其本人确认的 GitHub 邮箱。参见
[GitHub 共同作者说明](https://docs.github.com/en/pull-requests/how-tos/commit-changes/creating-a-commit-with-multiple-authors)。

## 最初的汉化思路

> **致谢主任保护协会提供了 AGES 引擎的汉化思路。**

本项目发起者最初在研究 TDA 汉化时参考了主任保护协会公开发布的
[Steam 版 Muv-Luv Alternative Total Eclipse 汉化补丁](https://www.moyu.moe/patch/5461/resource)，
并保存了对方允许发布本项目独立完成的 TDA 汉化、同时希望在发布时加入上述致谢的沟通
记录。

该致谢只说明“汉化路线与思路”的来源。本仓库没有把对方补丁文件、译文、字体、图片或
代码作为可自由拆解的素材；链接页面明确限制拆解、二次修改和移植，因此我们只链接原始
发布页并尊重其条款。

## rUGP／AGES 技术前人

| 项目 | 本项目具体受益 |
| --- | --- |
| [GARbro](https://github.com/morkt/GARbro) | 提供 RIO/ICI 目录读取先例；本项目的 Python 目录读取器明确移植其 MIT 许可的 `ArcRIO.cs` 思路并保留完整版权声明。GARbro 负责“找到对象”，不是 Photon 万能重封工具。 |
| [AFHook](https://github.com/eplightning/afhook) | 提供“补丁制作工具与实机运行时分离”的 AGES/rUGP Hook 架构先例；PF/PM 的版本门、字体和图片运行时由本项目按自身目标重新实现。 |
| [rugptools](https://github.com/osmium76/rugptools) | 提供历史 rUGP、alterdec 与对象行为术语参考；因仓库整体许可证边界不够明确，本项目不复制其源码。 |

CRsa/CVM 边界、8311、RUO 使用限制、Cr6Ti/CRip007/CRip008 编码、42 个
shared/common 端点和 PF/PM 1,490 图闭环均由本项目针对自己的样本继续实验、测试和实机
验证；参考前人入口不等于照抄最终实现。

## AGE2／FPD 前人

| 项目 | 本项目具体受益 |
| --- | --- |
| [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager) | 主要参考 FPD v2／`pack.bin` 结构、提取流程和 `Scrambler.cs` 密钥调度；本项目增加严格边界、路径、哈希检查，并采用 LocalAppData 松散覆盖而非声称完成通用 `pack.bin` 重封。 |

## 仓库与工作流参考

本项目还研究了 [thcrap](https://github.com/thpatch/thcrap)、
[07th-Mod python-patcher](https://github.com/07th-mod/python-patcher)、
[Committee of Zero SGHD Patch](https://github.com/CommitteeOfZero/sghd-patch)、
[Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation)、
[VNTranslationTools](https://github.com/arcusmaximus/VNTranslationTools) 与
[Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2)。采用的主要经验是玩家与
开发者入口分离、语言分层、输入哈希、格式/运行时边界、生成物不进入 Git，以及文本、
图片、字体和构建逻辑清晰归类。

## 待维护者补充的人类贡献

下列名单由项目维护者核对本人希望公开的名字和链接后继续补充：

- 部分译文提供者；
- 日文、中文和术语校对者；
- 提供有效截图、章节定位与复现步骤的玩家反馈者；
- 图片文案、无字底、排版和字体测试贡献者；
- 代码、文档、安装器和多语言移植贡献者。

如果希望被列出、修改署名或匿名，请在 Issue/PR 中说明显示名称、链接和贡献范围；不要
未经本人同意公开私人账号或聊天截图。

## English summary

Yi Shen (`imnotsureyi-sys`) is the human maintainer and final reviewer. OpenAI
Codex is credited for supervised AI-assisted engineering, research, tests and
documentation without inventing a GitHub identity. The project also explicitly
credits 主任保护协会 for the original AGES localization approach and the
listed upstream tools for their narrowly described technical precedents.
