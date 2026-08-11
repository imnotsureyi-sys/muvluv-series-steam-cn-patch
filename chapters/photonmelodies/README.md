# photonmelodies

## 状态

- 分支：`chapter/photonmelodies`
- 当前公开版本：《时空的欠片》全文对照表与术语表（补丁尚未发布）
- 发布页：无
- native 行数：40,541
- 补丁状态：翻译/写回流程阶段

## 范围

该工作流对应 Steam 版 `Muv-Luv photonmelodies` 的 native 资源。

当前已经跑通 RIO/CRsa 提取、JP 文本工作表生成、中文写回测试和 byte patch 补丁包生成，但还不是公开发布版。

《A Shimmering Shard of Spacetime／時空の欠片（时空的欠片）》已完成两遍制汉化与全文审核，当前先公开可定位的 JP-CN 正文源表和本篇术语表；这不代表已经完成游戏内写回、实机测试或补丁发布。

## 《时空的欠片》公开源表

- [`patch-sources/photonmelodies_shard_of_spacetime_jp_cn_compare.csv`](../../patch-sources/photonmelodies_shard_of_spacetime_jp_cn_compare.csv)：36,176 个唯一 `stable_id`，覆盖 36,177 次 branch-aware route occurrence 与 42 个 scene/branch block。
- [`patch-sources/photonmelodies_shard_of_spacetime_terminology_jp_cn.csv`](../../patch-sources/photonmelodies_shard_of_spacetime_terminology_jp_cn.csv)：137 项本篇专名、固定表达和人物称谓。

公开正文表只保留稳定顺序、`stable_id`、RIO、scene、日文说话人、JP 原文和当前 CN 文本；内部批次、审核结论、问题单和证据定位不公开。发布前另按已冻结术语对 31 行残留旧写法做了机械一致性统一，没有重新裁译剧情内容。

### 署名

汉化整理与审核：Yi Shen（[`imnotsureyi-sys`](https://github.com/imnotsureyi-sys)）与 OpenAI Codex。

## 当前证据

- 本地章节工作区中已有 native 工作表。
- 保留的 native 行应具备 chapter、csv_row、stable_id、egpack、scene、jp_text 等稳定定位字段。
- 写回时必须保留控制符，并通过 stable_id 与 payload offset 定位原文槽。

## 维护重点

- 只从 JP 原文继续翻译和 QA。
- 生成的 repack/test 输出不得进入 Git 历史。
- 对外只发布 byte patch 或发布包，不发布完整 RIO 资源。

## 相关说明

- 本地工作区：`C:\Users\Administrator\.codex\worktrees\babb\Muv-LuvSeries汉化`
- 提取说明、写回测试和中间表暂时只保存在本地，等形成公开补丁源表后再放入 GitHub。
