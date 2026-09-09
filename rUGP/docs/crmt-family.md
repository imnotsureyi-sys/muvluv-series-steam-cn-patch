# CRmt 家族：结构、图片对应与安全替换

[rUGP 首页](../README.md) · [图片工具](../tools/images/README.md) · [当前审核清单](../evidence/photon/crmt/README.md)

本指南针对已观察、验证的 PF／PM Steam 资源格式。工具遇到未知布局应拒绝，不把它泛化为所有 AGES 游戏支持。

## 三者不是三种平行的图片格式

```text
CRmt 图片父对象
├─ 内嵌 CRmti 层：通常为同图的不同尺寸，并非当然是动画帧
├─ 外部图片成员：可能引用独立存储的 CRmti，也可能为空
└─ ImageMP → CRimp：有类型的属性，如原点；不是像素图片

游戏日英映射：官方日文 CRmt → translation 目标 CRmt
汉化覆盖：原 translation 目标资源键 → 新编码的 CRmt
```

- **CRmt** 保留父前导、子图封装、引用及尾部元数据。不能只拷入 PNG，也不能只换顶层而遗留外文小图。
- **CRmti** 承载压缩像素。内嵌记录具有四字节 wrapper；独立记录采用不同封装，不能把内嵌子图偏移当作独立记录。
- **CRimp** 是带类型标签的属性映射。它不是 CRmt 的某一张图片，不能交给像素解码器。
- **Cr6Ti／CRip007／CRip008** 有自己的封装与像素编码；外部引用声明 CRip007 基类不代表实物就是 CRip007 压缩流。以实际解析类型为准。

`crmt_metadata.py` 重放已验证布局中的对象／类缓存，解析实际 ImageMP 及外部依赖；
它不凭相邻地址推断所有者。原生映射中 ImageMP 与外部图片是不同成员。

CRimp 的四字节整数带低两位类型标签 `2`，应作有符号算术右移两位；不能将原始字直接解释为 16.16。
`_CPoint32`／`_CVector32` 保留有符号分量。只有已验证的 `crmt_origin()` 消费路径使用其特定坐标解释，
不把其他属性自动解释为相同单位，也不把原点查询结果当成最终屏幕位置。

## 对照与翻译政策

使用 **官方日文／官方英文／汉化** 三列。

1. 日英共用图标记“官方日文，无英文本地化”，默认保留；明显影响阅读理解时另行汉化。
2. 日英分开图重点审核。日文内容与简体中文一致时，可将日文官图明确登记为 translation 槽候选，不能只删除英文替换而依赖回退。
3. 日文为日文、英文为英文时，以日文为原文制作中文；英文只作本地化方式参考。
4. 日文官图本来使用的英文通常保留，只处理其中需理解的日文。按文字用途判断，不机械排除所有 HUD、武器或场景招牌。
5. 同物理对象的缩放层、不同物理位置的副本和真正不同姿态／状态分别记账。

例如 U0478 有两个 PM 目标；日文竖排 4 层、英文横排 6 层、已批准中文竖排 4 层。
不能按层序跨语言强行认定相同尺寸，也不能把某一个目标通过当成两个目标都通过。
PF／PM 的 U0006 则是不同物理资源，哪一个被请求和替换必须分别核对。

## 从个人游戏副本复现

在仓库根目录安装 `rUGP/requirements.txt`。先使用 [ICI 目录工具](../tools/catalog/README.md) 确认类型、分卷、偏移和长度；
不要仅搜索可读的 `CRmt` 字样，也不要把扫描命中数量当作解析闭合证明。
以下 `X:` 路径及数值均为示例，用清单或本机目录核实的值替换。

导出 CRmt 的**全部内嵌层**，要求原记录哈希吻合：

```powershell
python -m rUGP.tools.images.export_crmt_layers `
  --source "X:\Game\example.rio.002" --offset 0x123400 --extent 0x5678 `
  --sha256 "从公开清单复制64位记录SHA256" --output-dir "X:\Work\source-layers"
```

输出每层 PNG 与 manifest，不自动追读外部引用。单张顶层预览可用
`python -m rUGP.tools.images.decode_record --codec crmt`，但顶层 PNG 不等于完整图片对象。

当元数据明确给出外部 **CRmti** 的准确范围时，另行读取：

```powershell
python -m rUGP.tools.images.decode_crmti `
  --source "X:\Game\example.rio.002" --offset 0x234500 --extent 0x6789 `
  --output "X:\Work\external.png"
python -m rUGP.tools.images.inspect_crimp `
  --source "X:\Game\example.rio.002" --offset 0x345600 --extent 64
