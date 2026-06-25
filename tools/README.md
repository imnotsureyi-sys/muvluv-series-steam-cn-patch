# 工具

这里保存可以随补丁仓库公开的可复用工具。

## AGES / egpack / FPD

- `extract_egpack_text.py`：提取 AGES egpack 风格脚本文本。
- `repack_egpack_with_csv.py`：按审核后的 CSV 重建文本载荷。
- `extract_fpd_filtered.py`、`probe_fpd.py`、`diagnose_fpd_keys.py`：检查 FPD/资源容器。
- `font_compat_zh.py`：检查字体的简体中文字符覆盖。

## RIO / CRsa

RIO/CRsa 相关工具放在 `tools/rio/`：

- `extract_native_rio_crsa_text.py`：提取 native RIO/CRsa 文本。
- `extract_native_rio_crsa_text_wide.py`：宽扫描提取，用于漏网文本审计。
- `rio_crypto_probe.py`：探测 RIO/CRsa 解密和 payload 结构。
- `rio_reencrypt_one_line.py`：单行解密/重加密写回验证。
- `rio_apply_batch_slots_v2.py`：批量槽位写回。
- `rio_apply_choice_slots.py`：选择项/特殊槽位写回。
- `make_byte_patch.py`：生成 byte patch 差分补丁。
- `verify_extraction_artifacts.py`：校验提取产物。

这些 RIO 工具来自 photonflowers / photonmelodies 工作流沉淀。使用前需要按本地游戏路径、源表路径和目标章节调整参数或默认路径。

一次性审计脚本、Codex 交接提示词、本地分支脚本、AI 翻译脚本和发布操作笔记只保存在本地，不放入公开 GitHub 树。
