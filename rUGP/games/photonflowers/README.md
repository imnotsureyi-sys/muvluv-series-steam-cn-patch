# Muv-Luv photonflowers*

[返回 rUGP 游戏](../README.md) · [项目清单](project.toml) · [文本](translations/) · [图片](images/) · [完整工作流](../../../localization/workflow.md)

- Steam App ID：`889700`
- 目标语言：简体中文（`zh-Hans`）
- 玩家包：尚未发布
- 已审校文本：Alternative 6,033 行、Extra 6,931 行，共 12,964 行
- 当前精确运行时绑定表：69 行
- Photon 图片权威：PF 636 项

`translations/reviewed/` 保存完整审校中文、稳定 ID 和日文源哈希；它是继续审核与制作
其他语言版本的文本权威。`translations/zh-Hans.csv` 进一步保存偏移、容量、控制符、
运行时值和写入路线，只包含已经精确绑定的 69 行。两者不是重复，也不能把 12,964 行
自动说成已经全部接入当前 writer。

公开表故意不批量镜像完整官方日文。贡献者从合法游戏提取源文本后，通过稳定 ID 与
源哈希连接。图片使用 PF/PM 共用的 [Photon 清单](../../evidence/photon/README.md)，但
PF 有自己的输入哈希、运行时配置、安装包和实机 QA；PM 的成功不能替代 PF。

源码树和 1,490 图研究资产 Release 都不是玩家安装包。正式发布前仍需完成干净克隆
构建、准确输入版本门、图片/字体许可、下载后安装与回滚，以及完整路线检查。

## English summary

Photon Flowers exposes 12,964 reviewed rows, 69 currently runtime-bound rows
and 636 image authorities. Reviewed text, exact runtime bindings and binary
release payloads are deliberately separate stages.
