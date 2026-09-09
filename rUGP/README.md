# rUGP：Photon Flowers 与 Photon Melodies

[返回首页](../README.md) · [游戏与汉化资产](games/README.md) · [格式](formats/) · [运行时](runtime/) · [打包](packaging/) · [逆向复盘](docs/postmortems/README.md) · [测试](tests/)

这里负责旧 rUGP／AGES 资源体系，与 [AGE2](../AGE2/README.md) 完全独立。当前目标是 Muv-Luv photonflowers（PF）和 photonmelodies（PM）。

## 先看懂资源层级

```text
<游戏>.rio.ici        加密的目录、对象类型与引用元数据
        │
        ▼
<游戏>.rio[.002…]     保存真正对象数据的一个或多个 RIO 卷
        ├─ CRsa                    文本或 VM 对象
        ├─ Cr6Ti/CRip007/CRip008  图片对象
        ├─ CRmt → CRmti           图片父对象、内嵌缩放层及可选外部图片
        ├─ CRmt ImageMP → CRimp   有类型的图片属性，不是像素
        └─ 父对象/CodeArcRef       偏移、长度与关系

替换路线
        ├─ <游戏>.rio.ruo1         适合静态覆盖的完整对象
        └─ 版本锁定运行时          静态对象无法安全表达的字体/解码表面替换
```

ICI 只告诉我们对象在哪里、是什么类型；找到 RIO 中的对象以后，还必须交给对应 CRsa 或图片解码器。能读取一个对象也不等于能安全写回，编码器还要保持头部、尺寸、透明度、预测状态、父引用和运行时约束。

CRmt 家族的结构、日英对应、全层导出和替换验证请从[专项指南](docs/crmt-family.md)开始。
当前[49 组审核清单](evidence/photon/crmt/README.md)与下方历史 1,490 项图片权威分开记账，不能直接相加。

## 游戏与核心汉化资产

| 游戏 | 已审校文本 | 精确运行时绑定表 | 图片资产状态 | 玩家包 |
| --- | --- | --- | --- | --- |
| [Photon Flowers](games/photonflowers/) | [13,025 条章节文本](games/photonflowers/translations/) | [69 行历史合同](games/photonflowers/text-data/runtime/zh-Hans.csv) | [636 项](games/photonflowers/images/) | [BETA 0.1](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/pf-BETA-0.1) |
| [Photon Melodies](games/photonmelodies/) | [44,698 条章节文本](games/photonmelodies/translations/) | [151 行历史合同](games/photonmelodies/text-data/runtime/zh-Hans.csv) | [854 项](games/photonmelodies/images/) | [BETA 0.1](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/releases/tag/pm-BETA-0.1) |

上表图片数为 V6 历史集合。另见[当前 1,791 项静态审核选集](evidence/photon/images/static-review-20260909/README.md)
及[审核页／长图工具](tools/images/README.md)：保留最新人工稿与待安装修订，不能与历史数相加。

图片的稳定身份、源/成品哈希、格式、尺寸与路由统一保存在
[`evidence/photon/`](evidence/photon/README.md)；编解码器在 [`formats/images/`](formats/images/)。
图片二进制位于单独的历史研究资产 Release，当前仍有 19 张与官方来源字节相同的项目
需要整改，因此不能当作已批准分发的玩家包。

字体文件也没有直接进入源码树。可复现的字体选择、覆盖检查、GDI 路由与失败经验记录在[字体运行时复盘](docs/postmortems/font-runtime.md)及 [`runtime/`](runtime/)；发布时仍须附可再分发字体及其许可证。

## 目录职责

- [`games/`](games/)：按游戏保存台词表与精确绑定表。
- [`formats/images/`](formats/images/)：Cr6Ti、CRip007、CRip008、CRmt／CRmti 编解码及 CRimp 类型属性。
- [`formats/rio/`](formats/rio/)：RIO 加密、引用、RUO、CRsa 和 VM 字符串池。
- [`tools/`](tools/)：ICI/RIO 目录、只读 CRsa 提取、图片检查、文本导出与来源验证。
- [`runtime/`](runtime/)：PF/PM 分开构建、遇到未知 EXE/DLL 哈希即拒绝运行的 x86 代理。
- [`packaging/`](packaging/)：从已经封存并锁定哈希的输入根构建候选包。
- [`evidence/`](evidence/)：公开清单、哈希、路由闭环和可复核结论。
- [`docs/postmortems/`](docs/postmortems/README.md)：8311、CRsa、RUO、Cr6Ti、CRip007/008、字体、shared/common 图片等完整攻克记录。

完整设计见[架构](docs/architecture.md)、[工作流](docs/workflow.md)、[质量门](docs/quality.md)和[来源模型](docs/provenance.md)。

## 测试

在仓库根目录运行：

```powershell
python -m pip install -r rUGP/requirements.txt
python -m unittest discover -s rUGP/tests -p "test_*.py" -v
```

这些测试验证公开代码和合成样本。真实游戏仍需要精确版本、合法输入、完整封装和逐路线实机 QA。

## English summary

This directory contains the legacy rUGP/AGES work for photonflowers and photonmelodies: reviewed translation tables, ICI/RIO/CRsa and image codecs, RUO primitives, a version-pinned runtime, packaging, evidence, tests and postmortems. It is independent from `AGE2/`; begin with the [workflow](docs/workflow.md).
