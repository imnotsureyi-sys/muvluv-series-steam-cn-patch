# 逆向研究与攻克记录

[返回首页](../../README.md) · [English](../en/research-index.md) · [参考项目](references.md) · [仓库边界](repository-architecture.md)

这里不是“最后成功代码”的目录列表，而是结论—证据—限制的索引。每篇复盘尽量保留：最初现象、错误假设、实验方法、根因、最终方案、回归测试，以及仍不能证明的部分。

## 哪些来自前人，哪些是本项目完成的

| 范围 | 主要参考 | 本项目实际增加的部分 |
| --- | --- | --- |
| rUGP 目录与对象定位 | [GARbro](https://github.com/morkt/GARbro) 的 RIO/ICI 读取实现 | 维护的 Python 目录读取器、PF/PM 卷映射、对象身份、父引用、路由普查和严格边界检查 |
| rUGP 运行时思路 | [AFHook](https://github.com/eplightning/afhook)、历史 AGES 本地化经验、[rugptools](https://github.com/osmium76/rugptools) | 针对当前 PF/PM 构建的哈希锁定、字体策略、图片解码表面替换、失败关闭和可复现构建 |
| AGE2 `pack.bin`/FPD | [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager) 的格式注释和 Scrambler | 严格读取/筛选提取、TDA EGPACK 槽位写回、字节级验证、松散覆盖与逐作资产整理 |
| 具体文本和图片格式 | 上述项目提供入口或局部先例 | CRsa/CVM 边界、8311 根因、RUO 使用边界、Cr6Ti/CRip007/CRip008 编码、1,490 图路由闭环等均按本项目样本和运行时重新验证 |

完整提交级来源、许可证与哈希见[参考项目](references.md)和[第三方说明](../legal/THIRD_PARTY.md)。参考某个工具不等于照搬全部实现；每项结论都以代码、测试或记录的实机实验限定适用范围。

## rUGP／AGES

### 从 ICI 到真正资源

[ICI/RIO 目录工具](../../rUGP/tools/catalog/README.md)把 `.rio.ici` 解密并还原为人能检查的对象目录：类名、卷号、偏移、长度、父对象和引用。它只负责“找到对象”；CRsa 文本和 Cr6Ti/CRip 图片仍要交给各自解码器。

```text
ICI 目录元数据
  └─ CodeArcRef：指向某个 RIO 卷的 offset + extent
       └─ CRsa / Cr6Ti / CRip007 / CRip008 的具体字节
            └─ 文本槽或 RGBA 像素
```

### 关键问题复盘

| 问题 | 已确认结论 | 代码/测试入口 |
| --- | --- | --- |
| [AGES Internal Error 8311](../../rUGP/docs/postmortems/error-8311.md) | 带长度的 CString 内混入 `U+0000` 会被运行时拒绝；静态结构和校验和正确仍不足以避免报错 | [文本导出器](../../rUGP/tools/text/export_translation_sources.py)与文本测试 |
| [CRsa/CVM 文本](../../rUGP/docs/postmortems/crsa-text.md) | 相邻直接字符串与索引 VM 字符串池是两种结构，发现、边界与容量规则不能混用 | [只读提取流程](../../rUGP/tools/text/README.md)、[`crsa.py`](../../rUGP/formats/rio/crsa.py)、[`crsa_vm_pool.py`](../../rUGP/formats/rio/crsa_vm_pool.py) |
| [RUO 覆盖](../../rUGP/docs/postmortems/ruo-overlay.md) | 可把既有对象身份重定向到更大的完整记录；多个独立 RUO 不能假设可安全叠加 | [`ruo.py`](../../rUGP/formats/rio/ruo.py)及合成测试 |
| [Cr6Ti](../../rUGP/docs/postmortems/cr6ti.md) | 对象序列化长度与 RIO 放置填充不是同一个数；遗留样本还存在明确配置差异 | [图片格式](../../rUGP/formats/images/) |
| [CRip007](../../rUGP/docs/postmortems/crip007.md) | 已审查灰度路线通过保持头部契约并使用 8 位通道，避免抗锯齿量化损失 | 编解码器与独立回读测试 |
| [CRip008](../../rUGP/docs/postmortems/crip008.md) | 从样本与原生行为重建了头部、MSB 整数流、绘制矩形、预测器及 kind 特有透明度 | [图片格式](../../rUGP/formats/images/)与 kind 2/3 测试 |
| [字体运行时](../../rUGP/docs/postmortems/font-runtime.md) | 字体文件覆盖、家族选择、注册、GDI 请求和图片内文字是不同层，必须分别验证 | [运行时源码](../../rUGP/runtime/)与可复现构建测试 |
| [42 个 shared/common 图片](../../rUGP/docs/postmortems/shared-common-images.md) | 1,448 个 translation peer 与 42 个 common endpoint 使用不同语义路由，不能简单覆盖同一槽 | [1,490 图清单](../../rUGP/evidence/photon-images-v6/)与[路由闭环](../../rUGP/evidence/photon-image-routes-v1/) |
| [ICI 尺寸元数据](../../rUGP/docs/postmortems/ici-resize-metadata.md) | 改尺寸涉及两个 `CInstallSource` 大小、bitmap 增长和未知包装位；只改一处会留下不一致 | 差分记录和独立静态解码；候选未获实机批准 |
| [图片传输与运行时](../../rUGP/docs/postmortems/image-transport-runtime.md) | 像素正确、语义端点正确、物理 extent/parent 正确和最终解码表面正确是四道独立门 | 路由闭环、容量普查、单对象探针与受保护运行时 |

这些结论都带范围。例如“一张 kind=3 图片能往返”不能推出所有 CRip008 kind=3 组合都已支持；新增 flag、画布或 predictor 仍需独立样本和回归测试。

## AGE2

| 问题 | 已确认结论 | 入口 |
| --- | --- | --- |
| FPD／`pack.bin` | FPD 是外层索引/数据容器，提取后才看到 EGPACK、WebP 等内部文件；当前不声称通用重封 `pack.bin` | [FPD 工具](../../AGE2/tools/fpd/) |
| EGPACK 文本槽 | 支持的 TDA 布局可导出字段、按稳定身份生成变更并验证只有授权字节变化 | [EGPACK 工具](../../AGE2/tools/egpack/) |
| [松散覆盖边界](../../AGE2/docs/postmortems/loose-overlay-boundary.md) | 补丁保持 `root/...` 相对路径写入 LocalAppData，游戏优先于 `pack.bin` 读取；Steam 验证不会清理这一层 | [AGE2 工作流](../../AGE2/docs/workflow.md) |
| [结构性空槽](../../AGE2/docs/postmortems/structural-empty-records.md) | 一部分空记录是引擎结构，不是漏译；必须以源身份和字段类型判断，不能按“空白数量”盲补 | 文本导出器与审计表 |
| [失败的字形替换](../../AGE2/docs/postmortems/font-glyph-substitution-retired.md) | 用近似字或字形偷换掩盖缺字会破坏文本权威，现已改为真实字体覆盖门 | [字体检查](../../localization/tools/font_coverage.py) |
| [公开快照与发布包对齐](../../AGE2/docs/postmortems/public-snapshot-release-alignment.md) | 可维护表、旧分支和历史 ZIP 不是天然同一权威，必须逐作以哈希和载荷审计对齐 | [对齐审计](../../AGE2/evidence/translation-snapshots-v1/authority-alignment-audit.md) |
| [TDA03 UI/成就映射](../../AGE2/docs/postmortems/tda03-achievement-uistring.md) | 早期包误用 TDA02 映射；逐作身份验证与实机成就检查必须成为发布门 | 专项复盘与测试 |

## 证据等级

- **合成测试通过：**证明代码处理了明确构造的分支。
- **独立解码/往返通过：**证明编码结果可由第二实现还原。
- **哈希与清单闭环：**证明输入、输出和资源身份没有漂移。
- **锁定版本实机通过：**才证明目标游戏在该版本、路线和环境下接受结果。
- **可发布：**还需安装、卸载、字体许可、内容权利和完整路线 QA；技术成功不自动等于可分发。

## 本地复核

在仓库根目录运行：

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s AGE2/tests -p "test_*.py" -v
python -m unittest discover -s rUGP/tests -p "test_*.py" -v
python -m unittest discover -s localization/tests -p "test_*.py" -v
python -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
python -m compileall -q AGE2 rUGP localization .github/scripts
python .github/scripts/verify_repository.py
```

这些命令不需要游戏原始包。Photon 原生运行时另需 Zig 0.16.0，详见 [`rUGP/runtime/`](../../rUGP/runtime/README.md)。
