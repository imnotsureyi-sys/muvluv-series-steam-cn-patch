# 补丁源表

这里保存 TDA00-03 当前补丁使用的 JP-CN 源表。

这些 CSV 是已发布 TDA 测试补丁的公开源表。表中保留 JP 原文、当前 CN 文本，以及工具写回和反馈定位所需的字段。

## 文件

| 文件 | 章节 | 行数 | 用途 |
| --- | --- | ---: | --- |
| `tda00_jp_cn_compare.csv` | TDA00 | 3,713 | `tda00-beta0.1` 当前 JP-CN 源表 |
| `tda01_jp_cn_compare.csv` | TDA01 | 8,565 | `tda01-beta0.2.2` 当前 JP-CN 源表 |
| `tda02_jp_cn_compare.csv` | TDA02 | 6,589 | `tda02-beta0.1` 当前 JP-CN 源表 |
| `tda03_jp_cn_compare.csv` | TDA03 | 6,913 | `tda03-beta0.1` 当前 JP-CN 源表 |

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

## 规则

- 翻译判断必须基于 `jp_text` 和 `speaker_jp`。
- 不使用英文槽作为翻译依据。
- 不使用旧中文兜底或模糊匹配兜底。
- 保留控制符和显示相关标记。
- 修改后至少检查空文本、Text ID Not Found、顺序错位、异常重复、乱码、英文残留和控制符损坏。
