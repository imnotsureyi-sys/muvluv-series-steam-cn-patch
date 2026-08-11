# photonflowers

## 状态

- 分支：`chapter/photonflowers`
- 当前公开版本：EX 七篇第二遍审核源表
- 发布页：无
- native 行数：5,510
- 补丁状态：EX 七篇第二遍审核完成；尚未写回或实机验证

## 范围

该工作流对应 Steam 版 `Muv-Luv photonflowers` 的 native 资源。

当前阶段是资源/文本提取和审计，还不是公开汉化补丁。

## photonflowers EX 公开源表

- [`patch-sources/photonflowers_ex_jp_cn_compare.csv`](../../patch-sources/photonflowers_ex_jp_cn_compare.csv)：EX 七篇共 6,931 行的第二遍审核 JP-CN 全文对照表。
- [`patch-sources/photonflowers_ex_terminology_jp_cn.csv`](../../patch-sources/photonflowers_ex_terminology_jp_cn.csv)：88 项篇内专名、固定表达、人物称谓与用户审定译名。
- [`patch-sources/photonflowers_ex_terminology_baseline_v1.csv`](../../patch-sources/photonflowers_ex_terminology_baseline_v1.csv)：945 行第一遍开工前冻结的完整术语基线，保留分类、适用范围、来源权威、证据示例与来源字段。

公开正文表只保留连续阅读顺序、`stable_id`、RIO、scene、日文说话人、JP 原文和当前 CN 文本；控制字符转写为 `<01>`、`<03>`、`<05>`、`<0A>` 等可见标记。内部批次、审核状态、问题单和证据定位不公开。

88 项术语表是当前采用译名的精简公开表；945 行基线表是 `photonflowers-ex-terms-v1.0` 的历史冻结快照，其中的 `candidate`、`contextual` 与 `question` 表示开工时分类，不覆盖第二遍审核及后续用户裁定。

《桜の花が咲くまえに》的 2,209 条既有中文受保护：第二遍审核未直接修改这些旧译；其中发现的 221 条实质问题仍保留原 CN，等待用户以后逐项或按组批准。其余六篇及第一遍新译已经完成第二遍审核，当前非保护开放问题为 0。

### EX 七篇

1. 《樱花盛开之前》
2. 《和小武在一起！》
3. 《小武哥的尾巴》
4. 《白银同学，等一下！！》
5. 《白银……在吃吗？》
6. 《其名小武》
7. 《吾名冥夜》

### 署名

汉化整理与审核：Yi Shen（[`imnotsureyi-sys`](https://github.com/imnotsureyi-sys)）与 OpenAI Codex。

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
