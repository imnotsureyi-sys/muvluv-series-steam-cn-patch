# The Imperial Capital Burns / 帝都燃烧篇

## 状态

- 分支：`chapter/imperial-capital-burns`
- 当前版本：`beta0.1` 预发布测试版
- 翻译依据：JP 原文/JP 语音；不使用 EN 槽、旧中文或模糊匹配兜底
- 原始包：Steam App 2630300，FPD v2 `obb/pack.bin`

## beta0.1 范围

- 正文：5,564 条 JP→CN 文本，按稳定文本 ID、来源 EGPACK、场景和 JP speaker 审核并写回。
- speaker 与选项：91 个 speaker 变更、18 个选项变更，使用普通中文正文/选项字体与独立 speaker 字体配置。
- `uistring.epk`：76 个实际需要变化的菜单、设置、系统提示和章节选择 ID，按 ID 与 JP 原文双重精确匹配。
- 图片 UI：按 TDA 路线把现成 `_en.webp` 图像字节复制到对应 `_ja.webp` 槽；通用 `data` 44 项，本作实际优先加载的 `data_spec` 通用图 86 项。
- 角色卡：`11_name00–35_ja.webp` 与 `11_name_non_ja.webp` 共 37 张，以 JP 卡片为姓名依据，使用 TDA 字体在原 224×96 透明槽中重绘中文姓名。
- 播片文字条：制作 JP 脚本实际调用的 74 个 `add_telop_*`，保持原 1280×720 透明画布、原锚点和显示位置。
- 日期地点卡：61 张日文原卡及其 61 张兼容槽均已制作中文版本，保持原画布、字号和文字中心位置，使用 `SourceHanSansSC-Bold.otf`。
- 字体：配置与 TDA00-03 完全一致，正文、选项、Common、speaker 与 HUD 全部使用 `SourceHanSansSC-Bold.otf`，不使用 ATE 字体。
- 开局提示：沿用 TDA00-03 的中文非商业补丁提示图。
- 安装路线：FPD loose overlay，不改写、不重封 `pack.bin`；提供 Windows 一键安装及 Steam Deck 手动替换说明。

## 公开源表

- [`patch-sources/imperial_capital_burns_jp_cn_compare.csv`](../../patch-sources/imperial_capital_burns_jp_cn_compare.csv)：5,564 条正文 JP-CN 源表。
- [`patch-sources/imperial_capital_burns_terminology_jp_cn.csv`](../../patch-sources/imperial_capital_burns_terminology_jp_cn.csv)：185 项本章术语表。
- `body/speaker_ja_zh.csv`：speaker JP-CN 表。
- `phase1/choice_ja_zh.csv`：选项 JP-CN 表。

## UI 与图片清单

- `phase1/uistring_ja_zh.tsv`：JP→简中系统文本源表。
- `phase1/image_ui_copy.tsv`：44 个通用 `data` 图片素材复制白名单。
- `phase1/image_ui_copy_data_spec.tsv`：86 个本作 `data_spec` 通用图片素材复制白名单。
- `phase1/character_name_cards_ja_zh.tsv`：37 张角色名中文卡清单。
- `phase1/telop_ja_zh.tsv`：74 个文字条、JP 语音证据与简中排版。
- `phase1/location_date_cards_ja_zh.tsv`：61 张日期地点卡的 JP-CN 文本与排版定位。
- `phase1/inventory.md`：原始资源盘点、四类边界与工具路线。

完整补丁、payload、安装器和校验和只通过 GitHub Release 分发，不提交到仓库树。补丁不包含游戏本体，不修改 exe、Steam 原始 `pack.bin` 或存档。
