# photonmelodies

## 状态

- 分支：`chapter/photonmelodies`
- 当前公开版本：未发布
- 发布页：无
- native 行数：40,541
- 补丁状态：翻译/写回流程阶段

## 范围

该工作流对应 Steam 版 `Muv-Luv photonmelodies` 的 native 资源。

当前已经跑通 RIO/CRsa 提取、JP 文本工作表生成、中文写回测试和 byte patch 补丁包生成，但还不是公开发布版。

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
