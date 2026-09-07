# PF / PM 章节 CSV 维护

## 唯一人工编辑入口

- [PF：13,025 条，13 份 CSV](../games/photonflowers/translations/README.md)
- [PM：44,698 条，45 份 CSV](../games/photonmelodies/translations/README.md)

这次从 2026-09-06 最新合并审计重组 **57,723 条**，不是拆分旧译文。
正文、姓名、标点、空格、现有换行及其他控制字符均不改动。
265 项原始注释的已有归并结果保持原样，附属中文注释随正文绑定保存。
公开表只含中文及日英源文哈希，完整官方日英槽仍留在本地三语审计中。

`chapters.json` 显式列出每份 CSV 的条数、RIO 和 CRsa 块，不凭文件邻近关系推断归属。
PF 使用现有章节菜单及各故事开头、续接人物和情境分组。PM 从历史长短篇数据集划分，
再将清十郎的《憧憬》和西尔维奥的《再诞》分开。穿插简报仍属于其原故事。
《时空的欠片》按 42 个原生脚本块分开，场景内分支不被任意拆断。
同一脚本块的选项和补提取文字随正文一起保存。全局章节菜单不重复放入每个篇章。

## 列与控制符

| 列 | 用途 |
| --- | --- |
| `binding_id` | 唯一原生绑定，不可重编号；历史 `stable_id` 不是唯一键 |
| `kind` | `cvm` 正文、`recovered_message` 补提取消息、`cstring` 选择或系统显示文本 |
| `translated_text` | 中文编辑列，控制字符以可逆的 `<HEX>` 形式显示 |
| `cn_annotations` | 随该行绑定的中文注释 JSON 字符串数组；空数组 `[]` 表示无注释 |
| `review_scope` | 继承原审计范围；空值表示原记录没有该字段，不伪造已审状态 |
| `jp_utf8_sha256` / `en_utf8_sha256` | 原始槽按 UTF-8 编码的精确哈希；空值表示原槽不存在 |

`<0A>` 表示实际换行，`<01>`、`<05>` 等保留原值，不在这次整理中重解释其功能。
已有正文不含 `<03>`，姓名内不加入 `<2060>`。正文其他位置已有的 `<2060>` 不擅自删除。
为防止字面文本与转义混淆，真正的小于号编码为 `<3C>`：
字面字符串 `<0A>` 在 CSV 内写作 `<3C>0A>`，读取只解码一次。
原反斜杠前缀如 `\A` 保持原样。不要用 Excel 自动转换绑定列、哈希或控制符。

## 读取和核验

从仓库根目录运行：

```powershell
python -m rUGP.tools.text.chapter_review rUGP/games/photonflowers/translations --unchanged
python -m rUGP.tools.text.chapter_review rUGP/games/photonmelodies/translations --unchanged
```

`--unchanged` 专门验证本次迁移：CSV 解码后每条记录和全部原生元数据都必须与封存快照相同。
后续授权修改正文时，不加该开关可检查列结构、全部绑定、章节归属、只读元数据和禁用控制符。
`read_chapters()` 以唯一绑定合入编辑后的正文、注释，按封存快照顺序返回完整记录，
其余原生偏移、历史身份、来源、修复记录均不丢失。不根据 CSV 行号生成写回索引。

## 历史文件与构建边界

- `../text-data/history/reviewed/`：封存的早期正文证据，不再人工编辑。
- `../text-data/layout-baseline/`：不可变基线和完整绑定元数据，不维护第二套新正文。
- `../text-data/runtime/zh-Hans.csv`：旧运行时精确写入合同，**不是新的正文编辑入口**。
- `../text-data/increments/`：原生补提取、注释和姓名修复的机器证据。

旧资料仅迁移位置，内容与哈希不变；新编辑只进入章节 CSV。原生构建接入时必须读取 `read_chapters()`
的有效结果并走已有原生写入合同，不能回退使用旧正文。
**本 PR 只完成编辑面重组和读取接口，不宣称章节 CSV 已直接接入玩家包构建。**
尤其 `cstring` 是可读显示文本，不等于含多个语言槽、PUA 与字段边界的完整序列化字段。
不能把可读 CSV 整行替代原生 CString 字段，也不能从源文哈希反造日英原文。

这次初始 CSV 经表格工具按文本类型写入、逐格读取核验后导出；完整 Python 往返校验
独立证明全部 57,723 条与基线相同。目录重组没有安装游戏文件，也没有修改玩家存档。

## 本地完整三语审核

公开仓库保留中文、唯一绑定及日英哈希，不发布完整官方日英脚本。
本地三语表是审核视图，不是第二份中文权威来源。日英列只读，中文及注释可编辑。
输出只能位于当前仓库已忽略的 `local-internal/` 子目录，不进入提交、Release 或 CI 附件。
版权声明与非商业用途不等于获得脚本分发许可；参见[内容权利说明](../../docs/legal/NOTICE.md)。

使用现有的本地合并审计 `full-three-language.jsonl` 作为输入；它应来自合法持有的对应游戏版本。
本命令不下载脚本，也不直接重新解析游戏安装目录。没有该私有输入时，应先走已有提取、
绑定和合并审计流程，不能从哈希反造原文或拿其他版本顶替。
导出逐条核对绑定、类型及精确日英哈希，中文始终读取当前公开章节表，忽略私有输入里的旧中文。

```powershell
python -m rUGP.tools.text.local_chapter_review export rUGP/games/photonflowers/translations local-internal/three-language/session-01/PF --source work/full-three-language.jsonl
python -m rUGP.tools.text.local_chapter_review export rUGP/games/photonmelodies/translations local-internal/three-language/session-01/PM --source work/full-three-language.jsonl
```

生成与公开目录一一对应的 58 份 CSV，`jp_text`、`en_text`、`translated_text` 并列。
所有源文控制符可逆显示，包括日英原有 `<03>`，不套用中文禁用规则。
源槽不存在时留空且哈希为空；真实空字符串的哈希不为空，不混淆二者。
已有会话不覆盖，需要更新原文或同步较新中文时换一个会话目录。

审核后先预检，确认修改条数，再显式回写：

```powershell
python -m rUGP.tools.text.local_chapter_review import rUGP/games/photonflowers/translations local-internal/three-language/session-01/PF
python -m rUGP.tools.text.local_chapter_review import rUGP/games/photonflowers/translations local-internal/three-language/session-01/PF --apply
```

PM 对应更换目录。回写仅更新中文与注释；按唯一 ID 对齐，允许同章排序，拒绝跨章移动、
漏行、重复行、日英改动、只读元数据改动和不合规控制符。所有章节先校验通过才写入。
`base_edit_sha256` 用于拒绝旧审核覆盖较新的公开中文，请勿修改。
无改动导入不重写文件；重复导入相同结果也不产生新改动。
