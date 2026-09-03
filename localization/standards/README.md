# 翻译规范：阅读与执行顺序

[返回本地化工作区](../README.md) · [完整工作流](../workflow.md) · [English workflow](../workflow.en.md)

文件名前的 `01`—`06` 表示开工时的阅读和准备顺序。前三份用于确认项目与数据；
正文工作的核心顺序是：**通读剧情并冻结术语 → 初译 → 独立二审 → 解决疑点并同步术语
→ 技术写回与 QA → 玩家反馈复核**。编号不表示后读的规则可以覆盖前面的规则。

## 按什么顺序读和用

| 顺序 | 规范 | 什么时候用 | 进入下一步前要明确什么 |
| --- | --- | --- | --- |
| 01 | [单个游戏项目清单](01-game-project.md) | 新游戏或接手任务时 | 游戏、引擎、目标语言，以及正文、术语、图片和字体的权威入口；已有项目先读其 `project.toml` 和 README |
| 02 | [补丁源表规则](02-source-data.md) | 提取、核对来源及每次修改源表时 | 版本、JP 原文槽、稳定 ID、源哈希、scene 顺序与修改范围；公开表没有 JP 全文时需从合法本机源数据连接 |
| 03 | [翻译与图片表字段约定](03-table-schemas.md) | 选择现有表或新建工作表时 | 身份、源证据、目标译文和状态分别在哪一列；已有表保留历史字段映射 |
| 04 | [章节术语工作流](04-terminology.md) | 正文初译前，之后每批持续使用 | 通读剧情与人物关系、扫描全章专名、核对总表、冻结章节术语基线，并列出疑点 |
| 05 | [简体中文初译规则](05-translation.md) | 按完整 scene 或自然剧情段初译时 | 产出候选译文、`translated / question / blocked` 状态、术语增量和下一批起点 |
| 06 | [独立审核规则](06-review.md) | 每批候选完成后，独立重新阅读 JP 时 | 逐句给出 `keep / revise / question`，记录修改理由，复查全章一致性 |

接手已有章节时先核验 01—03 的现有成果，再加载该章冻结术语进入当前批次。
这些准备工作不用在每一批重新建一遍，但来源或版本发生变化时必须重新核验。

## 二审之后还要做什么

1. **解决疑点：**按[完整工作流第 4 步](../workflow.md#4-解决-question-并再次冻结术语)
   补齐上下文、语音、截图或设定证据。`question` 有记录不代表已经解决；缺少依据的
   `blocked` 项也不能交付定稿。修改术语后返回 04，更新基线并检查所有受影响位置。
2. **技术写回与自动检查：**定稿后按对应引擎的 [AGE2](../../AGE2/docs/quality.md)
   或 [rUGP](../../rUGP/docs/quality.md) 规则验证控制符、编码、容量、资源绑定与打包。
3. **实机与反馈：**完成[实机 QA](../workflow.md#7-实机-qa)，玩家反馈再回到 JP、
   术语和可维护源表复核，修正后重跑相关检查。

初译自检不能代替独立二审，二审通过不能代替技术验证或实机检查。

## 规则冲突时怎样判断

- **原意判断：**以当前版本 JP 原文及其剧情上下文为依据。英文槽、旧中文、OCR 和
  模糊匹配只能帮助发现问题，不能用于兜底定稿；缺少依据就记录 `question` 或 `blocked`。
- **固定译名：**先用本章已冻结且适用于该语境的项目译法和公共术语表，再按
  [术语确认依据](04-terminology.md#4-译法确认依据) 补充证据。若基线、总表或 JP
  语境相互冲突，应记录并确认变更，不能静默选一个覆盖其他记录。
- **中文表达：**在原意准确、信息完整、人物关系正确和术语一致的前提下调整语序与文风；
  不能为了顺口删改剧情信息，也不能因个人偏好改掉已确认译名。
- **章节补充：**可以细化角色语气、专属术语和资源特点，不能降低初译与审核的硬规则。
- **数据与技术：**稳定身份和源字段遵守 02，列映射遵守 03，控制符和写回合约遵守
  对应引擎规范。语义正确与技术可用都必须通过，不能互相替代。

## 与以前翻译时的用法对应

旧 TDA 交接要求先读共通规则、源文件位置与检查方法，再处理章节；Photon 的
初译、二审分支进一步明确了下面的依赖：

- 原 `TERMINOLOGY_WORKFLOW.md` 要求先扫描全章、核对总表并冻结基线，对应现在的 04。
- 原 `TRANSLATION_RULES.md` 把术语基线列为初译开工条件，对应现在的 05。
- 原 `REVIEW_RULES.md` 要求候选完成后重新阅读 JP、逐句审核，对应现在的 06。
- 原 `TECHNICAL_QA_RULES.md` 的职责现在分别由 AGE2 与 rUGP 的技术规范承担。

本次将现有项目清单、源数据和字段规范排为 01—03，补齐开工入口；04—06 延续以前
“先术语、再初译、后独立审核”的使用顺序。完整阶段和交付要求以[完整工作流](../workflow.md)为准。

## English summary

Read 01–03 to establish the game, authoritative source and table mapping. Then
read the story and freeze terminology (04), translate complete scenes (05), and
independently review each candidate against Japanese (06). Resolve questions and
update terminology before engine writeback, automated checks and in-game QA.
The numbers describe workflow order, not rule precedence.
