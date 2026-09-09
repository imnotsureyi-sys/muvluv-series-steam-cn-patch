# 术语查证与历史记录

[返回现行术语表](../glossaries/README.md)

本目录保存历史快照与审计证据。记录中的原始路径、数量和哈希描述当时的状态；当前表的位置以现行术语入口和各作 project.toml 为准。

2026-09-09 按维护者确认进行[本篇／AL对齐及中文军衔修订](../reviews/main-al-alignment-20260909.md)。历史基线保留原始译法，修订记录逐条列出新旧译法。

后续完成的[独立发现目录](../references/main-al-independent-20260909/README.md)包含本篇403项、AL529项及77个共同词形；先独立发现再交叉比较，不是旧101／193项参考名单的命中扩展。

本篇／Alternative 的 [Steam 术语参考快照](../references/main-al-steam-20260909/README.md)单独存放，仅供查证，尚未加入生效术语表。

系列通用表为 [muv-luv.ja-zh-Hans.csv](../glossaries/muv-luv.ja-zh-Hans.csv)，目前 **143 条**（新增4条军衔规则）。
各作使用“通用表 + 本作术语表”，不继承其他作品的专表。基线用于查证和审校，不作为自动替换字典加载。

| 作品 | 本作术语表 | 基线证据记录 | 基线去重日文键 |
| --- | ---: | ---: | ---: |
| TDA00 | [133 条](../glossaries/tda00.ja-zh-Hans.csv) | [870 条](../../AGE2/games/tda00/terminology/baseline.ja-zh-Hans.csv) | 365 |
| TDA01 | [84 条](../glossaries/tda01.ja-zh-Hans.csv) | [480 条](../../AGE2/games/tda01/terminology/baseline.ja-zh-Hans.csv) | 187 |
| TDA02 | [86 条](../glossaries/tda02.ja-zh-Hans.csv) | [534 条](../../AGE2/games/tda02/terminology/baseline.ja-zh-Hans.csv) | 198 |
| TDA03 | [102 条](../glossaries/tda03.ja-zh-Hans.csv) | [616 条](../../AGE2/games/tda03/terminology/baseline.ja-zh-Hans.csv) | 236 |
| 帝都燃烧 | [183 条](../glossaries/imperial-capital-burns.ja-zh-Hans.csv) | [264 条](../../AGE2/games/imperial-capital-burns/terminology/baseline.ja-zh-Hans.csv) | 185 |
| PF | [298 条](../glossaries/photonflowers.ja-zh-Hans.csv) | [1561 条](../../rUGP/games/photonflowers/terminology/baseline.ja-zh-Hans.csv) | 1178 |
| PM | [745 条](../glossaries/photonmelodies.ja-zh-Hans.csv) | [3656 条](../../rUGP/games/photonmelodies/terminology/baseline.ja-zh-Hans.csv) | 2668 |

基线保留同一词的不同来源、不同状态和语境，**记录数不等于已确认术语数**。同一个词也可在通用表和专表有各自的使用依据，两表行数不能直接相加。TDA01–03 是依据旧词库及本作日文重建的基线，不冒充旧的完整人工审定表。

## 应该看哪张表

- 查系列稳定译法：通用表。
- 校对当前作品：本作术语表，必须连同 context 使用。
- 查旧译、候选、篇章限制、争议和为什么没有采用：本作基线。

术语表三列为 `jp,cn,context`。基线九列为 `jp,cn,status,chapter,source,source_row,source_status,occurrences,basis`。
`confirmed`、`contextual`、`candidate`、`question`、`excluded` 分别表示确认、语境限定、候选、疑问、退出使用。原记录的状态另保存在 `source_status`，不会因这次整理被抹掉。空中文候选也予以保留。

旧“激光级”、拟声片段“ァァ”等可能出现在基线或历史表中，**不代表它们恢复为现行采用译法**。光线级、重光线级及壬姬遵循当前修正。

## 来源与完整性

[恢复说明](recovery-20260908.md)记录原表规模、TDA 重建方法和未完成的语义确认；[恢复清单](recovery-20260908.json)记录原文件提交号、哈希和逐作计数。

完整恢复的独立输入包括：帝都燃烧 185 条、PF EX 表 88 条及基线 945 条、PF AL 表 98 条、PM 时空的欠片表 417 条及基线 2,321 条、PM 憧憬／再诞表 341 条，以及 TDA00 草案 369 条。不同表间有重复，不相加当作独立词总量。

[首次审计](scope-audit-20260908.md)已撤回“资料齐全／完成”结论，仅保留为历史。[旧混合表](mixed-20260908.csv)和[帝都旧表](imperial-20260908.csv)是历史校验副本，不参与加载。官方完整日英例句不重新公开，保留术语和来源定位。

## 使用与维护

每作 `project.toml` 明确指定 `terminology_common_authority`、`terminology_authority`、`terminology_baseline`。读取工具不会扫描、拼接其他作品或历史目录。

```powershell
python localization/tools/terminology.py photonflowers --term ミキ
python localization/tools/terminology.py tda00 --term ウィル
```

通用与本作出现同词异译时工具报错，不能以加载顺序覆盖。候选匹配采用片假名边界，避免ウィル命中ウィルス；单字人名仍须严格按人物/说话人语境判断。没有自动改写正文的操作。

新增或修改术语先在本作基线记录出处、状态和适用范围，审定后再改对应使用表；有跨作依据才提升到通用表。新增语言建立独立文件，不覆盖简体中文。具体规则见 [章节术语工作流](../standards/04-terminology.md)。
