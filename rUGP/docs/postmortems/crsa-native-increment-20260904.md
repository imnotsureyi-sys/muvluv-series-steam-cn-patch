# PF／PM CRsa 补译和原生绑定写回：2026-09-04

本轮在[全量原生字段审计](crsa-native-text-20260903.md)的结果上，按维护者确认的
范围处理 **40 处对白／提示**和 **265 个批注字段**。另有 **260 处兵装名参数**
保留原样，排除漏译统计和写回动作。565 只是此前的候选清点数，实际翻译／审校
范围是 305 个字段。

## 翻译和复核

40 处对白／提示按现有术语表、军衔表、角色口吻和同场景上下文翻译；其中 PF
4 处为训练场对白，PM 36 处为打西瓜小游戏的方向、距离、超时和命中提示。控制
源槽本身保留，写回现用中文显示槽。

265 个批注逐项判断：

- 157 项含有现用中文正文没有表达的词义，整理为 154 个中文显示批注；三组同句
  日文／英文来源合并，避免同一小字重复显示；
- 108 项为纯日语注音或正文已经完整表达的解释，不强行加入中文；
- 245 项原文列批注继续保留，其中 243 个旧索引修复到原批注单元；
- 20 项原显示列批注全部重新绑定，其中 19 项为可显示释义，1 项保留 `&` 格式值。

初译和第二轮复核由同一 Codex 工作过程分轮执行，不能冒充第二位独立审校者。
40 个控制源槽通过两个本地语音识别模型及同场景日文文本交叉确认，没有宣称完成
人工听校。逐项决定、来源绑定、译文及修订理由见公开的
[`crsa-native-review-20260904.json`](../../evidence/photon/text/crsa-native-review-20260904.json)；
本轮复用和限制使用的术语见
[`crsa-native-terms-20260904.json`](../../evidence/photon/text/crsa-native-terms-20260904.json)。

## 原生写回

[`crsa_vm_edit.py`](../../formats/rio/crsa_vm_edit.py)按原生 `CVmMsg3` 三字段结构写回：

- 40 处对白／提示全部写入原显示正文槽，池长度和正文索引不变；
- 原文批注只修复原文列的批注索引，不改变日文正文或批注字节；
- 154 个中文批注中，19 个复用原显示批注槽，123 个写入池内未被任何字段引用的
  连续空槽，1 个写入清单按原文哈希、索引和容量锁定的旧译残留槽；PF 余下 11 个
  没有原生容量，由清单逐项显式允许追加；
- 所有字段先核对原记录、明文、正文、批注、命令目标和索引哈希，任何漂移均拒绝。

PF 清单包含 7 个 CRsa、169 个动作；PM 清单包含 46 个 CRsa、268 个动作，合计
53 个 CRsa、437 个动作。其中 243 个是原文批注索引修复，154 个是中文批注绑定，
40 个是对白／提示写回。两个清单的兵装名写回动作均为 0。
原生写回器也不提供兵装名修改动作；兵装识别只保留在只读审计器中，用于证明
这些参数被完整排除。

写回器默认拒绝扩展文本池；非空闲槽复用和追加都必须有清单中的显式存储合同。
PM 的 46 个记录全部保持池长度、后缀位置和记录长度不变。PF 只有两个记录追加，
其中 11 个批注动作合计增加 150 个 UTF-16 代码单元；其余五个记录不扩池。构建器
逐条检查所有非目标池字节、命令、CString、声音引用、后缀内容及继承 RUO 路由。
严格 CRsa 解码和独立兼容解码都必须得到完全相同的明文。生成的 PF RUO、PM 分卷
副本和游戏二进制是本地／Release 产物，不进入 Git。

## PM 的 831 运输问题

最初把 PM 原生增量生成为独立 `.ruo1`。对后续分卷中的 CRsa 做**内容完全相同**的
身份重编码，也会在实机读取该记录时触发 `InternalError(831): Abnormal termination`；
因此这次错误不能归因于中文、字段内容、记录长度或校验和。随后在完整备份、原卷哈希
门和进程关闭检查下，把同一记录写回原分卷的相同物理范围，游戏通过了原报错位置。
46 个固定长度记录用同一路线写回后，也能进入 Adoration 批注场景和 Altered Fable
打西瓜小游戏，未出现 831 或 8311。验收结束后，所有原卷均按整卷 SHA-256 恢复。

据此，PM 本轮原生 CRsa 的生产运输固定为：从干净原卷生成新的固定长度分卷副本，
只改清单指定的记录范围，再由发布构建生成带安装／回滚哈希门的区段补丁。公共工具
[`build_crsa_native_volume_patch.py`](../../tools/text/build_crsa_native_volume_patch.py)
拒绝覆盖输入、继承 RUO、记录增长、范围重叠和任何非目标字节变化。PF 仍使用一个
累计 RUO，因为它的两个记录含有显式审核过的追加写入。这一 **831 分卷重定向问题**
与 [`8311` 的 counted CString 内嵌 NUL](error-8311.md)是两个不同故障。

