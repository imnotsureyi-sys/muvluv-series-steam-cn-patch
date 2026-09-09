# PM 图片 hook 已安装但图片功能关闭

PM 原先只有 7 个普通 hook。补入 CRip008 的两个直接解码调用点后，底层安装数
变为 9；production 层仍按 7 验收，把有效初始化当作失败并关闭图片替换。
用户看到菜单和图片 UI 仍为英文，单看底层 hook 成功日志会漏掉这个问题。

本次把 PM 普通表、直接解码调用包装和两个调用点身份一起纳入公开源码，并将
production 准入数同步为 9。调用包装沿用 PF 的 ABI，保留原解码调用与寄存器，
只在受认证的 sidecar 和 surface transaction 条件满足时提交替换。
PF 默认调用点签名字节不变；同工具链重建 PF 的规范化 DLL 身份不变。

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
`21EE2D8E9BE693FF59BE37C2AC977ADCB3628228C06BE018B2172C01A5AB071A`。
这是源码构建核对结果，不是最新本机安装包身份。公开 generated 表仍是封存配置；
本地署名图、人工稿和较新的运行时改动没有借这个 hash 自动成为公开发行内容。
Beta0.1 封包器的身份白名单保持不变，会拒绝未经它单独批准的新 DLL。
