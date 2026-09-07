# Muv-Luv photonmelodies♮

[返回 rUGP 游戏](../README.md) · [项目清单](project.toml) · [文本](translations/) · [图片](images/) · [完整工作流](../../../localization/workflow.md)

- Steam App ID：`889710`
- 目标语言：简体中文（`zh-Hans`）
- 玩家包：尚未发布
- 最新章节编辑表：44,698 条（包含系统文本与补提取消息）
- 历史已审校文本：Adoration + Resurrection 8,407 行、时空碎片 36,176 行，共 44,583 行
- 当前精确运行时绑定表：151 行
- Photon 图片权威：PM 854 项

[按章节命名的 CSV](translations/README.md) 是最新人工编辑入口。
`translations/reviewed/` 保留早期审校中文、稳定 ID 和日文源哈希，作为封存证据，不再人工编辑。
`translations/zh-Hans.csv` 仍是原有 151 行生产绑定契约，包含对象偏移、容量、精确运行时
值、控制符和写入路线。章节 CSV 读取接口不会把审校文本自动变成可安全写回的原生字段。

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

Photon Melodies has 44,698 latest review entries in chapter CSVs, a sealed legacy
44,583-row review dataset, 151 existing runtime contracts and 854 image authorities.
Error 8311 and multi-volume native writing remain distinct from CSV organization.
