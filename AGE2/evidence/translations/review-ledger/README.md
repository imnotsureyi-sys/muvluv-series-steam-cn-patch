# AGE2 文本复核清单

`pending.csv` 是从两组私有原文/译文对照审计导出的无正文队列，只保存游戏、资源稳定
身份、已公开源哈希、问题分类和审核状态；它既不复制官方日文，也不复制中文译文。

初始清单共有 246 个待检查身份：TDA00 72、TDA01 67、TDA02 77、TDA03 30。一行可
包含多个分号分隔分类。分类只是检索线索，不是自动修正；例如引号可能因中文句法合理
变化，必须回到合法原文和游戏上下文再决定。

`manifest.json` 绑定公开翻译表与产生该队列的私有审计输入。使用
[`build_review_ledger.py`](../../../tools/text/build_review_ledger.py) 重建；命令会拒绝
格式错误、身份歧义、源/译文漂移和覆盖既有输出。

该清单是维护工具，不会仅因“还有 pending”自动阻止历史包运行。状态变化必须通过审查
后的后续清单或重新生成，不能静默修改证据。

## English summary

This text-free queue records 246 stable AGE2 review identities and finding
categories without publishing source or localized prose. Findings are human
review leads, not automatic corrections.
