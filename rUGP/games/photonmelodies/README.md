# Muv-Luv photonmelodies♮

[返回 rUGP 游戏](../README.md) · [项目清单](project.toml) · [文本](translations/) · [图片](images/) · [完整工作流](../../../localization/workflow.md)

- Steam App ID：`889710`
- 目标语言：简体中文（`zh-Hans`）
- 玩家包：尚未发布
- 已审校文本：Adoration + Resurrection 8,407 行、时空碎片 36,176 行，共 44,583 行
- 当前精确运行时绑定表：151 行
- Photon 图片权威：PM 854 项

`translations/reviewed/` 保存完整审校中文、稳定 ID 和日文源哈希；
`translations/zh-Hans.csv` 是 151 行生产绑定契约，额外包含对象偏移、容量、精确运行时
值、控制符和写入路线。完整 44,583 行仍需继续从合法提取绑定，不能把“译完”与“已经
能安全写入游戏”混为一谈。

PM 的 CRsa 路线暴露了 AGES Internal Error 8311：带长度的 CString 内混入 `U+0000`
会被运行时拒绝，即使静态结构和校验和都正确。根因与修复保存在
[8311 复盘](../../docs/postmortems/error-8311.md)。图片使用 PF/PM 共用清单，但 PM 的
多个 RIO 分卷、shared/common 端点与运行时表面替换必须单独验证。

本轮原生 CRsa 补译还确认了另一条独立边界：后续分卷中的记录即使做内容完全相同的
RUO 重定向，实机仍会触发 `InternalError(831)`；相同字节写回原分卷的固定范围则通过。
因此 PM 原生 CRsa 不再由 RUO 构建器输出，而由
[`build_crsa_native_volume_patch.py`](../../tools/text/build_crsa_native_volume_patch.py)
从哈希锁定的干净原卷生成新分卷副本，发布时再转换为支持安装和回滚的区段补丁。
完整实验、实机抽样和 831／8311 的区别见
[CRsa 原生增量记录](../../docs/postmortems/crsa-native-increment-20260904.md)。

当前组件还不是玩家安装包。正式发布需要 PM 自己的干净根构建、哈希门、字体与图片
权利核验、安装/卸载以及完整路线实机 QA。

## English summary

Photon Melodies exposes 44,583 reviewed rows, 151 currently runtime-bound rows
and 854 image authorities. Error 8311, multi-volume CRsa binding and image
routes remain explicit production gates rather than hidden release folklore.
