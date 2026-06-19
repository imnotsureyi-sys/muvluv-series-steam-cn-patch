# Muv-Luv Series Steam 版简体中文补丁

这是一个非官方、非商业的 Muv-Luv Series Steam 版简体中文补丁总项目。

当前目标是把各章节 / 各作品的汉化补丁、术语表、检查工具、发布说明集中管理，方便测试、回滚、发布和收集反馈。

## 当前范围

计划纳入：

- Muv-Luv Unlimited: THE DAY AFTER TDA00
- Muv-Luv Unlimited: THE DAY AFTER TDA01
- Muv-Luv Unlimited: THE DAY AFTER TDA02
- Muv-Luv Unlimited: THE DAY AFTER TDA03
- Muv-Luv photonflowers
- Muv-Luv photonmelodies
- 帝都燃烧篇

## 当前状态

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| TDA01 | 迭代中 | 已在其他对话继续修正，发布前需同步最新成果 |
| TDA02 | 测试中 | 已生成 `beta0.1` 测试包 |
| TDA03 | 制作 / 核对中 | 仍需继续逐条核对和实机反馈 |
| 其他作品 | 计划中 | 等 TDA 工作稳定后再展开 |

## 下载方式

正式面向玩家的 zip 补丁不要直接放进 Git 仓库本体，建议放在 GitHub Releases 和百度网盘镜像。

当前发布/测试包状态：

- TDA01：已进入 `beta0.2.x` 测试阶段，zip 包通过 GitHub Releases / 百度网盘发布，不提交进 Git。
- TDA02：测试中，仍需继续实机反馈和复查。
- TDA03：制作 / 核对中，仍需继续逐条核对和实机反馈。

## 项目结构

- `handoff/`：给新对话接手使用的规则、路径、章节上下文。
- `chapters/`：每个章节 / 作品的状态、已知问题、发布记录。
- `release-notes/`：每次发布用的说明文本。
- `outputs/tda_text/*_deepseek_full.csv`：当前修正源 CSV。
- `outputs/glossary/`：术语表和专有名词表。
- `work/`：审计、打包、核对脚本。
- `tools/`：egpack / fpd / 字体相关辅助工具。

## 工作原则

- 只以日文原文字幕 / 日文 speaker 原文为依据。
- 不使用英文槽作为翻译依据。
- 不恢复英文兜底写回。
- JP 原文槽为空时，不能直接判定游戏一定不显示，必须核对实际显示槽 / egpack。
- 修改后要同步源 CSV、repack、当前游戏缓存和需要发布的压缩包。
- 每次发布前必须做残留扫描和显示文本审计。
- 如果 `git status` 显示已有未提交修改，先停下来确认，不要覆盖、不要 `reset`、不要丢弃他人或其他对话的改动。

更多规则见：

- `handoff/SHARED_RULES.md`
- `handoff/PROJECT_FILES.md`
- `handoff/TOOLS_AND_CHECKS.md`

## 分支工作流

本项目使用一个总库、三个章节分支：

- `main`：总库说明、发布流程、最终合并、打包和 Release。
- `chapter/tda01`：TDA01 专用修改分支。
- `chapter/tda02`：TDA02 专用修改分支。
- `chapter/tda03`：TDA03 专用修改分支。

同一个本地目录不要让多个对话同时写文件。最好一次只让一个章节对话实际修改；其他对话可以先分析截图、列问题。

章节对话开始前必须先执行：

```powershell
git status --short
```

如果工作区干净，再切到对应分支：

```powershell
git switch chapter/tda01
git pull origin chapter/tda01
```

TDA02 / TDA03 分别替换成 `chapter/tda02`、`chapter/tda03`。

章节对话修完后提交到自己的章节分支，不要直接推 `main`。回到总库对话后，再由总库对话合并、打包、发布。

完整交接模板见：

- `handoff/PROMPTS_FOR_NEW_THREADS.md`
- `handoff/BRANCH_WORKFLOW.md`

## 致谢

特别感谢“主任保护协会”提供 AGES 引擎汉化思路，并允许在发布时注明感谢。

也感谢所有提供截图、术语建议、错字反馈和实机测试的玩家。

## 免责声明

本项目不包含游戏本体，不提供破解，不修改 exe，不修改 Steam 原始游戏文件，不操作存档。

制作者本人不懂日语，当前版本未经过完整日中人工校对，可能仍存在错译、错字、术语不统一、说话人错位、空字幕、缺字或 Text ID Not Found 类问题。欢迎带截图和上下文反馈。
