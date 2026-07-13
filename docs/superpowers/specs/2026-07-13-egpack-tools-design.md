# EGPACK 字段级工具设计

## 目标

为 TDA00-03 使用的 AGES EGPACK 多语言表提供可复现、可审计的字段级解包、写回和验证工具，替代通过文本 ID 前后搜索可见字符串的旧启发式脚本。

本项目只改进公共工具、测试和说明文档，不修改 TDA00-03 字幕正文、现有补丁载荷、Release 或章节 CSV。

## 范围

- 解析以 `EPK\0` 开头的 EGPACK 多语言表。
- 识别 `de`、`en`、`es`、`fr`、`id`、`it`、`jp`、`pt`、`pt_br`、`zh_hans`、`zh_hant` 字段。
- 以长表 CSV 导出每个文本 ID 的每个语言槽，包括空槽和纯控制符槽。
- 按 `relative_path + id + slot + expected_text` 精确写回单个语言槽。
- 比较原文件与修改文件，验证只有授权槽和文件头声明长度发生变化。
- 用无版权的合成 EGPACK 测试解析、导出、写回和验证。
- 用本地 TDA00-03 与 ATE 资源进行不入库的兼容性回归。

不在本阶段处理：FPD 解密算法改写、`uistring.epk`、WebP、XML 场景语义映射、正文翻译修订和补丁重新发布。

## 公共目录

```text
tools/
├─ fpd/
│  ├─ diagnose_fpd_keys.py
│  ├─ extract_fpd_filtered.py
│  ├─ probe_fpd.py
│  └─ README.md
└─ egpack/
   ├─ egpack_codec.py
   ├─ extract_egpack_manifest.py
   ├─ repack_egpack.py
   ├─ verify_egpack.py
   ├─ EGPACK_FORMAT.md
   └─ README.md

tests/
└─ egpack/
   ├─ fixtures.py
   ├─ test_codec.py
   ├─ test_manifest.py
   ├─ test_repack.py
   └─ test_verify.py
```

旧的 `extract_egpack_text.py` 和 `repack_egpack_with_csv.py` 在删除前复制到：

```text
C:\Users\Administrator\Documents\MuvLuvSeries_archive_20260623\legacy_tools\egpack_heuristic_20260713\
```

该本地归档不进入 Git。现有 FPD 工具只移动目录并修正引用，不改变算法。

## 二进制模型

EGPACK 文件头必须以 `EPK\0` 开始，偏移 `8..11` 保存小端文件长度。表头声明以下字段，字段键为字段名的 CRC32 小端字节：

| 字段 | CRC32 小端十六进制 |
|---|---|
| `de` | `8b29907d` |
| `en` | `42c159f3` |
| `es` | `9bad5f90` |
| `fr` | `cece75cc` |
| `id` | `506739bf` |
| `it` | `34778ea2` |
| `jp` | `eee0ce8e` |
| `pt` | `2cde8e39` |
| `pt_br` | `a1508d55` |
| `zh_hans` | `629d650e` |
| `zh_hant` | `c1080190` |

字段值由确定的字段标记、NUL 结尾 UTF-8 值和周围未解释二进制组成。解析器只根据字段标记和 NUL 边界读取值，不通过可见字符、引号、日文范围或相邻 ID 猜测文本。

解析器保留每个字段的标记偏移、值偏移、值长度和原始值。遇到缺槽、重复槽、未知记录布局、文件长度不符或非法 UTF-8 时，必须报告文件与偏移并停止，不得用替换字符或模糊恢复继续处理。

## 资源分类

分类同时参考文件名和 ID：

- `scene`：普通 `*_tNNNNN` 文本记录。
- `ruby`：以 `_ruby` 结尾的文本记录。
- `speaker`：`__speakers__.egpack` 或 `*_sNNNNN`。
- `staffroll`：`__staffroll__.egpack`、`*_staffNNNNN` 或 `staff90000`。
- `unknown`：结构有效但不符合已知命名规则的记录；必须保留，不能丢弃。

## 完整长表

清单为 UTF-8 BOM CSV。每个 ID 的每个语言槽各占一行，空槽也输出：

