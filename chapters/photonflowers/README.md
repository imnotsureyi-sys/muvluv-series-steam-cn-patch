# photonflowers

## 状态

- 分支：`chapter/photonflowers`
- 当前公开版本：AL 五篇第二遍审校源表
- 发布页：无
- native 行数：5,510
- AL 审校目标行数：6,033
- 补丁状态：源表已审校，尚未写回或生成补丁

## 范围

该工作流对应 Steam 版 `Muv-Luv photonflowers` 的 native 资源。当前公开源表只覆盖 Alternative 世界线的五篇：

- 《编年史～赎罪～》
- 《雨舞者》
- 《编年史～告白～》
- 《编年史～继承～》
- `Chicken Divers`

当前阶段仍是源表审校，不是可安装汉化补丁。

## 当前证据

- 已可提取 native RIO/CRsa 文本。
- v5 native 表共有 5,510 行：
  - 5,322 行高置信 native 文本。
  - 188 行来自 wide 审计层的短 JP 恢复文本。
- Bilibili 文本只作为审计/对齐参考，不能直接导入为翻译。
- AL 五篇按稳定目标顺序形成 6,033 行 JP-CN 对照表，并完成第二遍逐行审核。
- 第一遍 3,158 个 `question` 已全部裁决为 `keep` 或 `revise`；终局候选没有 `question` 或 `blocked`。
- 21 处功能性 U+0001 终止符已逐处复核；公开 CSV 使用 `<01>` 等可见记号，避免嵌入原始控制字符。

## 公开源表

- `patch-sources/photonflowers_al_jp_cn_compare.csv`：AL 五篇 6,033 行全文 JP-CN 对照表。
- `patch-sources/photonflowers_al_terminology_jp_cn.csv`：姓名、称谓、军语、部队、装备与篇名统一表。
- `patch-sources/photonflowers_al_review_baseline.csv`：正式证据、项目定名、语境性裁决及用户最终裁定基线。

## 维护重点

- 保留 native JP 文本、stable_id、scene locator 和控制符。
- 不使用英文兜底、旧中文兜底或模糊匹配。
- JP 是语义判断的唯一依据；正式中文、术语和人物关系证据只用于裁决中文表达。
- 写回前仍须另行执行写回前审计、原生资源映射确认和游戏内验证。

## 质量边界

本次公开内容只包含全文对照、术语和审核基线。未写回 RIO、未启动游戏、未生成补丁或安装包，也未修改 EX、photonmelodies、TDA 或其他章节。
