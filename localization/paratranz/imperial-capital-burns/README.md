# 帝都燃烧 ParaTranz Action 试点

项目固定为 [20659](https://paratranz.cn/projects/20659)，初始范围 75 个文件、5,749 条。
只拉取正文、姓名、选项、界面四份既有中文表。术语表、图片、辅助资源以及 TDA/PF/PM
不在此 Action 的写入范围内。现有文件不删除、不拆分、不重新上传。

## 使用

合并工作流 PR 后，在 Actions → **ParaTranz ICB pilot** → **Run workflow** 操作。
默认 `dry_run=true`：实际联网校验并计算候选差异，但不会推送或创建同步 PR。
关闭 dry_run 后，仅 main 分支运行可创建 `[ParaTranz] 帝都燃烧校对同步` PR，仍须人工合并。
已有同步 PR 待处理时不重复创建。试点无定时任务，不会自动合并、审核或发布补丁。
安装分支的 push 只触发预检，不能发布同步 PR。

`PARATRANZ_ICB_TOKEN` 保存于仓库 Actions Secret，不写入文件或日志。工作流固定 API
项目编号，所有 ParaTranz 请求均为 GET；拒绝重定向，避免凭据被转发。原文只在 runner
内存中校验，不上传原文快照、调试附件或英文/日文正文。摘要只含计数。
GitHub 仓库默认工作流权限仍为只读；本工作流单独声明 contents/pull-requests 写权限。
发布 PR 需要仓库允许 Actions 创建 PR 的开关；同一平台开关也允许审核，但本脚本不审核。

## 合并规则

`baseline.json` 保存来源哈希、文件/词条 ID、在线状态及两边译文哈希，不包含完整日文。
首次以记载的 Git commit 为比较锚点：在线已审定而 main 未包含的修正生成候选 PR，
不反向用旧 main 覆盖 ParaTranz。之后基线与正文随同一 PR 更新。

- 只改中文目标列；列名、顺序、ID、日文和其他元数据保留。
- 两边同时改成不同译文时，全批停止，不产生部分导入；不能自动选择“最后上传者”。
- 仅 Git 改、在线未改时保留 Git；同样修改不重复改写。
- 未翻译、有疑问、隐藏条目暂缓回填，不改变在线状态。已翻译无需先标为已审核。
- 已确认军衔统一为少校/中校/上校、上尉、上士/中士/下士，不因人工回改而恢复日本军衔。
- 保留现行中文控制符序列；变更控制符需要独立审查，不机械复制日文的全部 `\w`。
  这延续了原中文已有的节奏差异，并不声称全作控制符已重新审核。
- 拒绝新手动换行、空译文、NUL、`<03>`、U+2060 及界面占位符变化。
- 文件增删/改名、词条缺失/重复、ID 或日文哈希变化必须人工更新映射，不自动重建。
- 一次下载前后文件元数据变化则中止重试；PR 合并后到下一次同步的并发修改由基线识别。

本地离线预检可传入私有 `[{file, rows}]` 快照：

```powershell
python -m unittest localization.tests.test_sync_icb_paratranz -v
python -m localization.tools.sync_icb_paratranz --snapshot PRIVATE_SNAPSHOT.json
```

不带 `--apply` 不写文件。即使带该参数，也仅修改本地 checkout，不向平台或 GitHub
发送修改；公开工作流只暂存四份中文表及基线，不使用 `git add .`。

线上机器生成的同步提交包含 `Co-authored-by: Codex <codex@openai.com>`。
若 squash 合并，应在最终提交信息中保留该 trailer。
