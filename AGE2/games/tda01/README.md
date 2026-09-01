# THE DAY AFTER episode:01

[返回 AGE2 游戏](../README.md) · [项目清单](project.toml) · [文本](translations/ja-zh-Hans.csv) · [图片](images/) · [历史补丁](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda01-beta0.2.2)

- Steam App ID：`1407090`
- 目标语言：简体中文（`zh-Hans`）
- 当前玩家包：历史测试版 beta0.2.2
- 可维护文本：8,565 行
- 历史 Release 图片：93 个 WebP 路径、71 份唯一内容

当前文本表保存资源 ID、EGPACK、场景、说话人、源哈希、记录类型和中文译文。完整日文
来自贡献者自己的合法提取，通过 [`build_changes.py`](../../tools/egpack/build_changes.py)
连接；生成的 EGPACK 不是维护权威。

beta0.2 曾产生 603 个不可见正文槽，之后修正为 beta0.2.2。这段经验说明结构为空不等于
漏译，正文显示、说话人、ruby、XML 调用、控制符和语言槽都必须分别验证。历史 Release
与当前可维护表的逐字节对齐仍在进行。

## English summary

TDA01 keeps an 8,565-row portable table and a deterministic inventory of the
93 WebP paths found in beta0.2.2. Join source hashes to a legal extraction;
never treat structural empty slots as missing translations by count alone.