```text
relative_path
egpack
resource_kind
file_size
declared_size
record_index
id
id_offset
slot
slot_crc32
field_offset
value_offset
value_length
value_sha256
is_empty
is_control_only
has_manual_newline
control_codes
text
```

- `text` 保存原始解码文本，不删除或改写 `\p`、`\w`、`\f`、`\n`。
- `control_codes` 按出现顺序记录受支持的反斜杠控制符。
- `is_empty` 只表示值长度为零。
- `is_control_only` 表示去掉控制符和空白后没有可见文本。
- `has_manual_newline` 标记字面 `\n`、`\r` 或真实 CR/LF，供中文换行审计直接筛选。
- `relative_path` 是相对输入根目录的路径，用于避免同名 EGPACK 冲突。
- CSV 中的偏移只用于审计，写回时必须重新解析目标文件。

## 精确写回

写回输入为 UTF-8 BOM CSV：

```text
relative_path,id,slot,expected_text,replacement_text
```

一行即一次明确修改。`replacement_text` 允许为空，因此“存在该行”表示执行替换；不依赖空值表示是否修改。

写回器必须：

1. 重新解析原文件并通过 `relative_path + id + slot` 唯一定位目标。
2. 要求 `expected_text` 与原槽完全一致。
3. 只替换目标值字节并更新偏移 `8..11` 的声明长度。
4. 按文件内偏移逆序应用同一文件的多个修改。
5. 拒绝 `replacement_text` 中的字面 `\n`、`\r` 和真实 CR/LF；中文由引擎自动换行。
6. 拒绝重复修改、未知槽、缺失 ID、期望值不一致和输入/输出路径重合。
7. 始终写入新的输出目录，不原地覆盖输入文件。

## 验证

验证器同时读取原目录、修改目录和变更 CSV。它重新解析两侧文件，并确认：

- 所有授权目标的文本等于 `replacement_text`。
- 所有未授权 ID/槽的文本、字段标记和未解释二进制保持不变。
- 新文件头声明长度等于实际长度。
- ID 集合、记录顺序、槽集合和资源分类没有变化。
- 无操作往返时输出 SHA-256 与输入完全一致。

验证失败时返回非零状态并列出文件、ID、槽、偏移、预期值和实际值。

## 测试与兼容性门槛

测试只使用 Python 标准库 `unittest` 和运行时生成的合成 EGPACK，不提交游戏资源。覆盖：

- 10 个语言槽及空槽完整导出。
- 正文、ruby、speaker、staffroll 和 `staff90000` 分类。
- 普通文本、空文本、`\f`、多个控制符和 UTF-8 中文。
- 手动换行审计，以及中文替换值中的 `\n`、`\r`、CR、LF 拒绝。
- 更长、更短和空字符串替换。
- `expected_text` 不匹配、重复目标、非法 UTF-8 和损坏长度失败。
- 无操作字节完全一致。
- 单槽修改只改变目标值和头部长度。
- 验证器检测未授权 EN 槽变化。

本地 TDA00-03 集成回归必须得到：

| 章节 | scene | ruby | speaker | staffroll |
|---|---:|---:|---:|---:|
| TDA00 | 3713 | 75 | 21 | 229 |
| TDA01 | 8565 | 40 | 82 | 257 |
| TDA02 | 6310 | 17 | 111 | 280 |
| TDA03 | 6913 | 24 | 133 | 232 |

主任保护协会 ATE V2 是已实机可用的参考补丁，也是本地兼容性探测对象。部分成品文件使用引擎可容忍的旧声明长度、附加键、重复字段或重排字段；发现这些差异时必须给出确定诊断，不把未支持表述为补丁错误，也不承诺第一版写回 ATE。

GitHub Actions 在 Windows 和 Linux 上运行合成测试。README 和格式说明全部使用中文，示例只引用合成文件名。

## 发布边界

上传 GitHub 的内容仅包括新工具、测试、中文文档、FPD 目录整理和 CI。不会上传：

- 原版或补丁 EGPACK。
- TDA/ATE 实物测试输出。
- 本地绝对路径。
- 字幕正文、章节 CSV 或 Release 载荷变化。
- 旧启发式脚本的本地归档。

提交时只暂存本设计范围内的明确文件，不使用 `git add -A`。
