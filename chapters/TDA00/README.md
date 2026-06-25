# TDA00

## 状态

- 分支：`chapter/tda00`
- 当前公开版本：`tda00-beta0.1`
- 发布页：<https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/tda00-beta0.1>
- 源表行数：3,713
- 补丁状态：已发布测试补丁

## 范围

TDA00 对应 `Muv-Luv Unlimited: THE DAY AFTER episode:00`。

beta0.1 补丁包含简体中文剧本文本、UI 相关文本和图片资源、视频/开场字幕资源、中文字体和安装脚本。

## 质量说明

- 使用冻结后的 JP baseline 制作，并检查调用顺序、说话人、ruby 和显示槽。
- 发布审计未发现空中文、Text ID Not Found、顺序错位、控制符损坏或英文整句兜底等硬性问题。
- TDA00 的实机反馈少于 TDA01-03，仍可能存在语义和措辞问题。

## 维护重点

- 收集带截图和上下文的实机反馈。
- 所有修订以 JP 原文为依据。
- 字幕正文修改交给 TDA00 章节工作流处理，不在 `main` 直接改。

## 相关文件

- 补丁源表：`patch-sources/tda00_jp_cn_compare.csv`
