# Photon 1,490 图语义路由闭环

[`routes.json`](routes.json) 把每个 PF/PM 日文/源图片身份映射到游戏实际选择的本地化
端点：1,448 个经过认证的 translation peer，以及 42 个经过认证的 shared/common
端点。

42 个 common 端点不等于“回退日文”。父对象、家族和槽位证据表明这些资源没有平行的
locale 对象，而是在不同语言间共用同一逻辑端点。JSON 保存 RIO 定位、哈希、编解码/
几何信息、成功状态与证明身份，不保存官方图片字节或原生范围附件。

公开文件经过 [`sanitize_route_closure.py`](../../../tools/images/sanitize_route_closure.py)
清除本地 staging 路径，同时保留逻辑卷名、偏移、extent、字节数和 SHA-256。

验证：

```powershell
python rUGP/tools/images/verify_route_closure.py `
  rUGP/evidence/photon/routes/routes.json `
  rUGP/evidence/photon/images/manifest.json `
  --expect-routes-sha256 FCF0BF5CFA30836567722BA3E23D37F7B543D73901163E61E1CC5F5EC2FED579 `
  --expect-images-sha256 428ED401E27ED5A61FD8F8738B381884D8277981140B5A7133DB469ADFCB98F0
```

通过只证明语义端点闭环。对象容量、原生放置、解码表面时机、视觉 QA 和最终封装仍是
独立发布门。

## English summary

`routes.json` proves semantic ownership for all 1,490 images: 1,448 locale
peers and 42 authenticated shared/common endpoints. It contains locators and
proof hashes, not official image bytes, and does not itself authorize runtime
transport or release.
