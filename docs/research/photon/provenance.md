# PF／PM 汉化技术来源与贡献分类

[总览](README.md) · [技术来源分类](provenance.md) · [完整蓝图](blueprint.md) · [证据索引](evidence-index.md)

日期：2026-09-12。范围：Steam photonflowers／photonmelodies 的技术、字体、中文内容与发布链；不把 AGE2／FPD 工作混进来。

> **技术路线补充核查：** 最终 PF r3／PM r4 的实际运输分工已在[完整技术蓝图与路线演变](blueprint.md)逐项核实。下文“PF 累计 RUO／PM 原分卷”的文本分工属于历史阶段；最终组装把两作 164 个正文显示 CRsa 固定范围写入 RIO，最终 RUO 仅保留 PF 20 个 CRmt＋1 个 Cr6Ti、PM 30 个 CRmt。不要将中间阶段说明直接当正式包结构。

本次核查补齐了 RioX 的具体版本及反汇编参考、alterdec 的实际副本、Cr6Ti 的早期实现错误、CRip007 的原生预测适配，以及 PhotonCN 的精确基础字体。旧说明中“RioX 仅作术语参考、版本不明”等表述，以此处的版本、用途和证据为准。

本项目的准确定位是：**移植及参考既有 rUGP 研究，在此基础上完成 Steam PF／PM 的目标版本解析、中文写入、图片和演出素材处理、字体与运行时适配、安装发布及故障修复。** 既不能说全是从零破解，也不能简化成现成英化工具换一份中文。

“本项目实现”包括维护者主导、Codex 辅助编写和研究的工作，不等于全部由维护者手敲，不等于发明官方格式，也不证明全球首创。下文分别判断算法知识来源、具体实现、中文内容、发布应用和验证范围。

## 1. 本次查了哪里，结论能证明到哪一步

### 对代码贡献先作三分，避免把“研究官方程序”与“参考前人工具”混在一起

这里按具体组件分类，不按整个游戏／整套格式一刀切。同一来源链可以同时包含前人提供的算法知识和本项目后来新增的功能。

| 分类 | 判定标准 | 已确认组件 |
| --- | --- | --- |
| **直接移植／复用**（用户所说的“照搬”） | 有明确前人源码移植或现成内容复用证据；移植后仍可有自己的适配 | GARbro ArcRIO.cs → Python 目录读取器。基础 Noto 字形、官图复用属于内容复用，应另记，不与代码原创混算。 |
| **参考前人具体实现后完成** | 前人代码或程序直接提供该组件的算法／状态规则，我们重实现、扩展或适配 | Cr6Ti → AFHook／AFEditor／alterdec；CRip007 → GARbro 加原生适配；CRmti → alterdec／rugptools 的预测基础与 RioX 反汇编；ICI／RIO 加密地址算法 → GARbro。 |
| **本项目研究并完成实现** | 核心工作由本项目分析官方样本／原生程序、编写并验证，未发现移植前人该组件实现的证据 | **CRip008 解码器及 kind2／kind3 编码器**；PF／PM 专用 CRsa 文本字段解析与写回；CRmt 父对象／属性及中文资源绑定适配；版本专用修复、安装器与打包实现。Hook 的具体运行时代码属于本项目实现，但其技术先例另行注明 AFHook。 |

**CRip008 应归第三类。** 现有代码与研究记录指向：本项目分析官方头部、原生解码器的 MSB 位流、4096 项整数表、预测及 Alpha 规则，完成解码与 kind2／kind3 逆向编码、回读和游戏路线验证。GARbro／AFHook 提供过外围 rUGP 知识，不能因此把 CRip008 本身降格为“移植它们的现成编解码器”。“独立研究并实现 CRip008 编解码”是合适表述；“发明 CRip008 格式”或“支持所有理论变体”不是。

以下检索与证据范围仍适用：

- 主目录 `local-record/Muv-LuvSeries汉化`：使用包含隐藏、忽略目录的检索，追查 tools、outputs、local-internal、patch-sources、旧审核报告和构建清单。技术关键词检索命中 17,779 个文件；这是检索覆盖量，**不是声称逐字阅读了 17,779 个文件**。
- 旧工作树 `0713`、`3016`、`bf82`：按主目录记录的真实路径追查字库构建、CRmt 研究、DLL 源码和历史会话。当前工作树 `0e0c` 用来对照现行公开代码。
- `local-record/Codex-Safe-Workspace`：核对当时保存的上游 Git 副本、源码哈希和修改过的研究版 GARbro。
- GitHub：获取本仓库现存 23 个分支的完整目录树、28 个 Issue／PR、13 个 Release、4 条 Issue 评论及 0 条行级 review 评论，检查相关正文和技术提交。分支树均未截断；没有声称逐行审查所有分支的所有文件。
- GitHub main 为 `1972bd9c0e792087842e805e9a90e626e79a118d`，当前工作树为 `6caab1176bc50350d39555374bd15015363b5f4b`；远端比较没有文件差异。主目录本身的 Git HEAD 较旧，不能只读它的现行追踪文件。
- 本次重新计算 RioX 机器码区段哈希、基础字体和历史构建文件哈希；另对真实 PF CRip007 记录进行了离线旧／新解码器对比。其余全量游戏验证数字明确标为历史报告结果。

