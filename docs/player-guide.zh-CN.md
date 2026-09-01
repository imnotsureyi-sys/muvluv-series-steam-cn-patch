# 玩家安装、卸载与排错指南

[English](player-guide.md) · [玩家下载](../README.zh-CN.md#玩家下载) · [提交 Bug](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)

## 安装前先知道

目前可供玩家使用的是历史 AGE2 prerelease/测试补丁。它们把松散文件复制到当前用户的 LocalAppData，不重写 Steam 原始 `pack.bin`、EXE 或存档。Photon 源码和 1,490 张 Photon 图片 Release **都不是玩家安装包**。

这些 beta 早于本仓库现在的发布门槛，尚未统一包含安装清单、输入版本哈希检查、卸载器或随字体附带的许可证说明。`install.bat` 成功只代表文件复制完成，不代表经过更新或被其他补丁修改的游戏一定兼容。

只使用首页下载表列出的最新历史版本。不要安装已被取代的 `tda01-beta0.1`、`tda01-beta0.2`、`tda01-beta0.2.1` 或 `tda03-beta0.1`；`tda01-beta0.2` 会产生 603 个不可见正文槽，`tda03-beta0.1` 误用了 TDA02 的 UI/成就映射。

历史构建也没有冻结并复核逐作安装时的 Steam/游戏语言槽设置；不同测试机留下过日语与英语配置，不能据此推导一个统一要求。不要为了“试出汉化”盲目覆盖另一作或另一语言的文件。如果补丁安装后仍显示日文/英文，请在反馈中附上该作 Steam 属性里的语言，以及 `appmanifest` 的 `UserConfig.language` / `MountedConfig.language`；在逐作重新实测前，本指南不会猜一个语言值。

## Windows 安装

1. 在 Steam 购买并安装对应游戏。若用户目录尚未生成，可先启动一次，再完全退出游戏。
2. 从[玩家下载表](../README.zh-CN.md#玩家下载)获取该作准确的 ZIP；不要使用 GitHub 仓库源码 ZIP。
3. 发布页有校验文件时一并下载，并在打开 ZIP 前校验。
4. 把整个 ZIP 解压到路径较短且可写的位置；不要直接在压缩包预览窗口中运行 `install.bat`。
5. 若已经安装其他补丁或手动修改过松散文件，先备份该作准确的 `data\root` 目录，确保可以恢复。
6. 阅读包内 `README.txt` 确认当时的安装结构，保证 `install.bat` 与 `payload` 位于正确的相邻位置，再运行安装脚本；涉及回滚安全时，以本中央指南为准。
7. 完全重新启动游戏。只返回标题画面不够；继续旧存档前先检查标题/设置界面和第一段台词。

### 五作准确的 Windows 目标路径

| 游戏 | 松散覆盖目标 |
| --- | --- |
| TDA00 | `%LOCALAPPDATA%\ancr\tda00\data\root` |
| TDA01 | `%LOCALAPPDATA%\ancr\tda01\data\root` |
| TDA02 | `%LOCALAPPDATA%\ancr\tda02\data\root` |
| TDA03 | `%LOCALAPPDATA%\ancr\tda03\data\root` |
| 帝都燃烧篇 | `%LOCALAPPDATA%\ancr\tm\data\root` |

不要把某一作的 `root` 复制到另一作。TDA03 beta0.1.6 会先删除且只删除自己的 `...\tda03\data\root`，再复制完整替换内容；如果里面还有个人松散文件，运行前必须备份。

TDA03 beta0.1.6 还附带历史文件 `0.1.6-fix-report.json`，其中
`source_package` 与 `package_dir` 元数据保留了制作者工作站的绝对路径。这两项不会被
`install.bat` 读取或执行，也不是安装目标；本指南与公开发布索引只记录经过脱敏的风险说明，
不复述路径内容。

Steam Deck 仅在发布包附带说明时按包内步骤操作，并确认使用的是该作自己的 Proton prefix。不要把 Windows 路径原样复制到无关 prefix。

## 校验下载文件

目前五作中有四个在 ZIP 旁发布了 SHA-256 文本文件。TDA03 beta0.1.6 没有单独校验附件，GitHub 记录的 ZIP 摘要为 `4B6CA4A531E9D07315E84DC2E02D7D8008C9B78EA4466172B45CAD1CEBA5C67D`。Windows PowerShell 可运行：

```powershell
Get-FileHash -Algorithm SHA256 "C:\Downloads\patch.zip"
```

把完整十六进制结果与发布页校验文件逐字比较。下载哈希一致只能排除传输或镜像损坏，不能证明游戏版本兼容。

## 卸载与回滚

现有 beta 并非全部带有逐文件安装清单，因此无法追溯承诺一个统一、精确的卸载器。

1. 完全退出游戏。
2. 包内还原文字只能视为历史说明。绝不要照任何旧说明删除整个 `%LOCALAPPDATA%\ancr\<游戏>\data`；TDA01 beta0.2.2 包内确实存在这条已废弃建议。不得删除 `data\user`、存档或进度数据。
3. 安装前做过备份时，先把该作准确的 `data\root` 移到别处，再恢复备份。优先使用可恢复的移动/改名，不要立即永久删除。
4. 若既没有备份也没有完整清单，不要猜着逐项删除，更不要删除整个 `%LOCALAPPDATA%\ancr`、完整 Proton prefix、`data\user` 或任何存档/进度目录。请通过 [Bug 表单](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)询问该作的准确处理方法。
5. Steam“验证游戏文件完整性”只能修复 Steam 安装目录内由 Steam 管理的文件，**不会**检查或删除本补丁位于 LocalAppData 的松散覆盖，因此不能代替第 2–4 步。

今后按当前[发布流程](release-process.md)制作的补丁应附完整安装清单和经过测试的回滚路线。

## 兼容范围

- 只测试发布页写明的 Steam 游戏；其他商店、主机、手机版、未来 Steam 更新和整合版不自动兼容。
- 当前 AGE2 beta 安装器不会强制检查原始 `pack.bin` 哈希；五个历史 Release 也没有保存准确 Steam build/depot 身份或原始 `pack.bin` SHA-256，因此安装前无法证明当前 Steam 版本兼容。请先备份准确的覆盖根目录、谨慎测试，不要把“复制成功”当成验证通过。
- 不要叠加两个会覆盖相同文本、图片、字体或缓存路径的补丁。
- 更新补丁前先备份个人松散文件；新版可能为清理旧残留而重建该作准确的 `root`。

## 排错与反馈

只保留一个确定版本的补丁，在正确游戏中完全重启后复现，并提供：

- 游戏名与 Release tag；
- Windows 或 Steam Deck/Proton 环境；
- 游戏/补丁是否刚更新、是否还装有其他 Mod；
- 完整截图、章节/日期/路线和前后台词；
- 准确错误文字，以及属于缺字/回退英文/说话人错误/裁切/图片异色撕裂不显示/启动报错/成就问题中的哪一类；
- 已尝试的回滚步骤。不要把“只运行 Steam 验证”描述成已经移除 LocalAppData 补丁。

[提交补丁或运行时 Bug](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)。译文偏好请改用[翻译修正表单](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml)，并附日文原文和语境。不要上传完整游戏资源。
