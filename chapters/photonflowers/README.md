# photonflowers

## 状态

- 分支：`chapter/photonflowers`
- 当前公开版本：未发布
- 发布页：无
- native 行数：5,510
- 补丁状态：提取/审计阶段

## 范围

该工作流对应 Steam 版 `Muv-Luv photonflowers` 的 native 资源。

当前阶段是资源/文本提取和审计，还不是公开汉化补丁。

## 当前证据

- 已可提取 native RIO/CRsa 文本。
- v5 native 表共有 5,510 行：
  - 5,322 行高置信 native 文本。
  - 188 行来自 wide 审计层的短 JP 恢复文本。
- Bilibili 文本只作为审计/对齐参考，不能直接导入为翻译。

## 维护重点

- 保留 native JP 文本、stable_id、scene locator 和控制符。
- 不使用英文兜底、旧中文兜底或模糊匹配。
- 翻译或写回前必须确认行来源层级和审计置信度。

## 相关说明

- 本地工作区：`C:\Users\Administrator\.codex\worktrees\4d5b\Muv-LuvSeries汉化`
- 提取说明和中间表暂时只保存在本地，等形成公开补丁源表后再放入 GitHub。
