# Muv-Luv Series Steam 版简体中文补丁

这是一个非官方、非商业的 Muv-Luv Series Steam 版简体中文补丁项目。目前已发布 `Muv-Luv Unlimited: THE DAY AFTER` TDA00/TDA01/TDA02/TDA03 四个章节的测试版补丁。

补丁不包含游戏本体，不提供破解，不修改 exe，不修改 Steam 原始 `pack.bin`，也不操作存档。请支持正版游戏。

## 下载

| 章节 | 当前版本 | 发布页 | 直接下载 |
| --- | --- | --- | --- |
| TDA00 | beta0.1 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda00-beta0.1/MuvLuv_TDA00_CN_Patch_beta0.1.zip) |
| TDA01 | beta0.2.2 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda01-beta0.2.2/MuvLuv_TDA01_CN_Patch_beta0.2.2.zip) |
| TDA02 | beta0.1 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda02-beta0.1) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda02-beta0.1/MuvLuv_TDA02_CN_Patch_beta0.1.zip) |
| TDA03 | beta0.1.6 | [发布页](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda03-beta0.1.6) | [下载](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/tda03-beta0.1.6/MuvLuv_TDA03_CN_Patch_beta0.1.6_full_achievement_fix.zip) |

历史版本见 [Releases](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases)。

## 快速说明

- 适用对象：已购买 Steam 正版 `Muv-Luv Unlimited: THE DAY AFTER` 的玩家。
- 当前状态：测试版，TDA00-03 均可下载使用。
- 主要内容：剧本文本、UI 文本、字幕图片、角色名字图和中文字体补丁。
- 反馈方式：欢迎带截图、章节位置、前后台词上下文反馈。反馈群：273626767。

## 文档

- [安装说明](docs/INSTALL.md)
- [卸载与还原](docs/UNINSTALL.md)
- [兼容性说明](docs/COMPATIBILITY.md)
- [常见问题](docs/FAQ.md)
- [更新日志](CHANGELOG.md)
- [版权与声明](NOTICE.md)

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

## 当前质量说明

- TDA01-03 已经过较多实机游玩、截图反馈和问题修正，当前未发现明显的字幕缺失、台词错位、重复台词或 `Text ID Not Found` 类硬性问题。
- TDA00 使用了更完整的工作流：先冻结 JP baseline，再按日文原文槽、speaker、ruby、XML 调用顺序进行翻译和审计；目前已粗略过一遍，但实机反馈仍少于 TDA01-03。
- 当前版本仍处于测试阶段，译文基于日文原文槽整理，并经过实机测试与反馈修正；仍欢迎玩家提交截图和上下文反馈以继续校对。

## 项目结构

这个 GitHub 仓库只保留必要公开资料：

- `docs/`：玩家安装、卸载、兼容性和常见问题文档。
- `screenshots/`：补丁效果截图和后续展示素材。
- `patch-sources/`：TDA00-03 当前补丁源 CSV。
- `tools/`：制作补丁用的可复用程序工具，包括 egpack/FPD 和 RIO/CRsa 相关工具。
- `glossary/`：Muv-Luv 共通 JP-CN 术语总表。
- `standards/`：翻译、补丁源文件和公开仓库范围规范。
- `chapters/`：各章节/工作流的简短状态卡片。

完整补丁目录、`payload/`、安装脚本和 zip 包属于发布资产，通过 GitHub 发布页或网盘镜像分发，不提交到仓库树。

## 致谢

特别感谢“主任保护协会”提供 AGES 引擎的汉化思路，并允许发布时注明感谢。

特别感谢群友子冰对 TDA01 提供反馈。

感谢所有参与测试、截图反馈和术语讨论的玩家。

## 免责声明

本项目为非官方、非商业同人补丁。不包含游戏本体，不提供破解，不修改 exe，不修改 Steam 原始游戏文件，不操作存档。

请支持正版游戏。本补丁仅供已购买 Steam 正版的玩家测试交流使用。
