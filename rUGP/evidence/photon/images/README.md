# photonflowers / photonmelodies 中文图片资源

[返回 Photon 证据入口](../README.md) · [完整资产地图](../../../../docs/research/asset-map.md) · [图片制作流程](../../../../localization/image-workflow.md)

这里保存 Muv-Luv photonflowers（PF）与 photonmelodies（PM）中文图片资源备份的公开清单与校验报告。完整图片包体积较大，作为 GitHub Release 附件保存，不进入 Git 历史。

> **分发整改未完成：**V6 的技术/本地化身份审核与分发权利审核不是一回事。清单中有 19 张 PNG 与官方来源文件字节完全相同；它们必须在下一份可分发资产中移除或改由合法本机输入重建。当前 Release 是历史研究资产，不是玩家补丁，也不代表通过现行[资产与发布政策](../../../../docs/project/asset-and-release-policy.md)。

## V6（2026-08-24）

- 技术/本地化审核集合：1,490 张 PNG；公开分发状态为 `pending-remediation`。
- PF：见 [`manifest.json`](manifest.json) 的 `games` 统计。
- PM：见 [`manifest.json`](manifest.json) 的 `games` 统计。
- 1,247 张：备份 PNG 文件字节与正式候选 SHA-256 完全一致。
- 243 张：历史候选 PNG 曾在本地清理时删除；备份由已封存的游戏原生记录双解码物化，并在 Release 包中同时保存原生记录。封包时必须复用原生记录，禁止把解码预览 PNG 再编码一次。
- 审核 JPG 从未作为备份源。

下载：

- [GitHub Release](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/photon-images-1490-20260824-v6)
- [完整图片包 ZIP](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/download/photon-images-1490-20260824-v6/MuvLuv_Photon_PF_PM_CN_Images_1490_20260824_v6.zip)
- [V6 发布说明](release-notes.md)

文件说明：

- `manifest.json`：逐项资源 ID、尺寸、正式候选 SHA、备份 PNG SHA、RGBA SHA、来源类型和原生记录信息。
- `verification.json`：对 Release ZIP 的独立回读结果。
- `SHA256SUMS.txt`：三项 Release 资产身份的仓库内审计表；其中使用发布页文件名 `manifest-v6.json` 与 `verification-v6.json`。

仓库与发布页为了避免含义混淆而使用了不同文件名：仓库中的
`manifest.json` 与 Release 附件 `manifest-v6.json` 字节完全相同，仓库中的
`verification.json` 与 Release 附件 `verification-v6.json` 字节完全相同。
因此仓库内短版 `SHA256SUMS.txt` 按 **Release 附件名**列出它们，并不是在引用
两个缺失的仓库文件。Release 另有
`MuvLuv_Photon_PF_PM_CN_Images_1490_20260824_v6.zip.sha256` 用于直接校验 ZIP；
ZIP 内部同名的 `SHA256SUMS.txt` 则是更长的逐成员校验表，不要把两者混为一谈。

## PM 西瓜教程倒计时补充审核（2026-09-04）

[`pm-watermelon-timer-runtime-routes-20260904.json`](pm-watermelon-timer-runtime-routes-20260904.json)
记录 11 个动态倒计时和 12 个整帧教程画面的逻辑/物理身份。动态项原本已在
V6 普通精确表内；本次只为缺失的 11 个唯一 Translation 槽整帧载荷追加
特殊路由，并保留既有 39 项不变。证据同时记录实机 Options 状态、语言 setter
调用栈、冷存档不触发 setter 的现象，以及本地截图和追踪文件的 SHA-256。
整帧中文 sidecar 是基于官方 Translation 槽画面生成的派生物，目前仍留在
Git 之外，等待单独审核的图片增量发布。0 秒画面先用同场景 300 秒画面修复
旧圈残片，再恢复原中文字，最后以 8 倍采样绘制一条闭合、固定 4 像素线宽且
不接触文字的黄色椭圆；证据账本记录其几何、掩码数量和最终 PNG/RGBA 哈希。

2026-09-05 从 `Altered Fable` 的 No.50 存档完成实机回放；300 秒教程帧、
0 秒闭合圈、教程选项和小游戏 300 秒帧均正常显示。剩余教程帧到小游戏的切换
过程中没有出现 831/8311、白屏、撕裂、字体或排版错误。零售游戏截图按仓库
边界留在本地，四个文件名、大小和 SHA-256 均写入上述证据账本。

这只是图片资源备份，不是可直接安装的游戏补丁，也不包含游戏本体。请支持正版游戏。
