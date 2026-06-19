# TDA00 更新记录

## JP baseline

- 从游戏实际 `egpack` / XML 调用重新提取 JP 文本。
- 固定 `game_t` 调用顺序、speaker、ruby、来源 egpack。
- 完成 JP 槽完整性审计：被调用但 JP 为空 0、重复 ID 0、重复 XML 调用 0。
- 提取并确认 368 条 TDA00 专有名词 / 术语候选。
- 将确认术语同步到正式术语表。

