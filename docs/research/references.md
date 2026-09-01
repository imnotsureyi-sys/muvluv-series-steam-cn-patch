# 研究参考与采用的经验

[返回研究索引](README.md) · [贡献者与致谢](../project/CONTRIBUTORS.md) · [第三方许可证](../legal/THIRD_PARTY.md)

参考对象按它解决的问题选择，而不是只看 star 数。star 会变化，因此这里固定上游项目、
用途和许可证边界，具体代码复用则在第三方说明中固定提交与哈希。

## rUGP／AGES

- [GARbro](https://github.com/morkt/GARbro)：证明目录导航与具体对象格式处理应分层；其
  RIO/ICI 读取实现是本项目 Python 目录工具的明确来源，但 GARbro 不是 Photon 重封器。
- [AFHook](https://github.com/eplightning/afhook)：展示“补丁制作端 + 游戏内运行时”的
  AGES/rUGP 结构，是 Photon Hook 路线最接近的公开先例。
- [rugptools](https://github.com/osmium76/rugptools)：保存 rUGP、alterdec 等历史术语和
  行为参考；许可证边界不够清晰，因此只研究行为，不复制代码。
- alterdec／RioX 相关历史资料：证明部分资源解码概念早有先例，但不提供现代 PF/PM 的
  完整制作、测试和发布流程。

## AGE2／FPD

- [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager)：FPD v2
  `pack.bin` 结构、密钥调度、提取与实验性重封的主要公开参考。
- [主任保护协会的 ATE 补丁](https://www.moyu.moe/patch/5461/resource)：本项目最初
  AGE2/AGES 汉化与 LocalAppData 覆盖路线的实践启发之一；只致谢思路，不复制受限制的
  补丁内容。

## 成熟补丁仓库

- [thcrap](https://github.com/thpatch/thcrap)：分层语言、补丁数据与运行时分离、版本检查。
- [07th-Mod python-patcher](https://github.com/07th-mod/python-patcher)：玩家优先安装入口，
  开发实现留在后层。
- [Committee of Zero SGHD Patch](https://github.com/CommitteeOfZero/sghd-patch)：补丁内容、
  安装器、启动器和生成资产的可见边界。
- [Tsukihimates](https://github.com/Tsukihimates/Tsukihime-Translation)：`script/`、
  `images/`、系统字符串和工具的实际归档方式；同时提醒清晰结构不自动解决资产权利。
- [VNTranslationTools](https://github.com/arcusmaximus/VNTranslationTools)：明确的提取/
  写回边界与可复用格式工具。
- [Kuriimu2](https://github.com/FanTranslatorsInternational/Kuriimu2)：archive、image、text、
  font 插件边界。

## 本项目没有照搬什么

没有导入其他项目的游戏译文或图片。GARbro 的直接移植被隔离、注明并保留 MIT 声明；
许可证不清楚的仓库不复制源码。哈希门、manifest、语言层、玩家/开发者分离等通用做法
仍必须由本项目对目标游戏重新测试，不能用“别人也这样做”代替证据。

## English summary

References are selected by the problem they solve. GARbro, AFHook, rugptools,
FatePackageManager and mature patch repositories inform narrowly documented
boundaries; only explicitly attributed compatible code is copied.
