# 字体资产与发布规则

[返回本地化工作区](../README.md) · [字形覆盖工具](../tools/font_coverage.py) · [rUGP 字体复盘](../../rUGP/docs/postmortems/font-runtime.md) · [AGE2 失败方案复盘](../../AGE2/docs/postmortems/font-glyph-substitution-retired.md)

这里保存字体的选择、来源、许可证和构建规则，不把来源不明的字体二进制直接提交进
Git。字体不是“把一个 TTF 复制进去”这么简单；至少要分别验证字符覆盖、字体家族名、
引擎选字、运行时注册、排版尺寸和实际游戏显示。

## 当前方案

| 范围 | 当前候选 | Git 状态 | 发布要求 |
| --- | --- | --- | --- |
| TDA00–03、帝都燃烧篇 | Source Han Sans SC／思源黑体简体中文 | 不追踪二进制 | 固定上游版本与 SHA-256，字体和完整许可证一起进入 Release，并通过全量译文字形检查 |
| Photon Flowers、Photon Melodies | `PhotonCN-Regular.ttf` 候选及 rUGP 字体运行时 | 不追踪二进制 | 先证明其源字体、修改/子集化过程、家族名和再分发许可，再由版本锁定运行时加载 |

历史测试包曾携带字体但没有把许可证文件一并封装。这也是历史 Release 当前仍标记为
rights review pending 的原因之一；新版本不能沿用这个缺口。

## 一个字体进入正式补丁前必须保存什么

```text
fonts/<family>/
├─ README.md          字体用途、游戏与引擎选择方式
├─ LICENSE.txt        上游完整许可证
├─ source.json        上游 URL、版本、原始 SHA-256
├─ build.ps1 / build.py（若修改或子集化）
└─ coverage.json      对目标译文字符集的检查结果
```

只有许可证明确允许再分发时，字体二进制才进入 Release；是否进入 Git 还要考虑体积与历史
膨胀。若字体经过改名、合并、子集化或修改 OpenType 表，必须同时公开可复现命令和输出
哈希，不能只留下一个无法解释来源的成品。

## 字形覆盖

在仓库根目录执行：

```powershell
python -m localization.tools.font_coverage `
  X:\fonts\candidate.ttf `
  AGE2/games/tda01/translations/ja-zh-Hans.csv `
  --column cn_text
```

覆盖率通过只说明字体“含有这些字”，不说明游戏真的选中了它。AGE2 还要验证松散覆盖
路径、XML／配置和所有 UI；rUGP 还要验证字体注册、家族替换、GDI 请求与 Hook 版本门。

## 多语言团队

韩语、俄语等语言必须重新选择字体并重新跑覆盖检查。中文字体通过，不能推出其他文字
系统也通过；同一字体文件在不同系统上的 fallback 行为也不能作为发布保证。

## English summary

Font binaries are license-gated release inputs, not unexplained repository
artifacts. Record the upstream version, license, hashes, any modification or
subsetting command, coverage result and engine-specific selection path before
distribution.
