# The Imperial Capital Burns / 帝都燃烧篇 beta0.1

这是帝都燃烧篇 Steam 版简体中文补丁的首个公开测试版。

## 本版内容

- 完整正文、旁白、speaker 与选项文本。
- 主菜单、设置、系统提示、章节选择等可见 UI。
- 角色名卡、播片文字条、日期地点卡及开局提示图。
- 沿用 TDA00-03 字体路线：正文、选项与 Common 使用 `SourceHanSansSC.otf` 常规字重，speaker 使用粗体；日期地点卡使用 `SourceHanSansSC-Bold.otf` 重绘。
- Windows 一键安装与安全卸载脚本。
- Steam Deck 手动替换说明。

翻译只以 JP 原文和 JP 语音为依据，不使用 EN 槽、旧中文或模糊匹配兜底。公开仓库同时提供 5,564 条 JP-CN 正文源表和 185 项本章术语表，方便定位与反馈。

## 安装

1. 退出游戏并解压补丁。
2. Windows 双击 `install.bat`。安装器会验证 Steam 原始 `pack.bin`、补丁清单及已有文件冲突，再写入 `%LOCALAPPDATA%\ancr\tm\data`。
3. Steam Deck 请阅读压缩包内的 `STEAM_DECK_MANUAL.txt`，按说明手动复制 loose overlay 文件。

补丁不会改写 Steam 游戏目录中的 `obb/pack.bin`，也不会修改 exe 或存档。卸载时运行 `uninstall.ps1`；脚本只删除哈希仍与本补丁一致的文件。

## 测试状态

- 已核对 5,564 条正文、91 个 speaker 变更和 18 个选项变更。
- 已核对 74 张实际调用的播片文字条、37 张角色名卡及 61 组日期地点卡。
- 已验证 534 个 payload 文件与清单哈希一致，Steam 原始 `pack.bin` 保持不变。
- 当前仍为 beta 测试版，欢迎提供截图、日期/章节位置和前后台词上下文。

## 致谢与声明

特别感谢“主任保护协会”提供 AGES 引擎的汉化思路。感谢所有参与测试、截图反馈和术语讨论的玩家。

本补丁非官方、非商业，仅供已购买 Steam 正版游戏的玩家学习交流使用。补丁不包含游戏本体，不提供破解。反馈群：273626767。
