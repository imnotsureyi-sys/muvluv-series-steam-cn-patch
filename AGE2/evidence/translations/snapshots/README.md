# AGE2 可移植翻译快照

这里的五份 JSON 把公开简体中文表绑定到产生它们的私有含原文快照。Git 中的表保留
资源身份、有限场景/说话人上下文、每个日文字段 SHA-256、中文译文和审核元数据，但不
批量镜像完整官方剧本。

从合法安装提取后，使用 `AGE2/tools/egpack/extract_egpack_manifest.py` 和
`AGE2/tools/egpack/build_changes.py` 将公开译文连接到准确本地原文；源哈希不符即停止。

这些快照不是“当前表与所有历史 Release 逐字节相同”的声明。旧分支、公开快照和发布后
修正之间存在差异，必须按稳定 ID 对下载的 Release 载荷逐作解决。具体见
[`authority-alignment-audit.md`](authority-alignment-audit.md)。

## English summary

These records bind five portable Chinese tables to sealed source-bearing
exports without mirroring the complete official script. Historical Release
alignment remains a separate per-game audit.
