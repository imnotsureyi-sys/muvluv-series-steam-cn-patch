# 现行术语表

[返回本地化工作区](../README.md) · [术语维护规则](../standards/04-terminology.md)

这里集中存放系列通用表和七作现行术语表。点击文件即可在 GitHub 查看日文、中文和使用语境。
校对某部作品时，使用 **系列通用表 + 本作表**。

| 范围 | 术语表 | 条目数 |
| --- | --- | ---: |
| 系列通用 | [muv-luv.ja-zh-Hans.csv](muv-luv.ja-zh-Hans.csv) | 143 |
| TDA00 | [tda00.ja-zh-Hans.csv](tda00.ja-zh-Hans.csv) | 133 |
| TDA01 | [tda01.ja-zh-Hans.csv](tda01.ja-zh-Hans.csv) | 84 |
| TDA02 | [tda02.ja-zh-Hans.csv](tda02.ja-zh-Hans.csv) | 86 |
| TDA03 | [tda03.ja-zh-Hans.csv](tda03.ja-zh-Hans.csv) | 102 |
| 帝都燃烧篇 | [imperial-capital-burns.ja-zh-Hans.csv](imperial-capital-burns.ja-zh-Hans.csv) | 183 |
| photonflowers | [photonflowers.ja-zh-Hans.csv](photonflowers.ja-zh-Hans.csv) | 313 |
| photonmelodies | [photonmelodies.ja-zh-Hans.csv](photonmelodies.ja-zh-Hans.csv) | 750 |

每张表使用 `jp`（日文）、`cn`（中文）、`context`（适用语境）三列。
同一词在不同作品中的人物、称谓或场景可能不同，请连同语境阅读；各作专表不互相继承。
表中条目数按各表分别统计，不代表去重后的系列总数或全篇人工校对进度。

## 维护与查词

直接编辑这里对应的现行表；各游戏的 `project.toml` 已指向这些文件，无须维护第二份副本。
新增或修改译法时，先在本作基线记录出处和判断依据，审定后更新现行表；有跨作依据才提升到通用表。

```powershell
python localization/tools/terminology.py tda00 --term ウィル
python localization/tools/terminology.py photonflowers --term ミキ
```

工具只读取通用与本作表，同词异译会报错，不会自动改写正文。

## 查证与历史资料

旧版本、恢复清单、审计记录及各作基线入口统一放在[术语查证与历史记录](../terminology-history/README.md)。
候选、争议与历史译法不作为现行术语加载。

## English

This folder contains the current shared glossary and seven game-specific glossaries.
Use the shared table plus the target game's table, and respect each entry's `context`.
These are the maintained source files, not duplicate exports. Historical evidence is kept
in the [terminology records](../terminology-history/README.md).