```

前者保留独立 CRmti 的完整画布，不先缩成父图尺寸；后者输出属性 JSON，不生成图片。

## 中文制作与编码

使用允许再分发的字体，保留许可与字体身份。图上日期、地点、术语必须经人工审校。
精确改字时用 `check_localized_image` 检查允许区域外的 RGBA 是否不变：

```powershell
python -m rUGP.tools.images.check_localized_image `
  --source-png "X:\Work\source.png" --candidate-png "X:\Work\zh-Hans.png" `
  --region 10,20,200,80
python -m rUGP.tools.images.replace_crmt `
  --source "X:\Game\example.rio.002" --offset 0x123400 --extent 0x5678 `
  --top-png "X:\Work\zh-Hans.png" --output "X:\Work\candidate.crmt"
```

区域坐标是左上角包含、右下角不包含。透明文字改写可能改变区域内 alpha，不能一概要求全图 alpha 不变。
编码器用预乘 alpha 的 Lanczos 生成模板指定的各层，考虑原生容量提示，并再次解码核对。
检查报告不证明文案正确或游戏已显示。该命令只生成独立记录，**不注入、不安装**。

普通替换必须保持模板尺寸。日文／英文形状不同的 U0478 等需要已经核实的父几何处理；
不能用一般命令保证跨语言模板切换、尾部边界框或 CRimp 属性已经正确。
当前公开工具不自动复制所有本机特例脚本，也不自动取得汉化稿。

## 验证顺序与曾经失败的原因

| 验证 | 能证明什么 | 不能代替什么 |
| --- | --- | --- |
| 目录＋有类型引用＋精确封装 | 对象身份和枚举范围 | 解码或翻译正确 |
| 全层解码／编码后回读 | 尺寸、像素、压缩和容量约束 | 游戏选择了该对象 |
| RUO 原目标键映射回读 | 替换落在正确路由，其他映射未改变 | 画面显示 |
| 专用入口请求原键＋只读 payload 探针＋截图 | 正确对象与汉化画面在测试环境成立 | 所有自然剧情场景 |
| 正常启动及原剧情回归 | 实际时机、位置、遮挡和交互 | 其他版本与机器必然正常 |

- PNG 看起来正确仍可能在游戏里消失：检查原生解码缓冲容量，不是仅检查压缩文件大小。
- 编码器回读成功仍可能命中错图：检查实际日英映射和原始请求键，不用另一个成功资源键冒充目标验证。
- 画面裁掉或空白还可能来自父几何、CRimp 或演出位置。保留原属性不是随意重排外形后的充分条件。
- 指针／payload 已加载不等于图片已经绘制；某 mip 驻留也不等于它被单独画过。
- PM 诊断曾依赖 8 GiB RUO 地址空间修正。诊断启动器通过不自动说明正式 DLL 通过；必须分别锁定 DLL、RUO 与 EXE 身份验证。

RUO 应合并进同一现有补丁映射，逐条检查未修改目标的旧映射／payload 不变。不要生成第二份补丁覆盖掉正文或其他图片。
此 PR 不修改运行时 DLL，也不发布 EXE、RUO、诊断注入器或玩家安装包。

## 测试和发布边界

审核发布适配器的四个输入格式、配对闭合规则和无需游戏素材的可运行示例，见
[审核导出输入契约](crmt-review-inputs.md)。导出时会重解码中文记录并逐层比较实际 RGBA，
不只验证清单自报的 PNG 哈希。

```powershell
python -m unittest discover -s rUGP/tests/formats/images -p "test_*.py" -v
python -m unittest discover -s rUGP/tests/tools/images -p "test_*.py" -v
python -m unittest rUGP.tests.provenance.test_crmt_review_catalog -v
```

编解码测试使用合成样本，清单测试不需要官方像素。公开清单的哈希不能让无游戏副本的人复现完整实机过程。
代码、公开元数据、图片内容权利和最终发布包应分开审查；见[发布政策](../../docs/project/asset-and-release-policy.md)。

## English summary

CRmt is a parent, CRmti stores pixels (inline mips or a separately framed external member),
and CRimp stores typed metadata. Publish tools and hash-bound locale/object/layer identities,
not extracted artwork. The current 49-group review is not the 20,650-image inventory or the
historical 56+811 subset. Offline decoding, diagnostic own-key rendering, formal-runtime
startup and original-story QA are separate evidence levels. See the public catalog for scope.
