# 03 · 翻译与图片表字段约定

[规则顺序](README.md) · 上一步：[02 源数据](02-source-data.md) · 下一步：[04 术语](04-terminology.md)

[返回本地化工作区](../README.md) · [源数据规范](02-source-data.md) · [单个游戏项目清单](01-game-project.md)

本仓库有多代已经由 manifest 和 SHA-256 锁定的表。为了“看起来统一”直接重命名历史
表头，会改变整份 CSV 字节、破坏公开证据并让旧工具失配。因此采用两层规则：

1. 已封存表保留现有 schema，由工具显式声明字段映射；
2. 新建的跨引擎工作表使用下面的规范核心字段。

## 新表的规范核心字段

| 字段 | 含义 |
| --- | --- |
| `stable_id` | 不依赖当前排序的资源/文本身份 |
| `source_locale` | BCP 47 源语言，例如 `ja` |
| `target_locale` | BCP 47 目标语言，例如 `zh-Hans`、`ko`、`ru` |
| `source_text_sha256` | UTF-8 源字段的准确 SHA-256 |
| `localized_text` | 面向人的已翻译候选或定稿文本 |
| `review_status` | `translated`、`keep`、`revise`、`question`、`blocked` 等受控状态 |
| `notes` | 必要且可长期维护的说明；临时聊天过程不放入正式表 |

引擎可以追加 `egpack`、`rio_file`、偏移、容量、控制符或 runtime binding 等字段，但不
应改变核心字段含义。

## 现有封存表的兼容映射

| 范围 | 身份 | 源哈希 | 人类译文 | 特殊说明 |
| --- | --- | --- | --- | --- |
| AGE2 TDA/帝都正文 | `id` | `source_text_sha256` | `cn_text` | 已由快照哈希绑定，暂不改表头 |
| rUGP 已审校正文 | `stable_id` | `source_text_sha256` | `translated_text` | 面向完整审校与其他语言移植 |
| rUGP 精确运行时表 | `stable_id` | `source_field_sha256` | `translation_text` | `runtime_text` 是写入值，不一定等同展示用译文 |
| 帝都图片文案 | `asset_id` | `source_text_sha256` | `zh_cn` | 还要结合源图锁、排版和资源路径 |
| 系列总术语 | `jp` | 当前无逐行哈希 | `cn` | 小型人工维护表；新增语言应建立独立文件 |

## 新语言模板

[`create_locale_template.py`](../tools/create_locale_template.py) 不猜测这些历史字段。调用者
必须显式提供身份列、源哈希列和旧目标文本列；工具删除旧目标文本并创建空的
`target_locale,target_text`。这能在不修改已封存中文权威的情况下，为韩语、俄语等目标
生成统一工作入口。

## 文件命名

- 同时包含源与目标文本/身份时优先：`<scope>.ja-zh-Hans.csv`；
- 只包含目标权威、源文本仅以哈希表示的历史文件可保留 `<scope>.zh-Hans.csv`；
- 新语言使用含义准确的 BCP 47 标识：`cn` 不是语言代码，`kr` 表示卡努里语而不是韩语；
  `ru-RU` 是合法的“俄罗斯地区俄语”标签，但项目没有地区差异时应使用较简洁的 `ru`；
- 版本号写入 schema、manifest 与 Git tag，活动目录名保持稳定。

## English summary

New cross-engine tables should use `stable_id`, BCP 47 source/target locales,
`source_text_sha256`, `localized_text` and an explicit review state. Existing
hash-sealed tables retain their historical headers and use declared mappings;
renaming them for cosmetic consistency would destroy provenance.
