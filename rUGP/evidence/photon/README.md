# Photon 文本、图片与路由证据

[返回 rUGP 证据](../README.md) · [PF 项目](../../games/photonflowers/) · [PM 项目](../../games/photonmelodies/)

[CRmt／CRmti／CRimp 专项](crmt/README.md)另行整理当前 49 组图片、日英对应、全层身份和分级验证结果；
不将它与历史 V6 图片数量相加，不分发官方或完整汉化图片。

```text
photon/
├─ text/
│  ├─ reviewed/   57,547 行已审校中文的公开身份与 manifest
│  └─ runtime/    PF 69 行、PM 151 行精确运行时绑定 manifest
├─ images/        历史 V6：PF 636 + PM 854 = 1,490 项图片权威
│  └─ static-review-20260909/ 当前 1,791 项审核选集；独立于历史发行账本
└─ routes/        1,448 个 translation peer + 42 个 shared/common 端点
```

目录使用稳定语义名称，版本号保存在 JSON schema、Git 历史和 Release tag 中，不再每次
升级就在活动路径上增加 `-v1`、`-v6`。图片清单仍可指向历史 V6 Release；移动目录没有
改变该 Release 的内容或标签。

四层证据回答不同问题：

1. `reviewed`：中文是否已经逐句审核；
2. `runtime`：某行文本是否已精确绑定到可写对象；
3. `images`：哪份中文像素/原生记录是权威；
4. `routes`：游戏运行时究竟从哪个 locale/common 端点取得该图片。

任一层通过都不能代替其他层或最终实机 QA。

[当前静态审核选集](images/static-review-20260909/README.md) 另行记录人工登记、候选版本、
角色卡状态和未安装术语修订。它不是对上方历史路由合同的自动更新。

## 2026-09-06 最新合并审计（草稿）

PF 13,025 条、PM 44,698 条的最新中文快照保存在各游戏的
`text-data/layout-baseline/`，不覆盖上方历史 reviewed 表。
参见[完整范围、宽度例外及未接入生产的颜色候选](../../docs/postmortems/pf-pm-layout-audit-20260906.md)。
完整官方日英原文仅保留在本地审计；公开快照记录原文槽校验值。

2026-09-07 已将同一批 57,723 条无损整理成 58 份章节／系统 CSV，作为后续人工编辑入口。
`reviewed` 与 `layout-20260906` 保留为历史证据，不再人工维护第二套正文。
参见[章节 CSV 维护与构建边界](../../docs/chapter-texts.md)。
