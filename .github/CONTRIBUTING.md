# 贡献者、致谢与参与 / Contributors, Credits & Contributing

[返回玩家首页](../README.md) · [公开的制作与研究成果](../docs/research/README.md) ·
[完整贡献指南](../docs/project/CONTRIBUTING.md)

## 项目维护与协助

- **[imnotsureyi-sys](https://github.com/imnotsureyi-sys)／Yi Shen：**项目发起、翻译与术语
  决策、实机验证、资源整理、Release 发布，以及公开内容的最终审核与责任。
- **[OpenAI Codex](https://openai.com/codex)：**在维护者指挥下协助代码、格式分析、翻译复核、
  术语整理、测试、文档和故障复盘。
- **OpenAI 图像模型／GPT Image 系列：**协助部分图片的无字底和候选视觉制作，成品仍由
  维护者审核。

## 特别感谢

我们从“主任保护协会”那里学到了 **通过松散文件结构覆盖游戏资源的方法**。
正是这份启发，让我们迈出了汉化的第一步，对此我们由衷感谢。
后续资源提取、翻译、工具开发与补丁制作由本项目自行完成。
具体技术参考与历史对照记录见下方及完整致谢页。

感谢“红桃皇后假说”为 **《樱花盛开之前》提供部分文本**。
感谢 ScRemilia、Tsubaki-G、X1AOFEI 及其他参与 TDA 人工校对、修正与反馈的朋友。

## 技术参考

- [GARbro](https://github.com/morkt/GARbro)：RIO／ICI 目录读取先例。
- [AFHook／AFEditor](https://github.com/eplightning/afhook)：AGES／rUGP Hook 架构及
  Cr6Ti 图片编解码行为参考。
- [rugptools](https://github.com/osmium76/rugptools)：历史 rUGP 格式与对象行为参考。
- **alterdec**：早期 rUGP 对象与图片行为资料，包含 Cr6Ti 解码状态机参考。
- **RioX**：早期 rUGP 对象与图片行为的历史资料；现有记录未固定具体版本与原始来源链接，
  不将其列为当前工具依赖。详见[研究参考](../docs/research/references.md)。
- [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager)：FPD v2 与
  `pack.bin` 结构参考。
- thcrap、07th-Mod、Committee of Zero、Tsukihimates、VNTranslationTools、Kuriimu2 等成熟
  项目提供了仓库组织、安装器、语言分层和工具设计方面的公开经验。

各项目的具体贡献边界和许可证说明见 **[完整贡献者与致谢](../docs/project/CONTRIBUTORS.md)**、
[参考项目比较](../docs/research/references.md)和[第三方来源](../docs/legal/THIRD_PARTY.md)。

## 参与项目

欢迎懂日语、愿意校对或修改译文的朋友加入
[TDA](https://paratranz.cn/projects/19505)、[帝都燃烧篇](https://paratranz.cn/projects/20659)、
[photonflowers](https://paratranz.cn/projects/20660) 或
[photonmelodies](https://paratranz.cn/projects/20661) 的 ParaTranz 项目。
即使不懂日语，也欢迎反馈错字、语句不通顺、显示异常或游玩问题，加入 **QQ 群：273626767** 交流。

- [报告补丁或运行问题](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=bug-report.yml)
- [提交翻译修正](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/issues/new?template=translation-review.yml)
- [阅读代码、文档和翻译贡献要求](../docs/project/CONTRIBUTING.md)

欢迎使用中文或英文提交 Issue 和 Pull Request。请勿上传完整游戏资源、游戏容器、账号信息或
来源不明的字体。

## English summary

Yi Shen (`imnotsureyi-sys`) maintains and reviews the project. OpenAI Codex and image models assist
under maintainer supervision. The project thanks 主任保护协会 for demonstrating the AGE2 loose-file overlay approach
that started our localization journey. Subsequent extraction, translation, tool development and patch
production are our own work, with specific references documented separately. We credit GARbro,
AFHook/AFEditor, rugptools, alterdec, RioX, FatePackageManager, and the other
listed patch projects for specific public technical precedents. See the
[full contribution guide](../docs/project/CONTRIBUTING.md) before opening a pull request.
