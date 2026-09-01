# Legacy rUGP localization path

[中文概要](#中文概要) · [Formats](formats/) · [Runtime](runtime/) · [Packaging](packaging/) · [Evidence](evidence/) · [Postmortems](docs/postmortems/README.md) · [Tests](tests/)

This tree covers the legacy rUGP/AGES resource system used by Muv-Luv photonflowers (PF) and photonmelodies (PM). It is independent from `age2/`.

## Mental model

```text
<game>.rio.ici       encrypted serialized directory/reference metadata
        |
        v
<game>.rio[.002…]    large archive volumes containing typed records
        |
        +-- CRsa                       serialized/encrypted text or VM objects
        +-- Cr6Ti / CRip007 / CRip008 image records
        +-- parent objects / CodeArcRef offset+extent references
        |
        +-- <game>.rio.ruo1            native override records where safe
        +-- version-pinned runtime      font and decoded-surface routes that static replacement cannot safely express
```

Opening the ICI does not produce pictures or dialogue by itself. It turns encrypted bytes into directory/reference metadata that locates typed records in one of the RIO volumes. A second decoder interprets each record; a third authoring step produces a verified replacement. Repacking is therefore not simply “run decompression backwards.”

## Current public work

| Game | Reviewed dialogue authority | Exact runtime-bound table | Player release |
| --- | --- | --- | --- |
| [Photon Flowers](games/photonflowers/) | 12,964 rows in [`translations/reviewed/`](games/photonflowers/translations/reviewed/) | [69 rows](games/photonflowers/translations/zh-Hans.csv) | Not yet published |
| [Photon Melodies](games/photonmelodies/) | 44,583 rows in [`translations/reviewed/`](games/photonmelodies/translations/reviewed/) | [151 rows](games/photonmelodies/translations/zh-Hans.csv) | Not yet published |

The repository also records the approved [1,490-image V6 authority](evidence/photon-images-v6/), runtime source, and a deterministic package builder whose inputs are already sealed, hash-locked staging roots. The public tree does not yet build those roots from a clean PF/PM installation end to end. These are release-candidate components, not an invitation to install files from a development checkout.

## Public surfaces

- [`formats/images/`](formats/images/): strict Cr6Ti, CRip007 and CRip008 decode/encode implementations.
- [`formats/rio/`](formats/rio/): RIO crypto/reference/RUO and CRsa/CVM string-pool code.
- [`runtime/`](runtime/): fail-closed x86 proxy/runtime compiled separately for PF and PM.
- [`packaging/`](packaging/): clean-root, hash-locked package builder, Windows installer template and strict read-only PF/PM Steam-locale preflight for a future player release.
- [`tools/`](tools/): portable ICI/RIO catalogue, read-only CRsa extraction, provenance and text export utilities; not research scratch scripts.
- [`docs/postmortems/`](docs/postmortems/): evidence, wrong hypotheses, root causes, fixes, and regression rules.

See the [architecture](docs/architecture.md), [workflow](docs/workflow.md), [quality gates](docs/quality.md), and [provenance model](docs/provenance.md).

## Test

```powershell
python -m pip install -r rugp/requirements.txt
python -m unittest discover -s rugp/tests -p "test_*.py" -v
```

## 中文概要

ICI 只是目录/引用元数据，RIO 各卷才保存真正的 CRsa 文本对象和 Cr6Ti/CRip 图像对象；找到对象后还要按其格式继续解码。能解码不代表必然能安全编码：编码器必须保留类型、画布、透明度、预测状态、引用关系和运行时约束。Photon 最终路线同时使用静态 RIO/RUO 修改与严格绑定游戏哈希的运行时，二者都有源码和验证门槛。
