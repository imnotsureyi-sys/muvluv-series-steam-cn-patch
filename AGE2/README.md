# AGE2：TDA 与帝都燃烧篇

[返回首页](../README.md) · [游戏与汉化资产](games/) · [工具](tools/) · [工作流](docs/workflow.md) · [问题复盘](docs/postmortems/README.md) · [测试](tests/)

这里负责较新的 AGE2 移植体系，与 [rUGP](../rUGP/README.md) 完全独立。当前涉及 THE DAY AFTER episode:00–03 与 The Imperial Capital Burns／帝都燃烧篇。

## 先看懂资源层级

```text
pack.bin                         FPD v2 外层容器
└─ root/assets/...
   ├─ localized/*.egpack        多语言正文与结构字段
   ├─ gui/**/*.webp             可直接查看的图片
   ├─ uistring.epk              单独加密的 UI 字符串
   └─ 字体、配置、XML 等

%LOCALAPPDATA%/ancr/<游戏>/data/root/...
└─ 保持相同相对路径的松散覆盖文件；游戏优先于 pack.bin 读取
```

FPD 与 EGPACK 是两层不同格式：先从 `pack.bin` 的 FPD 目录找到文件，再解析具体 EGPACK 的语言槽。现有补丁不修改原始 `pack.bin`，而是安装少量松散覆盖文件。

## 游戏与核心汉化资产

| 游戏 | 文本与术语 | 图片文案 | 历史补丁 |
| --- | --- | --- | --- |
| TDA00 | [`games/tda00/translations/`](games/tda00/translations/) | 尚未形成独立公开图片资产集 | beta0.1 |
| TDA01 | [`games/tda01/translations/`](games/tda01/translations/) | 尚未形成独立公开图片资产集 | beta0.2.2 |
| TDA02 | [`games/tda02/translations/`](games/tda02/translations/) | 尚未形成独立公开图片资产集 | beta0.1 |
| TDA03 | [`games/tda03/translations/`](games/tda03/translations/) | 尚未形成独立公开图片资产集 | beta0.1.6 |
| 帝都燃烧篇 | [正文、选项、说话人、UI 与术语](games/imperial-capital-burns/translations/) | [图片文字、排版与来源锁](games/imperial-capital-burns/images/copy/) | beta0.1 |

这些表是当前可维护的公开快照，不代表能够逐字节重建历史 Release。公开表、旧分支与实际发布载荷之间的差异保留在[对齐审计](evidence/translation-snapshots-v1/authority-alignment-audit.md)中。

## 工具按层分开

- [`tools/fpd/`](tools/fpd/)：读取和筛选提取 FPD；密钥调度参考 FatePackageManager 的 `Scrambler.cs`。
- [`tools/egpack/`](tools/egpack/)：导出语言字段、按准确槽位写回并验证允许变化的字节。
- [`tools/text/`](tools/text/)：把私有原文审校表导出为以哈希绑定的公开翻译表；它不是 EGPACK 写入器。
- [`tools/uistring/`](tools/uistring/)：修改已经解密的 UI 数据；不负责 FSNr EPK 解密。
- [`tools/font/`](tools/font/)：记录已淘汰的字形替换方案，并连接到通用字体覆盖检查。

完整步骤、质量门与依据分别见[工作流](docs/workflow.md)、[架构](docs/architecture.md)、[质量检查](docs/quality.md)和[来源说明](docs/provenance.md)。

## 测试

在仓库根目录运行：

```powershell
python -m pip install -r AGE2/requirements.txt
python -m unittest discover -s AGE2/tests -p "test_*.py" -v
```

测试只使用合成数据，不需要安装游戏。它证明被覆盖的格式分支，不代替真实版本、字体、图片与全路线实机验证。

## English summary

This directory contains the AGE2-specific game assets, FPD/EGPACK tooling, loose-overlay workflow, tests, evidence and postmortems for TDA00–03 and The Imperial Capital Burns. It is technically independent from `rUGP/`. Start with the [workflow](docs/workflow.md) and select a game under [`games/`](games/).
