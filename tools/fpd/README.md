# FPD 外层资源工具

这里保存 TDA00-03 外层 FPD 资源包的探测、密钥诊断和筛选提取工具。FPD 是资源容器；提取出来的 `.egpack` 多语言表应继续使用 `tools/egpack/` 中的字段级工具处理。

## 文件

- `probe_fpd.py`：探测 FPD 文件头、索引和密钥组合。
- `diagnose_fpd_keys.py`：诊断不同 CRC 与密钥偏移组合。
- `extract_fpd_filtered.py`：按资源路径过滤并提取 FPD 内容。

## 使用边界

- 这些工具需要目标版本对应的 `Scrambler.cs` 和资源包。
- 不要把解出的完整游戏资源提交到 GitHub。
- 不要把 FPD 提取和 EGPACK 文本提取混为同一层操作。