```powershell
python -m rUGP.tools.text.build_crsa_native_volume_patch `
  --spec rUGP/games/photonmelodies/translations/increments/crsa-native-20260904.json `
  --source-dir "<clean PM game directory>" `
  --output-dir "<new work directory>/pm-native-fixed-volumes"

python -m rUGP.tools.text.build_crsa_native_increment `
  --spec rUGP/games/photonflowers/translations/increments/crsa-native-20260904.json `
  --source-dir "<PF game directory>" `
  --base-ruo "<PF game directory>/photonflowers11.rio.ruo1" `
  --output "<work directory>/pf-native-v3-minimal-append.ruo"
```

## 兵装名保护

260 个兵装名参数分别位于 PF 246 个、PM 14 个 `CVmCall` 参数 2 位置，共四种
原文。验证程序逐项保存字段身份及写前／写后哈希，并检查所有字节保持一致；它们
不参与术语扩充，也不进入候选清单。公开证据保留数量和哈希合同，不复制游戏原文。

## PF 字体补字

新增 PF 批注使用了原字体缺少的 `U+4F36`。字体构建工具以当前
`PhotonR2-Regular.ttf` 为基底，只从 Noto Sans CJK SC 可变字体的常规字重提取该
字形。供体 SHA-256 为
`763146584CF0710223441356B4395E279021B0806C196614377A7A0174AE074A`，采用
SIL Open Font License 1.1；最终字体继续附带项目现有的字体许可文件。

[`extend_font_subset.py`](../../../localization/tools/extend_font_subset.py)拒绝覆盖输入，
核对基底和供体哈希，并确认原字形轮廓、提示、水平／垂直度量、cmap GID、GSUB／
GPOS、名称和许可表都没有变化。结果从 4,715 个字形增加为 4,716 个，只新增
`U+4F36`。字体 SHA-256 为
`AD5A0EE08FE7513EDF963CC78046C4EB4EF6AC91C480AD1444F06307770117B1`。

字体运行时的精确哈希针同时由
[`rebind_photon_font.py`](../../tools/runtime/rebind_photon_font.py)更新；该工具只允许
修改唯一的 64 字节 ASCII 哈希，并证明宿主 DLL 的可执行代码和其余字节不变。

## 实机抽样和证据

静态检查覆盖 305 个审校字段、53 个 CRsa、437 个写回动作和 260 个排除参数；
所有批注键都能在其正文中找到，全部命令、声音引用、继承路由和非目标池字节均回读
一致。2026-09-04 又完成下列实机抽样：

- PF Confessions 回看同时显示本轮四句训练场漏译对白；中文字体、长句换行、说话者
  标签和滚动区域正常；
- PF Rain Dancers 回看显示 `雨之舞者`／`雨舞中队`、`首席女伶`／`突击前卫` 两组
  小字绑定，字号、基线和行距正常；
- PM Adoration 的德语句首次试验暴露了长分句键只命中中间一项；改成正文内唯一短键
  `bitte`、`erschreckt habe`、`jemand ist.` 后，三项中文小字在回看中全部正确显示；
- PM Altered Fable 打西瓜小游戏直接显示了前进、向右、身后和向左四类本轮漏译提示，
  没有英文回退、缺字、越界、遮挡或异常换行；小游戏提示不进入普通回看，因此在实际
  控制界面取证；
- PM 以固定长度分卷写回进入上述两个场景，整个抽样没有出现 831 或 8311。

截图含零售游戏画面，不进入 Git；下列文件名和 SHA-256 固定本次本地证据：

| 实机证据 | SHA-256 |
| --- | --- |
| `pf-confessions-missing-dialogue-backlog-20260904.jpg` | `4A710B4DE5750788490C7F6CB29831138DA6A83A3F34FF358A2197ECDD99EB70` |
| `pf-rain-dancers-annotation-backlog-20260904.jpg` | `27B00C8BB90B8284B3574DB2CA9CADF371902DFE618E8D418DDAB59CD5E346D9` |
| `pm-adoration-annotation-backlog-20260904.jpg` | `46AB73DE97D287E84D32C5BE5E586BD055C87EAD759CE2EBFBD147596C5240C8` |
| `pm-watermelon-missing-prompt-forward-20260904.jpg` | `32E9C4264C3208EA16AB2BBAA2E1BC16FC5B04C65303872876EA0FA3861DCE8E` |
| `pm-watermelon-missing-prompt-right-20260904.jpg` | `17D010EAFA417F19806730F3F95575BE494AF3C4668BAA2040F4C31FB8433269` |
| `pm-watermelon-missing-prompt-behind-20260904.jpg` | `CFF8CF1D0102CA04312FC51DD7132FA0D2A54CBFFDF943142FD5353D0DDA572B` |
| `pm-watermelon-missing-prompt-left-20260904.jpg` | `8B0208B624F1BA634A23F88C27DE1F37C61B1174C75F34AD94FEF5C33668A0E1` |

这组抽样验证了两种游戏、两类字段和 PM 特殊小游戏表面的真实显示；它不冒充对 305
个字段逐一走完所有剧情分支。全量字段身份和写回正确性由哈希清单及解析回读覆盖，
实机抽样负责证明代表性表面的字体、排版和运输行为。
