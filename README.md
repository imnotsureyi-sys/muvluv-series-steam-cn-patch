# Muv-Luv Series Steam 版简体中文补丁

这是一个非官方、非商业的 Muv-Luv Series Steam 版简体中文补丁总库。

当前已经整理并发布 `Muv-Luv Unlimited: THE DAY AFTER` TDA00/TDA01/TDA02/TDA03 四个章节的测试版补丁。补丁不包含游戏本体，不提供破解，不修改 exe，不修改 Steam 原始 `pack.bin`，也不操作存档；安装脚本只写入本地用户缓存目录。

## 下载

| 章节 | 当前版本 | 发布页 | 直接下载 |
| --- | --- | --- | --- |
| TDA00 | beta0.1 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1.zip) |
| TDA01 | beta0.2.2 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2.zip) |
| TDA02 | beta0.1 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1.zip) |
| TDA03 | beta0.1.6 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1.6) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda03-beta0.1.6/MuvLuv_TDA03_CN_Patch_beta0.1.6_full_achievement_fix.zip) |

如果 GitHub 下载较慢，可以等待网盘镜像。历史版本见 [Releases](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases)。

## 当前范围

已发布测试版：

- Muv-Luv Unlimited: THE DAY AFTER TDA00
- Muv-Luv Unlimited: THE DAY AFTER TDA01
- Muv-Luv Unlimited: THE DAY AFTER TDA02
- Muv-Luv Unlimited: THE DAY AFTER TDA03

计划纳入：

- Muv-Luv photonflowers
- Muv-Luv photonmelodies
- 帝都燃烧篇

## 汉化范围

当前 TDA00-03 补丁覆盖：

- 剧本文本简体中文化。
- UI 文本、设置界面、章节名等可见内容汉化。
- 视频 / 开场演出字幕图片汉化。
- 角色语音切换界面名字图汉化。
- 简体中文字体补丁。
- 一键安装脚本与手动安装说明。

## 当前质量说明

- TDA01-03 已经过较多人工核对、实机游玩和截图反馈修正，当前未发现明显的中文语义不通顺、字幕缺失、台词错位、重复台词或 Text ID Not Found 类硬性问题。
- TDA00 使用了更完善的工作流：先冻结 JP baseline，再按日文原文槽、speaker、ruby、XML 调用顺序进行翻译和审计；目前已粗略过一遍，但实机反馈还少于 TDA01-03。
- 制作者本人不懂日语，所有版本仍未经过完整日中人工校对，可能仍有错译、语病、术语不一致、说话人错位、缺字、空字幕或其他显示问题。

发现问题时，欢迎带截图、章节位置、前后台词上下文反馈。

反馈群：273626767

## 工作原则

- 只以日文原文字幕 / 日文 speaker 原文为依据。
- 不使用英文槽作为翻译依据。
- 不恢复英文兜底写回。
- JP 原文槽为空时，不直接判断游戏一定不显示，必须核对实际显示槽 / egpack。
- 修改后同步源 CSV、repack、当前游戏缓存和发布包。
- 每次发布前检查压缩包完整性、空文本、Text ID Not Found、异常重复、术语一致性和显示槽对齐。

## 项目结构

这个 GitHub 仓库只保留必要公开资料：

- `patch-sources/`：TDA00-03 当前补丁源 CSV。
- `tools/`：制作补丁用的可复用程序工具，包括 egpack/FPD 和 RIO/CRsa 相关工具。
- `glossary/`：Muv-Luv 共通 JP-CN 术语总表。
- `standards/`：翻译、补丁源文件和公开仓库范围规范。
- `chapters/`：各章节/工作流的简短状态卡片。

完整补丁目录、`payload/`、安装脚本和 zip 包属于发布资产，通过 GitHub 发布页或网盘镜像分发，不提交到仓库树。

内部 Codex 交接、ATE 参考分析、提交规则、一次性审计脚本、旧中间输出、完整游戏资源和测试 repack 只保存在本地，不随 GitHub 公开仓库发布。

## 致谢

特别感谢“主任保护协会”提供 AGES 引擎的汉化思路，并允许发布时注明感谢。

特别感谢群友子冰对 TDA01 提供反馈。

感谢所有参与测试、截图反馈和术语讨论的玩家。

## 免责声明

本项目为非官方、非商业同人补丁。不包含游戏本体，不提供破解，不修改 exe，不修改 Steam 原始游戏文件，不操作存档。

请支持正版游戏。本补丁仅供已购买 Steam 正版的玩家测试交流使用。
