# Photon 文本、图片与路由证据

[返回 rUGP 证据](../README.md) · [PF 项目](../../games/photonflowers/) · [PM 项目](../../games/photonmelodies/)

```text
photon/
├─ text/
│  ├─ reviewed/   57,547 行已审校中文的公开身份与 manifest
│  └─ runtime/    PF 69 行、PM 151 行精确运行时绑定 manifest
├─ images/        PF 636 + PM 854 = 1,490 项图片权威
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
