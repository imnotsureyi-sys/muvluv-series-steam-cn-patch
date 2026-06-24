# AstrBot Muv-Luv Feedback Plugin

用于 QQ 群内收集 Muv-Luv 汉化反馈，并基于 TDA00-03 JP/CN ParaTranz CSV 定位章节、key、id、JP 原文和当前 CN。

## 触发方式

- `/反馈`：强制进入反馈流程，可附图或文本。
- `@机器人 + 图片`：自动 OCR 图片并尝试定位；普通未 @ 的图片不会触发。
- `@机器人 + 图片 + 文字`：图片为主，文字只用于聚焦图片中的某一句，例如“停车场对吗”。

## 输出内容

- 章节 / id / CSV 行 / egpack
- JP 原文
- 当前 CN
- 判定：需要修改 / 不需要修改 / 定位不足 / 已处理过
- 建议 CN
- 理由
- 交给哪个章节或是否无需处理

## 数据文件

插件会在 AstrBot 的 `plugin_data/astrbot_plugin_muvluv_feedback` 下维护两个 CSV：

- `feedback_queue.csv`：群友反馈队列，用于后续批量整理。
- `feedback_resolution_table.csv`：已处理反馈记录表。若 key、文件、JP/CN 对上，机器人会返回“已处理过”及具体内容。

翻译判断只基于 JP 原文，不使用英文槽或旧中文兜底。