原始证据与脚本保存在本地核查目录；公开摘要与未公开记录的界限见[证据索引](evidence-index.md)。核查过程没有启动游戏、改 Steam 文件或重打包。源码比对、静态回读、历史实机通过、最终包来源是不同层次的证据。

## 2. 前人来源与我们实际参考的版本

| 来源 | 本机保存的确切版本 | 实际作用及边界 |
| --- | --- | --- |
| GARbro／morkt | `b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0` | `ArcFormats/rUGP/ArcRIO.cs` 是目录读取器的明确移植来源；同文件的 ICI／RIO 加密、偏移与长度算法是对照来源；`ImageRIP.cs` 是 CRip007 解码参考。不是现成 PF／PM 完整汉化重封器。 |
| AFHook／AFEditor／eplightning | `3f613a097c07d3d9fb9969a130ea6d859b544f8a` | `CImageWriter.cpp`、`CR6Ti.cs` 的 Cr6Ti 状态机及编码行为；`CGameFunctions.cpp`、`CHookEngine.cpp` 的文本、人物名颜色、图片和 Windows 界面 Hook 先例。AFEditor 已经有编码功能，不能写成前人只会解码。 |
| alterdec：本项目实际使用的 chinesize 副本 | remote 保存为 `https://github.com/tsudoko/chinesize.git`，提交 `ad5bdad900e31edf2a17640d1d243470a58b29a8`；GitHub 当前重定向至 `tsdko/chinesize` | 历史审核明确绑定 `Rugp/alterdec/src2/r6ti.cpp`。这是我们实际参考副本的版本，不冒充 alterdec 原作者最初发布版本。上游沿革还包括 regomne/chinesize、hiko_bae 的工作。 |
| rugptools／osmium76 | `3ff587416e41eeeee7122fb122c90f7a36c409dd` | rUGP 对象与 alterdec 行为研究；早期 CRmti 探索明确借用 alterdec／rugptools 的 Cr6Ti 预测规则。其 README 自述包含从 hiko_bae alterdec 转录的代码，故不能把这条知识链截断成我们的发现。没有证据表明整套库被编进玩家补丁。 |
| **RioX／muzhi** | **1.2.143.810，随包 readme 更新日期 2013-10-08** | CRmti 位流、整数、行范围、透明段与颜色预测的重要反汇编参考；作用远多于“术语与先例”。它是研究参照程序，玩家安装和现行构建不需要执行 RioX。 |
| Noto Sans SC | 本机原始 `NotoSansSC-VF.ttf`；字体内版本 **`Version 2.04;241114210130;non-release`** | PhotonCN／PhotonR2 基础字形来源。我们做静态化、子集、度量、家族名及引擎专用改造，没有自行设计整套中文字形。 |

