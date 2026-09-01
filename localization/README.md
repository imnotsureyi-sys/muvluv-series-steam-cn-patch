# 通用本地化工作区

[返回首页](../README.md) · [制作新语言](new-locale.md) · [图片流程](image-workflow.md) · [翻译规范](standards/translation.md) · [术语规范](standards/terminology.md)

这里放不依赖具体引擎的本地化方法：翻译、术语、审核、图片制作、字体覆盖和新语言模板。FPD/EGPACK 工具属于 [AGE2](../AGE2/README.md)，RIO/RUO/Hook 属于 [rUGP](../rUGP/README.md)，不会混进本目录。

## 最重要的内容在哪里

| 内容 | 共用部分 | 游戏专属部分 |
| --- | --- | --- |
| 正文与 UI 文本 | [翻译规范](standards/translation.md)、[源数据规范](standards/source-data.md) | [AGE2 games](../AGE2/games/) · [rUGP games](../rUGP/games/) 下各自的 `translations/` |
| 术语 | [Muv-Luv 总术语表](glossaries/muv-luv.ja-zh-Hans.csv)、[维护规则](standards/terminology.md) | 只有确属单作的词才放进该游戏目录；例如[帝都燃烧篇术语](../AGE2/games/imperial-capital-burns/translations/terminology.ja-zh-Hans.csv) |
| 图片 | [无字底、确定性排字与 QA 流程](image-workflow.md)、[`tools/images/`](tools/images/) | [帝都图片文案](../AGE2/games/imperial-capital-burns/images/copy/) · [Photon 图片身份与路由](../rUGP/evidence/photon-images-v6/) |
| 字体 | [字形覆盖工具](tools/font_coverage.py) | 引擎实际选字和运行时问题分别记录在 [AGE2](../AGE2/docs/postmortems/font-glyph-substitution-retired.md) 与 [rUGP](../rUGP/docs/postmortems/font-runtime.md) |
| 审核与反馈 | [审核规范](standards/review.md) | 各引擎的质量门与实机清单 |

仓库目前公开的是可维护文本表、图片文案/身份/哈希、确定性工具与技术结论。成品图、无字底和字体二进制只有在权利与许可证可以说明时才进入 Git；未审计的本地批次不会冒充正式资产。

## 标准流程

1. **锁定原文身份：**记录游戏版本、原语言槽、资源 ID/路径与源哈希。
2. **导出稳定工作表：**身份、控制符和译文分列，不能只靠行号。
3. **依据原文翻译：**英语槽、OCR、旧补丁或机器输出只能辅助，不能悄悄代替日文依据。
4. **分层审核：**语义、术语、结构、图片/排版，最后才是实机路线。
5. **走正确引擎：**AGE2 与 rUGP 使用各自的写回、运行时和打包链。
6. **按清单发布：**声明支持的输入哈希、输出哈希、源码提交、字体许可和已知限制。

## 目录

- [`glossaries/`](glossaries/)：跨游戏共用术语。
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

This directory contains engine-neutral localization policy and tooling: source identity, translation/review tables, terminology, image authoring, font coverage and new-locale templates. Engine codecs and package builders remain under `AGE2/` or `rUGP/`. International teams should start with the [new-locale guide](new-locale.md).
