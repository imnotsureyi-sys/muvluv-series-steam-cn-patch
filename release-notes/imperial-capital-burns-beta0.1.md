# The Imperial Capital Burns / 帝都燃烧篇 beta0.1

这是帝都燃烧篇 Steam 版简体中文补丁的首个公开测试版。

## 本版内容

- 完整正文、旁白、speaker 与选项文本。
- 主菜单、设置、系统提示、章节选择等可见 UI。
- 角色名卡、播片文字条、日期地点卡及开局提示图。
- 字体配置与 TDA00-03 完全一致：正文、选项、Common、speaker 与 HUD 全部使用 `SourceHanSansSC-Bold.otf`；日期地点卡同样使用该字体重绘。
- 与 TDA00-03 相同的精简 Windows 一键复制安装。
- Steam Deck 手动替换说明。

翻译只以 JP 原文和 JP 语音为依据，不使用 EN 槽、旧中文或模糊匹配兜底。公开仓库同时提供 5,564 条 JP-CN 正文源表和 185 项本章术语表，方便定位与反馈。

## 安装

1. 退出游戏并解压补丁。
2. Windows 双击 `install.bat`，把 `payload` 复制到 `%LOCALAPPDATA%\ancr\tm\data`。
3. Steam Deck 进入桌面模式，把 `payload` 里的 `root` 目录手动复制到 Proton 前缀的 `AppData/Local/ancr/tm/data`，选择合并并覆盖；包内 `SteamDeck手动安装.txt` 有同样的图形文件管理器说明。

压缩包严格采用 TDA00-03 的四项结构：`payload/`、`install.bat`、`README.txt`、`SteamDeck手动安装.txt`。已移除预览图、开发清单、PowerShell/卸载脚本、`.smash` 和未调用的备用字体，并移除多余外层目录，避免 Windows Explorer 解压日期地点卡时路径过长。

补丁不会改写 Steam 游戏目录中的 `obb/pack.bin`，也不会修改 exe 或存档。

## 测试状态

- 已核对 5,564 条正文、91 个 speaker 变更和 18 个选项变更。
- 已核对 74 张实际调用的播片文字条、37 张角色名卡及 61 组日期地点卡。
- 已验证精简后的 523 个必要 payload 文件均与已审核构建一致，Steam 原始 `pack.bin` 保持不变。
- 当前仍为 beta 测试版，欢迎提供截图、日期/章节位置和前后台词上下文。

## 致谢与声明

特别感谢“主任保护协会”提供 AGES 引擎的汉化思路。感谢所有参与测试、截图反馈和术语讨论的玩家。

本补丁非官方、非商业，仅供已购买 Steam 正版游戏的玩家学习交流使用。补丁不包含游戏本体，不提供破解。反馈群：273626767。
