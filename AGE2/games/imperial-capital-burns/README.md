# The Imperial Capital Burns／帝都燃烧篇

[返回 AGE2 游戏](../README.md) · [项目清单](project.toml) · [正文与 UI](translations/) · [术语](terminology/ja-zh-Hans.csv) · [图片](images/) · [历史补丁](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/imperial-capital-burns-beta0.1)

- Steam App ID：`2630300`
- 容器：FPD v2 `obb/pack.bin`
- 补丁路线：LocalAppData 松散覆盖，不修改原始 `pack.bin`、EXE 或存档
- 当前玩家包：历史测试版 beta0.1
- 历史 Release 图片：315 个 WebP 路径、232 份唯一内容

## 可维护汉化源

- [`translations/main.ja-zh-Hans.csv`](translations/main.ja-zh-Hans.csv)：5,564 行正文，
  保存稳定身份、源哈希和中文译文，不批量镜像完整官方文本。
- [`translations/speakers.ja-zh-Hans.csv`](translations/speakers.ja-zh-Hans.csv)、
  [`choices.ja-zh-Hans.csv`](translations/choices.ja-zh-Hans.csv) 与
  [`ui-strings.ja-zh-Hans.tsv`](translations/ui-strings.ja-zh-Hans.tsv)：说话人、选项和系统
  UI 权威。
- [`terminology/ja-zh-Hans.csv`](terminology/ja-zh-Hans.csv)：本作专用术语。
- [`images/copy/`](images/copy/)：启动提示、常用 UI、角色名、telop、日期/地点卡的中文
  文案、排版和源图锁。
- [`images/release-inventory.json`](images/release-inventory.json)：历史 beta0.1 中 315 个
  WebP 成员的尺寸、模式和 SHA-256。
- [`evidence/initial-inventory.md`](evidence/initial-inventory.md)：最初格式盘点与实现边界。
- [`releases/beta0.1.md`](releases/beta0.1.md)：该历史版本的范围与安装说明。

译文以日文文本和语音为依据，不以英语槽或模糊匹配兜底。历史范围包括正文、说话人、
选项、系统 UI、图片文字、37 张角色名卡、74 张 telop、61 张日期/地点卡及中文字体路径。

## 构建边界

[`tools/build_phase1.py`](tools/build_phase1.py) 是本作“非正文阶段”的松散覆盖构建器，
负责 UI 字符串、图片、字体、telop 和事件卡。它目前不会消费 5,564 行正文表，也不会
生成正文/说话人 EGPACK；因此不能声称公开仓库已经可以逐字节重建历史 beta0.1。

构建器要求调用者提供：

- 从准确合法版本提取的 GUI 与 `data_spec` 资源；
- 已解密的 UI 字符串输入；
- 经哈希锁定、允许再分发的字体及其许可证；
- 日文脚本、telop 与事件卡几何参考；
- 单独取得并审查的 FSNr 加密工具。

输出写入全新的 staging 目录，并生成 payload manifest、带哈希门的安装器和按清单卸载器；
它不会重写源 FPD。`--font-license` 必须提供非空 UTF-8 许可证，且许可证会与字体一起
进入载荷并写入 manifest。

从仓库根目录调用：

```powershell
python AGE2/games/imperial-capital-burns/tools/build_phase1.py `
  --repo . `
  --gui-root "X:\input\imperial\root\assets\data\gui\textures" `
  --data-spec-gui-root "X:\input\imperial\root\assets\data_spec\gui\textures" `
  --uistring-dec "X:\input\imperial\uistring.epk_dec" `
  --tda-font-root "X:\input\fonts\source-han-sans-sc" `
  --font-license "X:\input\fonts\SourceHanSansSC-LICENSE.txt" `
  --tda-boot-root "X:\input\approved-tda-boot-notices" `
  --fsnr-main "X:\tools\FSNr\main.exe" `
  --jp-script-root "X:\input\imperial\root\assets\data_spec\adv\game\scr" `
  --telop-reference-root "X:\input\imperial\root\assets\data_spec\adv\game\chr\00no_text_telop" `
  --location-date-card-root "X:\input\imperial\root\assets\data_spec\adv\game\bg\30イベント絵\010_TEイベント絵\050_帝都燃ゆ\140_テロップ" `
  --output "X:\build\imperial-phase1"
```

这些 `X:\...` 均是调用者自己的输入示例，不会从仓库下载。共享 EGPACK 工具未来可以
承担正文阶段，但帝都的具体布局还必须单独冻结和测试，不能因为 TDA00–03 已支持就直接
宣布兼容。

## English summary

Imperial Capital Burns keeps dialogue/UI/terminology sources, editable image
copy, a 315-WebP historical release inventory, and a hash-gated non-story
loose-overlay builder. A legal extraction and redistributable font inputs are
required; the public repository is not yet a byte-identical full rebuild of
the historical beta.
