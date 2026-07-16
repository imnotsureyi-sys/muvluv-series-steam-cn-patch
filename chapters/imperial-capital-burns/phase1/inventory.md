# 第一阶段资源盘点（历史基线）

本文件记录进入正文汉化前的只读盘点和当时的阶段边界，不代表 beta0.1 的最终覆盖范围。当前发布状态与完整范围见本章 [`README.md`](../README.md)。

## 原版定位与指纹

- appmanifest：`D:/Steam/steamapps/appmanifest_2630300.acf`
- 安装目录：`D:/Steam/steamapps/common/The Imperial Capital Burns`
- 资源包：`obb/pack.bin`
- 大小：965,436,479 bytes
- SHA-256：`1D749713C01AE4E825A82FA2E75BF232303B1510708BBC9B7B98275315F7344F`
- 容器：FPD v2；42,588 项；数据起点 `0x178214`

## 扩展名统计

| 扩展名 | 数量 | 包内存储字节 | 判断 |
|---|---:|---:|---|
| `.webp` | 18,705 | 255,750,877 | GUI、角色/事件图片、文字条等 |
| `.xml` | 11,226 | 3,941,606 | 索引、脚本旁挂信息及资源描述 |
| `.fcd` | 4,366 | 359,061,509 | FSNr 加密媒体，包含 JP 语音等 |
| `.txb` | 3,300 | 0 | 与 `.zstd` 成对的纹理描述 |
| `.zstd` | 3,300 | 70,295,160 | 压缩纹理数据 |
| `.avif` | 1,175 | 48,823,868 | 图像资源 |
| `.pso` | 218 | 649,412 | 着色器 |
| `.gut` | 168 | 610,283 | GUI/布局相关容器 |
| `.egpack` | 74 | 5,520,628 | ADV 多语言文本表 |
| `.ogv` | 22 | 195,796,540 | 过场视频；抽查的帝都燃烧篇 avant 为无音轨画面 |
| `.epk` | 8 | 61,954 | FSNr 文本/配置容器，包括 `uistring.epk` |
| `.png` | 7 | 58,600 | 图像 |
| `.json` | 7 | 12,524 | 配置/描述 |
| `.vso` | 6 | 11,628 | 着色器 |
| `.otf` | 4 | 23,299,432 | 字体 |
| `.cfg` | 2 | 1,830 | 字体配置 |

主要分布：`root/assets/data_spec/adv/game` 40,924 项；`data_spec/gui/textures` 564 项；`data/gui/textures` 449 项；`data/adv/sys` 227 项。数值来自修正后的 FPD v2 索引解析，不以相邻作品结构代替本作证据。

## 引擎与工具路线

- 外层为 FPD v2，使用 `tools/fpd/` 与对应 `Scrambler.cs` 只读解析/筛选提取。
- 正文表为 EGPACK，后续正文阶段才使用 `tools/egpack/`；本阶段不修改。
- `uistring.epk` 使用 FSNr EPK 工具解密/加密；补丁器仅改可见字段，并强制精确 JP baseline。
- `.fcd` 使用 FSNr FCD 解密获得 JP OGG，供文字条听译核对；不改写语音。
- `.webp` 可直接作为 loose overlay；文字条用 Pillow + TDA 字体制作 lossless WebP。
- 本作未发现需要走 RIO/CRsa 的本阶段目标；`tools/rio/` 经验仅作排除参考。

## 四类清单

| 分类 | 路径/格式 | 证据 | 推荐工具/处理 |
|---|---|---|---|
| 非正文可翻译 | `root/assets/data/epk/uistring.epk` | JP 槽含菜单、设置、系统提示 | FSNr EPK + `tools/uistring/patch_uistring.py` |
| 非正文可翻译 | `root/assets/data/gui/textures/**/_en.webp` → `_ja.webp` | 本作内 44 对素材实际存在；与 TDA 白名单交集一致 | 字节复制白名单 |
| 非正文可翻译 | `root/assets/data_spec/gui/textures/**/_en.webp` → `_ja.webp` | 实包提取确认本作优先加载这一层；122 对 JP/EN 字节不同的非正文 UI 素材 | 按 TDA 做法把 EN 字节原样复制到 JA 槽 |
| 非正文可翻译 | `root/assets/data_spec/adv/game/chr/00no_text_telop/add_telop_*` | JP 脚本实际引用 74 个编号，JP 基础图为透明占位 | JP 语音证据 + 1280×720 中文 WebP |
| 非正文可翻译 | `root/assets/data/gui/font/*` | 简中缺字需覆盖 | 完整复制 TDA font payload 并校验哈希 |
| 正文暂缓 | `root/assets/data_spec/adv/game/scr/*.egpack` | ADV 场景对白、旁白、多语言表 | 正文阶段按 JP 槽使用 `tools/egpack/` |
| 正文暂缓 | speaker 名称字段 | 与场景正文共同出现，用户指定同正文处理 | 正文阶段统一术语与姓名 |
| 无需翻译 | 日期/地点图片卡、地图、图解、HUD | 用户明确本阶段不处理 | 不进入 payload |
| 无需翻译 | 未调用文字条 `09`、`42–58`、`76–78`、`83–84`、`90` 等 | 全量 JP 脚本无引用 | 不生成、不替换 |
| 无需翻译 | `.pso`、`.vso`、`.zstd`、`.txb` 及绝大多数媒体 | 无可见本地化目标或不在批准范围 | 保持原版 |
| 未知待研究 | `.gut` GUI 容器与 `data_spec02` 变体 | 目前没有本阶段缺失界面的实机证据 | 出现缺项后再只读定位 |
| 未知待研究 | 其余 7 个 `.epk` | 尚未证明含必要可见文本 | 不猜测，不批量汉化 |

## 当时的边界结论

第一阶段补丁采用 loose overlay；当时不覆盖场景 EGPACK、语音 FCD 和视频 OGV，也不写回或重封原始 `pack.bin`。后续正文阶段在同一 loose overlay 路线中加入严格按 JP 槽生成的 EGPACK，并完成日期地点卡；原始 `pack.bin` 仍保持不变。ATE 只用于核对“独立画面文字层”的成熟做法，图片 UI 与字体实施均按 TDA；字体不采用 ATE 版本。
