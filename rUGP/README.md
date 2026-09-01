# rUGP：Photon Flowers 与 Photon Melodies

[返回首页](../README.md) · [游戏与汉化资产](games/) · [格式](formats/) · [运行时](runtime/) · [打包](packaging/) · [逆向复盘](docs/postmortems/README.md) · [测试](tests/)

这里负责旧 rUGP／AGES 资源体系，与 [AGE2](../AGE2/README.md) 完全独立。当前目标是 Muv-Luv photonflowers（PF）和 photonmelodies（PM）。

## 先看懂资源层级

```text
<游戏>.rio.ici        加密的目录、对象类型与引用元数据
        │
        ▼
<游戏>.rio[.002…]     保存真正对象数据的一个或多个 RIO 卷
        ├─ CRsa                    文本或 VM 对象
        ├─ Cr6Ti/CRip007/CRip008  图片对象
        └─ 父对象/CodeArcRef       偏移、长度与关系

替换路线
        ├─ <游戏>.rio.ruo1         适合静态覆盖的完整对象
        └─ 版本锁定运行时          静态对象无法安全表达的字体/解码表面替换
```

ICI 只告诉我们对象在哪里、是什么类型；找到 RIO 中的对象以后，还必须交给对应 CRsa 或图片解码器。能读取一个对象也不等于能安全写回，编码器还要保持头部、尺寸、透明度、预测状态、父引用和运行时约束。

## 游戏与核心汉化资产

| 游戏 | 已审校文本 | 精确运行时绑定表 | 图片资产状态 | 玩家包 |
| --- | --- | --- | --- | --- |
| [Photon Flowers](games/photonflowers/) | [12,964 行](games/photonflowers/translations/reviewed/) | [69 行](games/photonflowers/translations/zh-Hans.csv) | 纳入跨两作的 1,490 图清单 | 尚未发布 |
| [Photon Melodies](games/photonmelodies/) | [44,583 行](games/photonmelodies/translations/reviewed/) | [151 行](games/photonmelodies/translations/zh-Hans.csv) | 纳入跨两作的 1,490 图清单 | 尚未发布 |

图片的稳定身份、源/成品哈希、格式、尺寸与路由保存在 [`evidence/photon-images-v6/`](evidence/photon-images-v6/) 和 [`evidence/photon-image-routes-v1/`](evidence/photon-image-routes-v1/)；编解码器在 [`formats/images/`](formats/images/)。图片二进制目前没有进入 Git 主线，因为其中仍有官方原件与衍生内容的再分发边界需要清理。

字体文件也没有直接进入源码树。可复现的字体选择、覆盖检查、GDI 路由与失败经验记录在[字体运行时复盘](docs/postmortems/font-runtime.md)及 [`runtime/`](runtime/)；发布时仍须附可再分发字体及其许可证。

## 目录职责

- [`games/`](games/)：按游戏保存台词表与精确绑定表。
- [`formats/images/`](formats/images/)：Cr6Ti、CRip007、CRip008 的严格解码/编码实现。
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
