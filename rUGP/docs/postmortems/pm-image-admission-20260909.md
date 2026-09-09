# PM 图片 hook 已安装但图片功能关闭

PM 原先只有 7 个普通 hook。补入 CRip008 的两个直接解码调用点后，底层安装数
变为 9；production 层仍按 7 验收，把有效初始化当作失败并关闭图片替换。
用户看到菜单和图片 UI 仍为英文，单看底层 hook 成功日志会漏掉这个问题。

本次把 PM 普通表、直接解码调用包装和两个调用点身份一起纳入公开源码，并将
production 准入数同步为 9。调用包装沿用 PF 的 ABI，保留原解码调用与寄存器，
只在受认证的 sidecar 和 surface transaction 条件满足时提交替换。
PF 默认调用点签名字节不变；后续同步安装表后，两款默认构建的身份均已更新。

## 可重复验证

```powershell
python -m rUGP.tools.images.verify_pm_production --zig "X:\zig\zig.exe" --output "X:\checks\pm-production"
```

该 Windows 测试使用合成 host、64 字节身份 token、8×6 自制色块 PNG 和单项
临时 exact 表。它调用实际 selector、production 准入、native 安装、PNG 身份校验
和 surface 提交；不伪造 native 成功状态，不绕过 selector。旧版只回退 PM
production 计数为 7，必须复现 exit 70 / `gate_disabled=1`；当前版本必须成功。
同时检查提交前不改像素、正负 pitch、直接／索引两条事务路径、无效区域不写入。

合成测试只把 hook 写入合成内存并直接调用 prepare/commit；不会执行游戏私有
解码器或通过真实调用栈执行汇编跳板。它能拦住这次准入回归，不能证明每个资源
在实际游戏流程里都已命中。汇编 ABI 和游戏入口兼容仍依赖精确版本审计与实机抽验。

## 发布边界

PM 当前可重复构建身份为
`59B39661218C7B7E01382AEBC6E09718EEF2F52A6F4913852EB9CEFBF804615E`。
同步后的源码和封存表另可用现有 speaker-color candidate 构建选项逐字节复现
实机 PM DLL；具体两种构建身份见 [运行时说明](../../runtime/README.md)。图片文件仍在
Git 之外，Beta0.1 封包器白名单保持不变，不把构建通过当作玩家包发布批准。

## PM RUO 基址修复

同步 `photon_pm_ruo_base_fix.h` 及 proxy 调用：在完整 EXE SHA-256 校验后、
原生归档初始化前，核对 RVA `0x1DE2FE` 的 8 字节指令契约，仅修改其中一个立即数字节，
把 RUO 虚拟起点从与 `.004` 重叠的 6 GiB 移到 8 GiB。不修改磁盘 EXE，不在
DllMain 中执行。已修复状态可重复调用；未知签名和短映像拒绝写入。

公开合成测试另外覆盖保护页设置失败、指令缓存刷新失败、恢复保护失败和回退失败。
成功回退时恢复原字节；若操作系统也拒绝回退，函数仍返回失败，启动 guard 终止初始化，
不能声称失败时一定完全恢复。测试使用独立内存和失败注入，不运行游戏解码器。
