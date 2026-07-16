# 补丁源表

这里保存 TDA00-03 与帝都燃烧篇当前补丁使用的 JP-CN 源表。

这些 CSV 是已发布测试补丁的公开源表。表中保留 JP 原文、当前 CN 文本，以及工具写回和反馈定位所需的字段。

## 文件

| 文件 | 章节 | 行数 | 用途 |
| --- | --- | ---: | --- |
| `tda00_jp_cn_compare.csv` | TDA00 | 3,713 | `tda00-beta0.1` 当前 JP-CN 源表 |
| `tda01_jp_cn_compare.csv` | TDA01 | 8,565 | `tda01-beta0.2.2` 当前 JP-CN 源表 |
| `tda02_jp_cn_compare.csv` | TDA02 | 6,589 | `tda02-beta0.1` 当前 JP-CN 源表 |
| `tda03_jp_cn_compare.csv` | TDA03 | 6,913 | `tda03-beta0.1` 当前 JP-CN 源表 |
| `imperial_capital_burns_jp_cn_compare.csv` | 帝都燃烧篇 | 5,564 | `imperial-capital-burns-beta0.1` 当前 JP-CN 正文源表 |
| `imperial_capital_burns_terminology_jp_cn.csv` | 帝都燃烧篇 | 185 | 本章专有术语、统一译名与审定依据 |

## 字段

当前公开源表只保留这些核心列：

- `call_order`：稳定调用/显示顺序。
- `id`：游戏文本 ID。
- `egpack`：来源包或容器。
- `scene`：场景或脚本定位信息。
- `speaker_jp`：日文说话人字段。
- `jp_text`：日文原文。
- `cn_text`：当前简体中文文本。

`review_status`、`audit_flags` 等内部审计列不放在公开源表中。

帝都燃烧篇术语表另保留 `jp`、`cn`、`occurrences` 与 `basis` 四列，用于核对本章统一译名；内部候选、问题单和审核过程列不公开。

## 规则

- 翻译判断必须基于 `jp_text` 和 `speaker_jp`。
- 不使用英文槽作为翻译依据。
- 不使用旧中文兜底或模糊匹配兜底。
- 保留控制符和显示相关标记。
- 修改后至少检查空文本、Text ID Not Found、顺序错位、异常重复、乱码、英文残留和控制符损坏。
