# TDA00 新对话上下文

## 当前状态

TDA00 已完成 JP baseline 提取和术语候选确认，可以进入翻译阶段。

当前分支：

`chapter/tda00`

当前 JP 基准：

- `chapters/TDA00/baseline/tda00_jp_text_by_call_order.csv`
- `chapters/TDA00/baseline/tda00_jp_text_by_egpack_id.csv`
- `chapters/TDA00/baseline/tda00_speakers_jp.csv`
- `chapters/TDA00/baseline/tda00_ruby_jp.csv`

当前术语确认表：

- `chapters/TDA00/terms/tda00_all_terms_with_cn_draft.csv`
- `chapters/TDA00/terms/tda00_all_terms_with_cn_draft.md`

## JP baseline 审计结果

- egpack 文件：14
- XML 文件：13
- XML message 标签：3708
- XML text 调用：3713
- JP 文本槽：3713
- speaker：21
- ruby：75
- 被调用但 JP 为空：0
- 未被 XML 调用的 egpack 文本：0
- 重复 ID：0
- 重复 XML 调用：0
- speaker 缺失：0
- ruby 缺失：0
- 英文整句混入 JP：0
- XML / egpack 文件名不匹配：0

结论：TDA00 当前 JP 文本槽、speaker、ruby、调用顺序、来源 egpack 一致，可以作为翻译基线。

## 翻译回写规则

- 只按 `tda00_jp_text_by_call_order.csv` 的游戏实际调用顺序对齐。
- 不使用英文槽兜底。
- 不使用旧中文槽兜底。
- 不使用模糊匹配覆盖不同 ID。
- 不因为 CSV 中 JP 为空就自动清空中文。
- 回写后必须重新跑显示槽审计，再做实机抽查。

## 已确认的重要术语

- `ブラック・ナイヴス` / `ナイヴス`：黑刃
- `ナイヴス１` / `ナイヴス２` / `ナイヴス３`：黑刃1 / 黑刃2 / 黑刃3
- `オール・ナイヴス`：黑刃全机
- `ナイヴス・リード`：黑刃长机
- `ハイヴ`：HIVE
- `オリジナルハイヴ`：原始HIVE
- `JFKハイヴ`：JFK HIVE
- `ビッグ・マム`：Big Mom
- `キング`：国王号
- `リンク`：链路
- `データリンク`：数据链
- `広域データリンク`：广域数据链
- `近接データリンク`：近距离数据链
- `静止衛星リンク`：静止卫星链路
- `戦域データリンク`：战域数据链
- `プランＤ`：D计划
- `モード・オート・スペシャル`：自动特殊模式
- `センパー・ファイ`：永远忠诚
- `セキュリティ・クリアランス`：安全许可
- `バディ`：搭档
- `ドッグタグ`：身份牌
- `メモリアル・デイ`：阵亡将士纪念日
- `ブラディ・ナイトメア`：血色噩梦
- `ビンゴ・フュエル`：返航燃料
- `スーパーホーネット`：超级大黄蜂

完整 368 条见 `chapters/TDA00/terms/tda00_all_terms_with_cn_draft.csv`。

## 下一步

1. 以当前 JP baseline 生成 TDA00 翻译源表。
2. 翻译时优先套用正式术语表。
3. 回写前后分别审计 ID、JP、speaker、ruby、调用顺序、来源 egpack。
4. 打 beta 包后做实机抽查，重点看空白字幕、重复字幕、speaker 与语音是否错位。

