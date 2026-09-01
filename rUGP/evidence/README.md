# rUGP 公开证据

[返回 rUGP](../README.md) · [Photon 证据总入口](photon/README.md)

这里保存体积较小、能够长期复核的权威记录。大体积输入、游戏原件和临时实验不进入
Git；经过审核的结论则不能只留在聊天或本地 `outputs/` 中。

当前公开范围集中在 [`photon/`](photon/)：

- `text/runtime/manifest.json`：绑定 PF 69 行、PM 151 行精确运行时文本表；
- `text/reviewed/`：绑定四组故事共 57,547 行已审校中文；
- `images/`：绑定 1,490 项图片权威及研究资产 Release；
- `routes/`：证明 1,448 个 translation peer 与 42 个 shared/common 端点。

证据是构建的只读输入。新候选先在本地 staging 验证，审核通过后生成新的清单或 Git
提交；不能覆盖旧清单来让后来的实验看起来像早已批准。

## English summary

This directory stores compact, durable authorities for runtime text, reviewed
dialogue, localized images and semantic routes. Bulk private inputs and game
files stay outside Git; evidence is immutable build input, not scratch space.
