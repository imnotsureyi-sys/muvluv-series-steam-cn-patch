# THE DAY AFTER episode:00

[返回 AGE2 游戏](../README.md) · [项目清单](project.toml) · [文本](translations/ja-zh-Hans.csv) · [图片](images/) · [历史补丁](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1)

- Steam App ID：`1407100`
- 目标语言：简体中文（`zh-Hans`）
- 当前玩家包：历史测试版 beta0.1
- 可维护文本：3,713 行
- 历史 Release 图片：70 个 WebP 路径、59 份唯一内容

`translations/ja-zh-Hans.csv` 保存稳定身份、场景、记录类型、日文源字段 SHA-256 与
中文译文，不批量镜像完整官方日文。贡献者需要从自己合法拥有的游戏提取准确 EGPACK，
再由 [`build_changes.py`](../../tools/egpack/build_changes.py) 按哈希连接。

历史玩家包还包含 UI／视频文字、图片和字体，但当前公开源表尚不能逐字节重建该 ZIP；
跨旧分支、公开快照与 Release 的对齐仍在[审计](../../evidence/translations/snapshots/authority-alignment-audit.md)。TDA00 的完整路线反馈少于后续作品，修正时应附日文上下文、
截图和调用场景。

## English summary

The maintained 3,713-row table stores localized text plus stable identity and
Japanese source hashes. The historical beta contains 70 WebP paths, inventoried
under `images/`, but the public source is not yet a byte-identical rebuild of
that release.
