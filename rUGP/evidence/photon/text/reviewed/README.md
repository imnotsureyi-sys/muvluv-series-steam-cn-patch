# Photon 已审校文本证据

这里绑定四组故事共 **57,547 行**已审校简体中文，同时省略完整官方日文。它面向继续
审核、其他语言移植和未来构建，不声称每一行都已接入当前运行时；PF 69 行、PM 151 行
精确写入契约仍由各自 `translations/zh-Hans.csv` 负责。

| 公开表 | 行数 |
| --- | ---: |
| [Photon Flowers / Alternative](../../../../games/photonflowers/translations/reviewed/alternative.zh-Hans.csv) | 6,033 |
| [Photon Flowers / Extra](../../../../games/photonflowers/translations/reviewed/extra.zh-Hans.csv) | 6,931 |
| [Photon Melodies / Adoration + Resurrection](../../../../games/photonmelodies/translations/reviewed/adoration-resurrection.zh-Hans.csv) | 8,407 |
| [Photon Melodies / Shard of Spacetime](../../../../games/photonmelodies/translations/reviewed/shard-of-spacetime/) | 36,176 |

公开行保存调用顺序、稳定 ID、RIO 分卷、CRsa 场景、日文源字段 SHA-256 与中文译文。
说话人和完整日文只作为私有导出验证输入，不写入公开 CSV。导出器拒绝顺序缺口、重复
身份、RIO/scene 不一致、空必需字段、内嵌 `U+0000`、源哈希漂移和行数漂移。

给定与 manifest 哈希完全相符的合法私有对照表，可运行：

```powershell
python -m rUGP.tools.text.export_reviewed_translation `
  "<private-comparison.csv>" `
  "<new-public.zh-Hans.csv>" `
  --expect-source-sha256 <SHA256> `
  --expect-id-prefix pf --expect-rows 6033
```

时空碎片按 RIO 分卷拆为三个文件，避免单文件逼近仓库 10 MiB 硬门。测试按 manifest
顺序重新连接并验证历史合并身份；临时合并文件必须留在忽略的工作目录。

## English summary

This authority binds 57,547 reviewed Simplified Chinese rows using stable IDs
and exact Japanese source hashes without mirroring the complete official
script. Reviewed rows remain distinct from the smaller exact runtime-binding
contracts.
