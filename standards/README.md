# 项目规范

这里保存公开仓库中需要长期维护的通用规则。翻译、审核和技术写回是三个不同阶段，不能用同一份状态或检查表混在一起。

## 推荐流程

1. `TERMINOLOGY_WORKFLOW.md`：全章扫描专名，确认并冻结章节术语基线。
2. `TRANSLATION_RULES.md`：只依据 JP 产出第一版 CN 候选。
3. `REVIEW_RULES.md`：独立回看 JP，逐句给出 `keep / revise / question`。
4. `TECHNICAL_QA_RULES.md`：按 EGPACK、RIO / CRsa、FPD 等格式写回并审计。
5. `PATCH_SOURCE_RULES.md`：维护可公开的稳定补丁源表。

## 文件

- `TRANSLATION_RULES.md`：初译输入、中文表达、批次推进和译者自检。
- `TERMINOLOGY_WORKFLOW.md`：章节术语扫描、确认、冻结、变更和 MAIN 总表同步。
- `REVIEW_RULES.md`：独立语义审核、逐句结论和审核完成标准。
- `TECHNICAL_QA_RULES.md`：控制符、资源写回、自动审计、实机和补丁验证。
- `PATCH_SOURCE_RULES.md`：补丁源表字段、修改边界和基础 QA。
- `PUBLIC_REPOSITORY_SCOPE.md`：公开 GitHub 仓库应保留和不应保留的内容。

## 不可降低的原则

- JP 原文是唯一翻译依据。
- 不使用英文槽、旧中文或模糊匹配作为兜底。
- 每篇开始翻译前先确认章节术语基线；普通词句不需要逐条审批。
- 初译状态使用 `translated / question / blocked`，不能把译者自检当成审核通过。
- 独立审核使用 `keep / revise / question`，并必须重新阅读 JP 和上下文。
- 修改资源前必须定位章节、CSV 行、文本 ID、资源文件、场景、说话人、JP 原文和当前 CN。
- 控制符按资源格式处理；EGPACK 中文正文不得加入 `\n`、`\r` 或真实换行。
- 修改后必须审计错位、空文本、重复、乱码、符号、控制符、外语残留和术语一致性。
- 完整补丁包、payload、repack 输出和本地交接材料不放入公开仓库树。
