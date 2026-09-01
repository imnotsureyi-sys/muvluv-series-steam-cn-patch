# EGPACK 字段级工具

这里保存 TDA00-03 内层 EGPACK 多语言表的精确提取、写回和验证工具。工具按真实字段键读取 `id`、`jp`、`en` 等语言槽，不在文本 ID 前后猜测可见字符串。

## 文件

- `egpack_codec.py`：严格解析 EGPACK 记录并执行受保护的单槽字节替换。
- `extract_egpack_manifest.py`：导出包含全部语言槽、空槽、控制符和偏移的长表 CSV。
- `build_changes.py`：把公开译文表与用户本机导出的原文清单严格连接，生成写回器所需的五列变更表。
- `repack_egpack.py`：按变更 CSV 写入新的输出目录。
- `verify_egpack.py`：确认输出文件只包含变更 CSV 授权的修改。
- [`EGPACK_FORMAT.md`](EGPACK_FORMAT.md)：已验证的文件结构、字段 CRC32 和兼容性边界。

这些工具只使用 Python 标准库，要求 Python 3.10 或更高版本。

## 1. 导出完整清单

输入可以是单个 `.egpack`，也可以是包含多个 `.egpack` 的目录：

```powershell
python age2/tools/egpack/extract_egpack_manifest.py "X:\input\localized" `
  --output "X:\work\egpack_manifest.csv"
```

清单使用 UTF-8 BOM。每个文本 ID 的每个语言槽各占一行，包括空槽。主要字段包括：

```text
relative_path,resource_kind,record_index,id,slot,slot_crc32,
field_offset,value_offset,value_length,value_sha256,
is_empty,is_control_only,has_manual_newline,control_codes,text
```

`text` 原样保留 `\p`、`\w`、`\f`、`\n` 等控制符。`is_empty` 和 `is_control_only` 用来区分空槽与纯控制符槽，`has_manual_newline` 用于直接筛出字面 `\n`、`\r` 或真实 CR/LF。

## 2. 准备精确变更表

不要手工复制几千行 `expected_text`。先把译文权威表与第 1 步从
正版游戏导出的清单连接：

```powershell
python age2/tools/egpack/build_changes.py `
  age2/games/tda00/translations/ja-zh-Hans.csv `
  --manifest "X:\work\egpack_manifest.csv" `
  --slot jp `
  --output "X:\work\changes.csv"
```

公开表既可以带精确 `jp_text`，也可以只带 `source_text_sha256`；无论
哪种情况，最终 `expected_text` 都来自用户自己的导出，并会在原文或
哈希不一致时停止。说话人、选项等已经是五列格式的白名单可通过重复
`--append` 合并，重复目标同样会停止。

现行 AGE2 正文表另有显式 `record_kind`。`text` 必须同时绑定非空本机
原文和非空译文；`structural_empty` 必须绑定 SHA-256(empty) 且本机源槽、
译文都为空，验证后作为结构 no-op 跳过。不能靠删除这些行保持行号，也
不能把它们伪装成普通的空译文写入。

`build_changes.py` 默认只创建新文件；如果 `--output` 已存在会停止，防止
覆盖已经审核的变更表。确认需要替换生成物时显式传入 `--force`，替换会
通过同目录临时文件原子完成。`--force` 仍不能让输出覆盖译文表、清单或
任何 `--append` 输入。CI 可传 `--check` 只比较现有输出是否与当前输入
重新生成的字节完全一致；`--check` 与 `--force` 不能同时使用。

写回工具只接受下面五列，顺序不能改变：

```csv
relative_path,id,slot,expected_text,replacement_text
scene.egpack,game_t00000,jp,「原文」\p,「中文」\p
```

- `relative_path` 必须与完整清单一致。
- `slot` 必须是明确语言槽，例如 `jp`。
- `expected_text` 必须与当前 EGPACK 完全相同。
- `replacement_text` 默认不能为空；所有 `--append` 表遵守同一门禁。
  `--allow-empty` 只保留给没有 `record_kind` 的显式旧式清空操作；它不能
  绕过现行正文表中 `text` / `structural_empty` 的一致性规则。
- 中文 `replacement_text` 禁止包含字面 `\n`、`\r` 或真实 CR/LF；游戏会按文本框宽度自动换行。
- `\p`、`\w`、`\f` 不属于手动换行。工具不会从原槽自动复制控制符，变更表必须明确写出最终值。
- 不支持模糊匹配、EN 兜底或旧中文兜底。

TDA00-03 当前补丁主要把中文写入 `jp` 槽，但命令行工具不会自动假设目标槽；必须显式传入例如 `--slot jp`。生成的五列表中每一行都会写出该 `slot`。

## 3. 写入新目录

```powershell
python age2/tools/egpack/repack_egpack.py "X:\input\localized" `
  --changes "X:\work\changes.csv" `
  --output-dir "X:\work\repacked"
```

写回器不会覆盖原文件，也不会覆盖已经存在的输出文件。它重新解析目标 EGPACK，通过 `relative_path + id + slot` 定位，并用 `expected_text` 锁定原值。

## 4. 验证输出

```powershell
python age2/tools/egpack/verify_egpack.py "X:\input\localized" "X:\work\repacked" `
  --changes "X:\work\changes.csv"
```

验证器从原文件和变更表重新计算唯一合法的输出，然后进行完整字节比较。任何未经授权的 EN 槽、其他语言槽、ID、字段标记或二进制区域变化都会失败。

## 资源边界

本目录只处理 `.egpack` 多语言表：

- 普通场景正文和旁白。
- `__speakers__.egpack` 说话人名称。
- `*_ruby` 注音记录。
- `__staffroll__.egpack` 片尾职员表。

以下内容不属于本工具：

- 外层 FPD 容器：使用 `age2/tools/fpd/`。
- 动态 UI 字符串 `uistring.epk`。
- WebP 按钮、日期字幕和画面文字。
- XML 场景调用、speaker、voice 和 ruby 关系。
- 字体、安装脚本和补丁发布包。

## 兼容性

- TDA00-03 的标准 11 字段布局是当前正式支持范围。
- 主任保护协会 ATE V2 是已经实机可用的参考补丁。其部分成品 EGPACK 保留旧声明长度，并存在附加键、重复字段或重排字段，说明它采用了引擎能够容忍的另一种写入结果。
- 第一版严格写回只支持已完整验证的 TDA00-03 标准 11 字段布局；ATE 只做只读结构对照，工具不把“当前不支持”解释为补丁无效。
- 在正式支持的 TDA 布局内，结构异常、非法 UTF-8、缺槽、重复槽和文件头长度不符都会立即停止并报告文件与偏移。

## 测试

仓库只包含运行时生成的无版权合成数据：

```powershell
python -m unittest discover -s age2/tests -p "test_*.py" -v
python -m compileall -q age2
```

原版游戏资源、补丁 EGPACK 和本地实物清单不会提交到 GitHub。
