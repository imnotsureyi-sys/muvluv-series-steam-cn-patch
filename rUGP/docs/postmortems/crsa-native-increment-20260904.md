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
合计增加 150 个 UTF-16 代码单元；其余五个记录不扩池。构建器逐条检查所有非目标
池字节、命令、CString、声音引用、后缀内容及继承 RUO 路由。严格 CRsa 解码和
独立兼容解码都必须得到完全相同的明文。生成的 RUO 和游戏二进制是本地／Release
产物，不进入 Git。

```powershell
python -m rUGP.tools.text.build_crsa_native_increment `
  --spec rUGP/games/photonmelodies/translations/increments/crsa-native-20260904.json `
  --source-dir "<PM game directory>" `
  --output "<work directory>/pm-native-v3-fixed.ruo"

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

## 验证边界

静态检查覆盖 305 个审校字段、53 个 CRsa、437 个写回动作和 260 个排除参数；
所有批注键都必须能在其正文中找到，全部命令、声音引用、继承路由和非目标池字节
都要回读一致。实机抽样还需分别确认对白／提示及批注的正文显示、回看显示、字体、
换行和布局，并记录 PM 是否出现 831／8311。只有这一步通过后，才能将候选标为
可提交状态；解析回读不能代替实机验收。
