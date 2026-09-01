# 通用本地化工作区

[返回首页](../README.md) · **[完整工作流](workflow.md)** · [制作新语言](new-locale.md) · [表字段约定](standards/table-schemas.md) · [图片流程](image-workflow.md) · [字体](fonts/README.md)

这里放不依赖具体引擎的本地化方法：翻译、术语、审核、图片制作、字体覆盖和新语言模板。FPD/EGPACK 工具属于 [AGE2](../AGE2/README.md)，RIO/RUO/Hook 属于 [rUGP](../rUGP/README.md)，不会混进本目录。

## 最重要的内容在哪里

| 内容 | 共用部分 | 游戏专属部分 |
| --- | --- | --- |
| 正文与 UI 文本 | [完整流程](workflow.md)、[初译规则](standards/translation.md)、[第二轮独立审核](standards/review.md)、[源数据规范](standards/source-data.md) | [AGE2 games](../AGE2/games/) · [rUGP games](../rUGP/games/) 下各自的 `translations/` |
| 术语 | [Muv-Luv 总术语表](glossaries/muv-luv.ja-zh-Hans.csv)、[维护规则](standards/terminology.md) | 只有确属单作的词才放进该游戏目录；例如[帝都燃烧篇术语](../AGE2/games/imperial-capital-burns/terminology/ja-zh-Hans.csv) |
| 图片 | [无字底、确定性排字与 QA 流程](image-workflow.md)、[`tools/images/`](tools/images/) | [五部 AGE2 WebP 清单](../AGE2/games/README.md) · [帝都图片文案](../AGE2/games/imperial-capital-burns/images/) · [Photon 图片身份与路由](../rUGP/evidence/photon/README.md) |
| 字体 | [字体来源与发布规则](fonts/README.md)、[字形覆盖工具](tools/font_coverage.py) | 引擎实际选字和运行时问题分别记录在 [AGE2](../AGE2/docs/postmortems/font-glyph-substitution-retired.md) 与 [rUGP](../rUGP/docs/postmortems/font-runtime.md) |
| 审核与反馈 | [审核规范](standards/review.md) | 各引擎的质量门与实机清单 |

仓库目前公开的是可维护文本表、图片文案/身份/哈希、确定性工具与技术结论。成品图、无字底和字体二进制只有在权利与许可证可以说明时才进入 Git；未审计的本地批次不会冒充正式资产。

## 本项目实际采用的两轮流程

1. **合法提取并锁定身份：**记录版本、语言槽、资源 ID/路径与源哈希。
2. **先理解剧情并建立术语：**按 scene 阅读人物关系和前后文，冻结本章术语，不随机抽行翻译。
3. **第一次翻译：**按完整剧情段生成候选译文；疑点标为 `question`，不能硬猜。
4. **第二次独立审核：**重新阅读日文，逐句决定 `keep`、`revise` 或 `question`，不能只润色中文。
5. **解决问题并再次冻结术语：**用后文、语音、截图、设定和实际调用补证据。
6. **走正确引擎：**AGE2 与 rUGP 分别完成写回、格式验证、图片和字体检查。
7. **实机与玩家反馈：**按路线复现，反馈回到可维护源表后重跑测试和发布，而不是只修生成文件。

每一阶段的输入、输出、状态和完成门详见[完整工作流](workflow.md)。

## 目录

- [`glossaries/`](glossaries/)：跨游戏共用术语。
- [`fonts/`](fonts/)：字体来源、许可证、覆盖与发布规则。
- [`standards/`](standards/)：翻译、术语、原始数据与审核规范。
- [`tools/`](tools/)：新语言表、字体覆盖、图片制作与校验工具。
- [`tests/`](tests/)：不依赖游戏资源的合成测试。
- [`image-workflow.md`](image-workflow.md)：无字底、Image API 辅助、确定性排字与图片 QA。
- [`new-locale.md`](new-locale.md)：为 `ko`、`ru` 等新语言建立独立身份和工作表。

## 开始制作其他语言

使用 BCP 47 风格标识，如 `ko`、`ru`、`zh-Hans`。新语言必须新建文件或语言列，不能覆盖日文依据或现有中文。模板工具只保留稳定 ID、源哈希和明确选择的上下文，并把目标译文置空：

```powershell
python -m localization.tools.create_locale_template rUGP/games/photonflowers/translations/reviewed/alternative.zh-Hans.csv work/ru/photonflowers-alternative.csv --target-locale ru --identity-column stable_id --source-hash-column source_text_sha256 --text-column translated_text
```

完整要求见[新语言指南](new-locale.md)。

## 测试

```powershell
python -m pip install -r localization/requirements.txt
python -m unittest discover -s localization/tests -p "test_*.py" -v
python -m compileall -q localization
```

整仓检查见[贡献指南](../docs/project/CONTRIBUTING.md)。

## English summary

This directory contains the engine-neutral two-pass workflow: establish story
context and terminology, produce a first translation, independently review
each row as `keep`/`revise`/`question`, resolve questions, bind through the
correct engine, and feed in-game/player findings back into maintained source.
International teams should start with the [workflow](workflow.md) and
[new-locale guide](new-locale.md).