固定版本源码：[GARbro ArcRIO.cs](https://github.com/morkt/GARbro/blob/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0/ArcFormats/rUGP/ArcRIO.cs)、[GARbro ImageRIP.cs](https://github.com/morkt/GARbro/blob/b09ee4570ccb1daf6ac56710ee8934dc0b8baeb0/ArcFormats/rUGP/ImageRIP.cs)、[AFEditor CR6Ti.cs](https://github.com/eplightning/afhook/blob/3f613a097c07d3d9fb9969a130ea6d859b544f8a/editor/AFEditor/CR6Ti.cs)、[AFHook CImageWriter.cpp](https://github.com/eplightning/afhook/blob/3f613a097c07d3d9fb9969a130ea6d859b544f8a/plugin/afhook/CImageWriter.cpp)、[本次确定的 alterdec 副本](https://github.com/tsdko/chinesize/blob/ad5bdad900e31edf2a17640d1d243470a58b29a8/Rugp/alterdec/src2/r6ti.cpp)、[rugptools](https://github.com/osmium76/rugptools/tree/3ff587416e41eeeee7122fb122c90f7a36c409dd)。

关键源文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| GARbro 原始 ArcRIO.cs | `DEF71FDDD334C6DC2BD03671600A3F4C3987355CE9C2E579C32EF1F73FDB4AB5` |
| AFHook CImageWriter.cpp | `338125E5AA4C804FD490485CCAECFAD20D1348FDC665CC5F7AD768B7FB01CD34` |
| AFEditor CR6Ti.cs | `BBDB1E77066BA5FD8DD1794A2275F24D98D12E041DE1DE7D150536F94A791F73` |
| 实际参考的 alterdec r6ti.cpp | `DA8DB38D82925952F703C810A0B33D2E313DC4903C42DE6CD62109CA73D11F3E` |

主目录报告中的引用路径、旧副本内容、Git commit 与源码哈希能够相互对应。这比“现在下载最新版，上面碰巧也有类似代码”更能说明实际来源。

## 3. Cr6Ti：确实有偏色问题，但不能说是照抄上游导致

### 来源和本项目贡献

Cr6Ti 的已知状态机来自 AFHook C++、AFEditor C# 与 alterdec C++。本项目在此基础上编写 Python 编码器、严格解码器、分离的回读实现，并适配 PF／PM 的记录封装、容量、资源身份和安装路径。

用户记得的“之前颜色不对”有明确记录。但这组证据表明：**三套上游实现对关键规则是一致的，我们早期的实现没有正确遵循这些规则。** 不应写成“前人方案有色差，我们把前人的 bug 修好了”。

| 具体问题 | 正确行为／前人已有行为 | 我们早期的错误与后续工作 |
| --- | --- | --- |
| kind3 透明像素 | Alpha 为零时清空上一行该位置 RGB 缓存 | v1 保留旧 RGB；后续预测读到脏值，造成像素偏差。修正缓存维护。 |
| 红、蓝通道增量 | 共享增量与残差相加后，最后统一 clamp 一次 | v1 中间先 clamp 再叠加，相当于两次裁限，极值附近颜色不同。改成最后裁限。 |
| kind2 负奇数预测 | C／C# 整数除法向零截断 | Python `//` 向负无穷取整，`-3/2` 会由期望的 `-1` 变成 `-2`。显式匹配原生语义。 |
| 上一行复制指令 | 是合法、且官方大量使用的 opcode | 不能把错误归咎于复制指令本身；错误是相关缓存状态。后续实现正确支持，而非声称必须禁用它。 |
| 记录边界 | 44 字节头＋payload＋两个零尾字节；外部放置对齐不是记录内容 | 纠正我们对 extent／尾部／对齐的混用，避免多算少算一字节。 |

历史全量报告记录：1,475 个官方样本采用参考语义时全部匹配 canonical RGBA；v1 仅 354 个匹配。另一次代表性回读中，旧模型与原生兼容模型有 10／11 个替换样本不一致。**这些是本次重新读取的历史审核结果，没有在本次重新跑完 1,475 张。**

这也解释了为什么“自己编码、再用自己写的错误解码器解回来一致”不足以证明正确：双方可能共享同一处错误。

### 不能把其他失败混进偏色原因

当时两种粗粒度实机 A／B 包都失败：PM 报 8311，PF 仍是英文 Page／Return。因此历史报告明确没有把偏色 bug 单独认定为这两种运行失败的根因；资源键、模板、父记录及尾部绑定另需排查。

还有一种“颜色／精度损失”属于编码容量选择：PM VoiceSkip 某次试验从 6,040 字节压到 3,484 字节以适配 3,488 字节容量，使用了官方调色板／Alpha 条件。那是有损、未批准候选，不能把试验结果写成最终采用方案。后来正式方案还包括原生记录路线和 PNG 运行时替换路线，不能把所有制作侧编码试验都等同于玩家包。

主要证据：[原始 Cr6Ti 兼容性结论（本地记录 L15）](evidence-index.md#l15)、[官方样本 census（本地记录 L16）](evidence-index.md#l16)、[当前编码器](../../../rUGP/formats/images/cr6ti_encode.py)。

## 4. CRip007：GARbro 参考、原生像素适配与早期移植错误要分开

### 我们用了什么

GARbro 固定提交的 `ImageRIP.cs` 提供通道位数、位流、预测和无 Alpha Bgr32 分支的已有解码知识。本项目早期 `tools/rio/photon_r6ti_extract.py` 的 `decode_rip007_rgb` 明确标注该来源，随后维护严格解码器与灰度字图编码器。

但早期 Python 代码**不是原封不动执行 GARbro C#**。其符号位读取顺序、预测开关等还存在自身偏离。不能把 Python 旧版表现全部说成 GARbro 的行为。

| 具体点 | 发现与改动 | 归属 |
| --- | --- | --- |
| 原生像素高字节 | AGES7 的无 Alpha 像素用 `0x80` 表示完全不透明，原生黑色为 `0x80000000`；导出 PNG 要映射成 Alpha 255 | 对官方目标游戏行为的核实与输出适配；不是把 PNG 的 128 当成正确半透明 |
| 上一行预测读取 | 先 `packed_above & 0x00FFFFFF`，再判断 RGB 是否为零并处理 RGB 基线；高字节不能参与颜色预测 | 旧代码把整颗 32 位像素混进去，会污染后续行；修正版注释给出 PF 原生位置 `0x005EC8F7` |
| 数值运算 | 匹配 uint32 溢出／回绕语义 | Python 移植必须显式适配 |
| 符号位读取 | 符号位在 GetInt 前读取 | 上游已有正确顺序；旧项目移植存在偏差，不能列为我们首次发现的格式规则 |
| 是否应用预测 | 根据 `CompressInfo[3]`／pred_flag 决定 | 上游已有条件分支，旧代码无条件预测是项目移植问题 |
| 灰度抗锯齿精度 | 原始 6／6／6 位不足以精确保留中文候选的 256 个灰度级；审核后的灰度编码改为 8／8／8 | 本项目针对文字图片的编码扩展；不代表支持所有理论 flag 组合 |
| 封装 | 40 字节头＋指定长度 payload，没有 trailer | 按实际样本实现，不能套 Cr6Ti 的两字节尾部 |

### 本次重新做的可复查实验

从本机 PF RIO 只读取得一条原始记录，偏移 `0x1AD8246C`、长度 57,846 字节。先检查源记录哈希，再分别运行本项目旧、新解码器：

- 原图 800×600，q=3、pred_flag=1、通道 6／6／6。
- 源记录 SHA-256：`96C70B17D7A01F8335C42255E651AEBBA8A47C6D6A429B88E53FB5E745D8CFA1`。
- 480,000 个像素中，**255,533 个 RGB 不同**，首个差异行索引为 75，最大单通道差为 255。
- 修正版 RGBA SHA-256：`B97ADD760ED8F0092E139267C1B332365C01AD20E7DD9DF84ABAC03956934AA2`，与历史 canonical 完全一致。

这是对**我们历史移植与现行修正版**的真实原始样本重放；没有执行上游 C#，没有重新进游戏，也不能由这一个样本推导所有 CRip007 变体都无误。历史编码审核另记录 4 个目标的独立回读零像素差。

证据：[本次重放结果](evidence/crip007-readonly-replay.json)、[重放脚本（本地记录 L17）](evidence-index.md#l17)、[现行解码器](../../../rUGP/formats/images/crip007_decode.py)、[历史编码审核（本地记录 L18）](evidence-index.md#l18)。

## 5. RioX：版本和具体参考内容已经查实

### 精确程序身份

保存位置：`local-record/local-internal/third-party-readonly/RioX-1.2.143.810/`。

| 项目 | 核查结果 |
| --- | --- |
| 软件、作者、版本、日期 | 随包 readme 标为 age Game Graphic/Text Extractor RioX；muzhi；1.2.143.810；2013-10-08 |
| 原压缩包 | `riox.zip`，1,141,812 字节 |
| 原压缩包 SHA-256 | `08C1C1AFAEB453623E0BD410ED32588140D5CBA7DC4769440D15B61F0A61F973` |
| 实际研究程序 | `static/RioX.exe` |
| 程序 SHA-256 | `B19FB4D4A43BF79C158F7AB251FA48135CA1E2ADA44686A6D8A6E8E32403F78F` |
| 版本证据边界 | 版本来自随包 readme 与保存目录；EXE 没有可用的版本资源值。没有找到当时原始下载 URL／Zone.Identifier，不能捏造下载渠道。 |

### 到底参考了哪些技术

| RioX 位置／规则 | 本项目对应证据 | 实际用途 |
| --- | --- | --- |
| `0x41D1E8` 的宽有符号编码 | 主目录 `probe_crmt.py::read_signed_wide`、`build_custom_crmt.py::write_signed_wide` 的直接注释 | 确认 CRmti 行范围等字段使用的宽整数编码；随后实现其反向写入，不能拿 Cr6Ti 短编码的 ±127 范围替代 |
| `0x41D12B` 的短编码差异 | 3016 工作树 `probe_generalized_codec.py`；现行 `crmti_decode.py` 仍有 RioX 注释 | LSB 短格式达到六组 continuation 后终止；MSB 分支有不同终止行为 |
| flags `0x08` 及位流方向 | `CrmtiBitReader` 和泛化探针 | 区分实际观察的 `0x07`／`0x0F` 格式；不能把一套读位顺序套在全部记录上 |
| `0x41E114`、`0x41E2CC` 的行范围状态 | 3016 探针及现行代码“Both RioX readers reset…”注释 | 空行 span=0 时，累积的横向起点归零，避免后续行水平错位 |
| `0x41D3F4`、`0x41D920` 等颜色预测逻辑 | `stage2_verify_transparency_fix.py` 及原生指令摘录 | 核对量化的 RGB 状态、数值处理及透明区段的缓存行为 |
| 元数据到透明段清零分支 | 历史 stage2 验证保存六段精确指令区间与哈希 | 当时针对条带问题确认：观察到的 `0x0F` 模式清空透明区段 RGB 缓存，`0x07` 模式保留；两份自写解码器曾共享漏分支问题 |

六个保存的机器码区间为：`0x40900C–0x409098`、`0x41DA3A–0x41DA5F`、`0x41DDB7–0x41DDC2`、`0x41DEA4–0x41DF61`、`0x42B9E8–0x42BA01`、`0x41D3F4–0x41D5D2`，结束地址不包含。本次重新从保存的 RioX.exe 读取，**六段哈希全部与旧验证记录一致**。

历史透明段修正验证包含 77 次三方比较、24 个手工状态样本、24 个旧行为反事实检查、12 个畸形输入和 29 个冻结样本。报告自己限定为静态参考验证；**RioX 是第三方程序，反汇编 RioX 不等于执行了 Steam 原生游戏解码器。**

### 哪些仍是我们完成的

CRmti 的预测规则不是全部独立发现：早期代码先沿用 alterdec／rugptools 的 Cr6Ti 知识，再借 RioX 二进制补齐 CRmti 特有行为。本项目完成了目标格式的有界解析、Python 实现与逆编码、父对象和内部层级处理、资源配对、容量／几何检查、中文素材编码、覆盖绑定、运行时整合及验证。

CRmt 是父对象，CRmti 才存像素，CRimp 是类型化属性；内嵌 mip 也不自动等于动画帧。这部分结构与 PF／PM 适配工作不能被“前人能导出 PNG”概括掉。

同时不能反过来宣称“前人完全不会解 CRmt”：**RioX 实际已有相关行为，且我们的研究使用了它。** 曾经在所查 GARbro／AFHook 的某些对象表中看到 ReadNull，并不能推广到所有前人工具。

公开通用工具、历史试验脚本和正式包载荷的覆盖范围并不相同。透明段修正的完整历史实现与现行公开通用解码器不能仅凭同名就视为完全同一版本；本报告把它作为已证实的研究与修正来源，**不把历史某次全量验证自动赋给所有现行 helper，也不据此断言已发布包存在同一显示缺陷**。正式包正确性需沿具体载荷／路由核验。

证据：[随包 readme（本地记录 L19）](evidence-index.md#l19)、[初期 CRmti 探针（本地记录 L20）](evidence-index.md#l20)、[历史透明段验证（本地记录 L21）](evidence-index.md#l21)、[本次机器码哈希复核（公开节选）](evidence/source-chain-summary.json)。

## 6. 字体：最初用的文件也已找到

此前只从 Adobe／Source 版权字段推测来源不够准确。现在找到实际 PhotonCN 构建审计与构建器，确认：

| 环节 | 已确认内容 |
| --- | --- |
| 基础输入 | `local-record/NotoSansSC-VF.ttf`，17,773,244 字节；family=Noto Sans SC；version=`Version 2.04;241114210130;non-release` |
| 输入 SHA-256 | `763146584CF0710223441356B4395E279021B0806C196614377A7A0174AE074A`，本次重新核对相同 |
| 初代构建器 | bf82 工作树 `tools/font/build_photoncn_font.py`，SHA-256 `86D346C0EABE7546C8804B40EF5A1F7086E0AAC9BBBEC307EA359C6625BF5F2B` |
| 构建处理 | 将可变字体固定为 wght=400，保留所需码点子集，改名 PhotonCN，处理 hhea／OS2 度量与 codepage 标志 |
| 是否混入微软雅黑／MS PGothic 字形 | 此次找到的基础字形来源链仅为上述 Noto 文件；审计明示参考字体不影响输出字节，MS PGothic 用于度量／覆盖对照，不是字形来源 |
| 初代 PhotonCN 输出 | SHA-256 `B807475C9F60D34711703BACC6D919AF1E619BD92273236E274A2495D2ABC25B`，已核对 |
| 后续适配 | U+2060 零宽字形、独立家族名 PhotonR2、PM 227 个 PUA 选项字形别名、竖向度量修复，以及“珥”补字；“珥”来源仍是同一 Noto 输入哈希 |
| PF 最终字体 | `AADF895003AE6452E1FBDCA1B64206B77D6F9A6EEBE226C31D46D1247AD4830B` |
| PM 最终字体 | `3D1CDF9B8C3CA71D09ECBF5A380FA7F6E9D2F2EE4BB020805711B42FA4322F3B` |

准确署名：**Noto Sans SC 的修改与引擎适配版**，保留上游版权和 OFL；不称自制中文字库。游戏字体来源已追实，不代表每张栅格图片使用的字体也都相同。历史下载渠道尚未追实，但这不影响精确输入文件身份已经确定。

证据：[基础字体构建审计（本地记录 L13）](evidence-index.md#l13)、[基础构建器（本地记录 L22）](evidence-index.md#l22)、[PM 补字说明](../../../localization/fonts/pm-er-20260909.md)。

## 7. 其他组件的完整归属表

这一表补齐前述重点之外的工作。每项“自写”只判断现有证据中本项目的实现归属，不声称相关想法从未出现。

| 技术／内容 | 前人、官方或系统提供什么 | 本项目实际做什么 | 准确类别 |
| --- | --- | --- | --- |
| RIO／ICI 目录解析 | GARbro ArcRIO.cs 的反序列化与目录逻辑 | 维护型 Python 移植；PF／PM 的分卷、范围、父引用、身份、清单和异常检查 | 明确移植＋适配 |
| ICI 解密与 RIO 地址编码 | GARbro `DecryptIci`、`ReadEncrypted`、`DecodeOffset`、`DecodeSize` 的既有算法；包括字节重排、差分／异或、0x20 分段校验、密钥推进、位变换 | Python 对应实现、加密逆过程、保头与写回检查 | 算法重实现／逆过程扩展，不是发明加密算法 |
| 修改过的 GARbro 研究副本 | b09ee457 基线 | 本机 ArcRIO.cs 增加对象类标签、CBoxOcean／OceanNode 映射、2／4 偏移单位处理、Unicode CString、诊断等 | 历史研究代码修改；目录也用于主篇／AL，不能把每一行变化都算成 PF／PM 专属贡献 |
| CRsa／CVM 原生文本结构 | 游戏原有命令、CString、字符串池、引用与语言槽；已有资源／加密知识 | 目标版本的顺序完整解析、字段身份、池引用、注释绑定、边界判定与中文写回 | 本项目版本专用实现，建立在已有格式研究基础上 |
| 正文漏提取检查 | 官方 PF 201、PM 265 个 CRsa 记录 | 检查正文、受语音控制字段、注释、池尾与非待译兵装字段，补提取和修复实际漏项 | 本项目资源普查与文本工作 |
| 文本写入路径 | 官方原生记录与覆盖机制 | 中间阶段 PF 累积 RUO、PM 部分记录固定 extent 写分卷；最终两作 164 个正文显示 CRsa 统一固定范围写入 RIO，旧正文 RUO 覆盖移除 | 本项目写入与安装适配；不能把 append／rewire 试验或中间分工作全部正式默认路线 |
| RUO | 引擎本来支持的覆盖格式 | 核实 12 字节尾部、4 字节单位、映射、累计覆盖限制；构建器与回读；指定 PM 版本虚拟基址修正从 6 GiB 调至 8 GiB | 利用并适配官方格式，不是发明 RUO |
| CRip008 | 官方样本和原生解码函数，已有资源研究背景 | 重建 MSB 位流、4096 整数表、预测及 Alpha；实现验证过的 kind2／kind3 编解码、字面量编码和回读 | 本项目目标子集实现，不是全版本通用解码器 |
| CRmt 父记录与 CRimp 属性 | 官方对象模型；CRmti 像素规则来源见第 5 节 | 已验证父布局、封装、层级、引用、类型化属性及坐标解释；中文各层制作与尺寸／容量保持 | 参考像素算法＋本项目对象和资源适配 |
| 普通图片 PNG 替换 | 官方图像加载；Windows WIC 处理 PNG 解码 | PF／PM 精确资源键、像素表面、行距、Alpha、局部矩形、动态 UI、共享节点和日英 selector 挂接 | 自写版本专用运行时；通用 PNG 解码能力归 WIC |
| Hook 思路、文本与名字颜色 | AFHook 已有制作端／运行时分工、HandleText3/5/6/7→TranslateText、名字颜色、图片解码与 Windows 界面挂钩 | 本项目源码针对两作具体 EXE 地址、调用约定、生命周期和资源身份实现；正文还采用原生写入 | 有明确前人先例的重新实现，不能宣称首次实现上述 Hook 能力 |
| 字体运行时 | Windows GDI、官方资源 DLL 和字体创建链 | 私有字体注册、四条字体路由、家族隔离、官方导出转发及 PF／PM 版本检查 | 本项目适配；不是重写 GDI／字体栅格化引擎 |
| PM 选项字裁边 | 原生四倍字形栅格化／缩小路径，Windows GetGlyphOutlineW | PUA 字形别名及位图边缘处理、固定缓冲容量适配；找到 20260831 v8 wrapper 源码与同哈希正式 DLL | 本项目问题定位和修复 |
| UI／回看／对白排版 | 原游戏布局、动作、颜色系统 | 中文换行、姓名边界、零宽填充、专名字形、颜色别名与绑定；回看“返回游戏”动作修复 | 本项目中文适配与维护；返回动作曾被本项目误改，不是原游戏 bug |
| PM BETA 0.1.1 特殊文本修复 | 原生字段带执行需要的前缀／控制信息 | 修复早先换行／写回流程未完整保留控制信息造成的日文回退；保留特殊字段结构 | 修复本项目回归，不能包装成原游戏特殊字体缺陷 |
| PM 相册与 PF 祭典 | 官方语言对象、动画背景、招牌与局部矩形 | PM selector 失效绑定处理；PF 特定长度编码及 232×253 局部招牌路径；用户实机复测 | 本项目针对实际遗漏／崩溃的整合修复 |
| 图片资源准入与安装 | 既有批准成图和资源记录 | 新旧素材身份检查、索引排序、普通图／CRmt 路由合并，避免只装新 UI 却丢旧素材 | 本项目打包与回归修复 |
| 译文和术语 | 官方日文、已有系列专名、外部提供的部分文本 | AI 辅助初译／复核、维护者修订、语境和军衔统一、注释与版面调整 | 混合来源的本地化；不能称全部从零纯人工翻译 |
| 图片中文制作 | 官方原画和 UI；部分用户成图、部分 GPT Image 辅助 | 文案、擦字／修底、中文排版、透明层与缩放层处理、编码、定位和游戏内展示 | 官方素材的汉化衍生制作；不能称原创原画 |
| 安装器和两作分包 | Windows、.NET、PowerShell、Steam 游戏目录 | PhotonInstaller.cs、Install-PhotonCN.ps1、载荷和压缩包构建、版本识别与安装、按要求不做玩家备份 | 本项目安装实现；未查到直接复制前人整套安装器 |
| 协作校对与 GitHub | ParaTranz API、GitHub Actions 等平台 | PF／PM 稳定词条绑定、拉取、冲突检查、控制符保护、待审 PR 工作流 | 本项目后续维护工具；不倒算为最初包的解包技术 |
| 游戏程序、资源 DLL | 官方 EXE、资源 DLL、Steam API | 仅在指定文件位置改字体名、地址或转发／替换逻辑 | 修改官方程序；整个文件不能算本项目原创 |
| 引擎、画面、声音、成就 | 官方游戏、Steam、系统库 | 中文内容与读取／显示适配 | 官方能力，本项目没有自写整套引擎、音频系统或 Steam 成就系统 |

现行代码入口：[目录与资源工具](../../../rUGP/tools/catalog/rio_inventory.py)、[加密实现](../../../rUGP/formats/rio/crypto.py)、[CRsa 解析](../../../rUGP/formats/rio/crsa_vm_stream.py)、[CRmt 结构说明](../../../rUGP/docs/crmt-family.md)、[运行时构建](../../../rUGP/runtime/build.py)、[安装器](../../../rUGP/packaging/windows/PhotonInstaller.cs)。

## 8. 下载过但不能直接列为生产来源的东西

本次还找到以下准确 Git 副本，但目前没有足够的采用记录把它们列为 PF／PM 实际算法或载荷来源：

| 仓库 | 本机提交 | 判定 |
| --- | --- | --- |
| crskycode/GARbro | `48d7066485f712827b5cc2b9e758aba9a4ab6e8a` | 历史研究副本；不能仅因目录存在就说正式方案采用其修改 |
| nanami5270/GARbro-Mod | 同上 `48d7066485f712827b5cc2b9e758aba9a4ab6e8a` | 同样限定 |
| UserUnknownFactor/GARbro2 | `afcda6feed8eac0d6414f2c81154223372bf8e68` | 同样限定 |
| tsdko/deoptimizeobs | `a710a6482d3191a26180c60b2eaa8b610a259f35` | 同样限定 |

另有 official-riorha2、official-rugp-runtime 等研究目录；没有足够记录证明其中程序进入正式玩家包。版本或用途未闭合时，保留“发现候选但采用未证实”，不能为了凑全把它们写成贡献来源。

thcrap、07th-Mod python-patcher、Committee of Zero SGHD Patch、Tsukihimates、VNTranslationTools、Kuriimu2 的记录支持“仓库边界、玩家入口、语言层、提取／编辑／写回分离等工作流研究”，不支持“直接用它们完成 PF／PM 解包和安装”。也没有把这些参考对象当时每次浏览的提交都保存下来，不能凭今日 HEAD 补造历史版本。

FatePackageManager／主任保护协会的松散覆盖启发属于 AGE2 研究线；可以在整个系列项目致谢中说明，不能算成 PF／PM 的 Cr6Ti、CRip007 或 CRmti 技术来源。

现行依赖清单固定 NumPy 2.5.0、Pillow 12.3.0、fontTools 4.63.0；原生构建文档记录 Zig 0.16.0。Python、.NET、PowerShell、WIC、GDI，以及 pefile、FreeType 等辅助工具的能力归其自身项目。**现行清单版本不自动等于每一次早期试验的环境版本。**

## 9. 正式文件的来源不能凭名字判断

此前已沿实际包及旧构建核实，下列结果继续成立：

| 正式文件 | 具体归属／证据 |
| --- | --- |
| PF Ages3ResT.dll，640,512 字节 | 本项目组合运行时；SHA-256 `80F311F3AC8FAEA4612C779CAF718E238FE0ACAADB8CB739A4917D8C44AFB684` |
| PM Ages3ResT.dll，613,888 字节 | 本项目组合运行时；SHA-256 `F3EEEA147CFC746EB57DB51B9370E8051AAFFEAE5044237342F5035A780217B3` |
| PF private.dll／PM official.dll，15,360 字节 | 相同的官方资源 DLL 字体名修改版；SHA-256 `022079515CB9856B8A2ED452535C939EE410DABF805A5B505D18A0E711AEFB7D`；official 文件名不表示未修改 |
| PM private.dll，244,224 字节 | 本项目选项位图 wrapper，与旧 0713 工作树 v8 产物完全同哈希：`5991C0170B7AB71CFB661D53D15CD5A1CB616BB62695DBC02E97756BB961A4AE` |
| ages_screenSv.dll，137,216 字节 | 官方文件字体名修改版；SHA-256 `6BF8300B5EAC07B39F67BF5C1F32D337935E5606CE2EAD3BF1C2B001929DF0C6` |
| PF／PM EXE | 官方 EXE 的指定补丁版，不能将整个 EXE 视作我们的程序作品；旧“改名变化几个字节”只描述某一步，不代表最终相对 Steam 原件的全部差异 |

这能区分“我们写的转发／替换模块”“修改了名字的官方 DLL”“实际修改过的游戏 EXE”。也不能因其都叫 DLL 就说直接拿了 AFHook DLL。

证据：[实际包固定文件清单](evidence/shipped-fixed-files.json)。

## 10. 内容贡献、仍待补齐的证据，以及对外表述

### 已知内容来源

- “红桃皇后假说”提供过 PF《樱花盛开之前》的部分文本，致谢已明确记录。当前没有完整逐句采用账本；4,037 行被某轮审校保护不变不等于这些行全部由其提供。
- CRmt 审核 49 个逻辑组中，38 组登记中文制作、1 组登记用户成图 U0479“新年初欢！！”、3 组复用日文官图到 translation 槽、7 组保留官图。用户成图的进一步作者／工具来源未由这些清单证明。
- 图片底层人物、插画、UI 构图来自官方；中文改图包括模型辅助和维护者审定，不能说全是原创绘画或全是手工制图。
- 1,789 张、1,490 张、2,793 条路由、49 个逻辑组，属于不同时间与计数单位，不能计算成“原创图片数量”或原创百分比。
- 技术研究、代码、译文处理和图片流程有 Codex／AI 辅助，维护者负责方向、取舍、修订和实机确认。记录不支持全剧情逐句人工听校的绝对承诺。

### 尚不能声称全部查清的部分

1. 外部文本的完整逐句提供、采用、修改范围。
2. 每幅图片的文字作者、修底／排版者、模型版本和所用字体，以及用户成图进一步来源。
3. RioX 当时的下载链接、基础 Noto 文件最初下载渠道；**版本和实际文件哈希已经查清，缺的是渠道，不再是版本。**
4. 仅留下下载目录的候选工具究竟在何次实验使用；没有采用证据的条目不能填成生产依赖。
5. 所有历史试验与每份已发包逐文件逐行一一对应的完整账本；本报告只对已绑定源码／构建／哈希的项目作确定判断。

以上未闭合的来源范围保留为待确认，不用推测填补。本次公开说明同步更新已核实的 RioX 版本与参考用途。

## 11. 本次新增证据索引

以下是本地核查记录的名称及用途，不代表原始文件均已上传；公开的测量摘要见[证据索引](evidence-index.md)。

| 文件 | 内容 |
| --- | --- |
| `historical-research-checkouts.json` | 上游本地副本 remote、完整提交与保存路径 |
| `historical-garbro-ArcRIO-adaptation.diff` | 旧 GARbro 研究副本相对固定上游的实际代码差异 |
| `verified-source-chain.json` | RioX 六段指令的重新哈希核对、旧 Cr6Ti／字体审计及 23 分支目录检查 |
| `crip007-readonly-replay.json`、`replay_crip007.py` | 本次真实原始记录离线旧／新解码对比及可复现脚本 |
| `historical-source-excerpts.json` | 按 RioX 等关键词定位的历史会话摘录，仅作旁证 |
| `github-issues-and-prs.json`、`github-releases.json`、`github-issue-comments.json` | 当前 GitHub 历史记录快照 |
| `github-branches.json`、`github-branch-trees/`、`github-current-to-main.json` | 远端分支、完整目录树及现行文件一致性 |
| `main-technical-hit-files.txt`、`main-riox-hit-files.txt`、`3016-riox-hit-files.txt` 等 | 主目录和历史工作树的检索定位记录，不是逐文件审核通过清单 |

旧报告保存在本地审计历史中，关于 RioX、alterdec、字体和相关来源的旧结论以本报告为准。
