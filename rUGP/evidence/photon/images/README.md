# photonflowers / photonmelodies 中文图片资源

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

这只是图片资源备份，不是可直接安装的游戏补丁，也不包含游戏本体。请支持正版游戏。
