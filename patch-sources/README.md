# 补丁源表

这里保存各章节当前公开的 JP-CN 源表、术语表和审核基线。

TDA00-03 与帝都燃烧篇表格对应已发布测试补丁。photonflowers AL 五篇目前只公开审校源表，不代表已经写回或发布补丁。

## 文件

| 文件 | 章节 | 行数 | 用途 |
| --- | --- | ---: | --- |
| `tda00_jp_cn_compare.csv` | TDA00 | 3,713 | `tda00-beta0.1` 当前 JP-CN 源表 |
| `tda01_jp_cn_compare.csv` | TDA01 | 8,565 | `tda01-beta0.2.2` 当前 JP-CN 源表 |
| `tda02_jp_cn_compare.csv` | TDA02 | 6,589 | `tda02-beta0.1` 当前 JP-CN 源表 |
| `tda03_jp_cn_compare.csv` | TDA03 | 6,913 | `tda03-beta0.1` 当前 JP-CN 源表 |
| `imperial_capital_burns_jp_cn_compare.csv` | 帝都燃烧篇 | 5,564 | `imperial-capital-burns-beta0.1` 当前 JP-CN 正文源表 |
| `imperial_capital_burns_terminology_jp_cn.csv` | 帝都燃烧篇 | 185 | 本章专有术语、统一译名与审定依据 |
| `photonflowers_al_jp_cn_compare.csv` | photonflowers AL 五篇 | 6,033 | 第二遍逐行审校后的全文 JP-CN 对照源表 |
| `photonflowers_al_terminology_jp_cn.csv` | photonflowers AL 五篇 | 98 | 姓名、称谓、军语、部队、装备与篇名统一表 |
| `photonflowers_al_review_baseline.csv` | photonflowers AL 五篇 | 104 | 正式证据、项目定名、语境性裁决与用户最终裁定基线 |

## 字段

当前公开源表只保留这些核心列：

- `call_order`：稳定调用/显示顺序。
- `id`：游戏文本 ID。
- `egpack`：来源包或容器。
- `rio_file`：来源 RIO 文件；部分全文对照表使用该列。
- `scene`：场景或脚本定位信息。
- `speaker_jp`：日文说话人字段。
- `jp_text`：日文原文。
- `cn_text`：当前简体中文文本。

`review_status`、`audit_flags` 等内部审计列不放在公开源表中。

术语表另保留 `jp`、`cn`、`occurrences` 与 `basis` 四列，用于核对统一译名和依据。

photonflowers AL 审核基线表保留：

- `version`：裁决基线版本。
- `category`：姓名、称谓、军语、篇名或语境性问题等类别。
- `jp` / `cn`：裁决对象与采用形式。
- `status`：正式确认、语境性采用、项目定名或用户最终裁定。
- `scope`、`basis`、`handling`：适用范围、证据和具体处理边界。

内部候选、逐行状态、问题单和审核过程列不公开。photonflowers AL 公开表中的功能控制符统一写成 `<01>`、`<02>`、`<03>`、`<0A>` 等可见记号，不嵌入原始 U+0001/U+0002/U+0003 字符。

## 规则

- 翻译判断必须基于 `jp_text` 和 `speaker_jp`。
- 不使用英文槽作为翻译依据。
- 不使用旧中文兜底或模糊匹配兜底。
- 保留控制符和显示相关标记。
- 修改后至少检查空文本、Text ID Not Found、顺序错位、异常重复、乱码、英文残留和控制符损坏。
- 公开源表不等于可安装补丁；RIO 写回、打包和游戏内验证必须作为独立阶段执行。
