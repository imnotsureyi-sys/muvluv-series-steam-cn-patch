# PF / PM 当前静态图审核登记（2026-09-09）

新增 hook 的 [离线检查收尾](../../../../docs/postmortems/offline-hook-audit-20260909.md)
汇总 237 条详细绑定回放、23 个 hook 位置核对、汇编转发及日志对账结果。
实机待采集项单列，不改变本目录原有人工审核与安装状态。

[第一轮用户实机采集](runtime-capture-round-01.json) 记录 PF 95 条、PM 14 条
普通绑定的提交回读成功，PM 另有 4 条仅观察到加载。两款已恢复正常 DLL；
40 条待确认 CRip008 长度身份本轮均未触发，不扩大为全量实机验收。

[`catalog.json`](catalog.json) 是当前审核选集的可移植索引：1,791 项，
其中 1,789 项含图片身份，2 项仅登记状态。它不是全部解包资源数量，也不是
1,791 项全部安装或实机验收通过的声明。原图、人工稿、派生图及本机路径不入 Git。

| 分类 | 项数 |
| --- | ---: |
| 章节与标题 | 110 |
| 设置与角色 | 624 |
| 存档与读档 | 164 |
| 游戏内操作 | 164 |
| 鉴赏与附录 | 126 |
| 小游戏与地图 | 149 |
| 地图与剧情资料 | 86 |
| 剧情图片 | 360 |
| 制作与片尾 | 8 |

## 状态边界

- 人工完成登记共 8 项。G1286、G1287、G4138、G4147、G3698、G3725 六项
  已在本地采用并绑定 8 个载荷路由；尺寸分别为 1075×660、210×123、1280×786，
  每组两项。G1030、G1049 保留状态登记，本清单不含它们的图片身份或安装声明。
- 当前审核稿含 54 项新的术语修订，尚未安装；不得把 `candidate` 当作已发布载荷。
- 四组返回按钮为 PF 粉色 G488/G490、青色 G489/G491，PM 橙色 G1003/G1005、
  绿色 G1004/G1006；本地修订统一字形和位置，保留状态颜色差异。
- PM 启动署名在本地绑定到 G1281 对应资源。公开源码现已同步图片 hook 准入、
  RUO 基址修复及实机图片绑定表；图片文件与玩家发布包仍留在 Git 之外。
- 椭圆角色卡已核对 18 个角色的无圈、白圈、黄圈，共 54 态；原资源另有
  彩峰、柏木、纯夏、霞四个暗态（G1110、G1111、G1114、G1116），合计 58 态。
  不能据此为其余角色臆造暗态；暗态实际解锁条件未在本次确认。
  [逐角色状态矩阵](oval-state-matrix.json) 保存 18 人全部状态的资源 ID，并由测试核对
  58 项无重复、无缺失，均存在于当前审核清单。

## 语言列与复现

`official.jp` / `official.en` 表示确认的官方语言对应；`shared_native` 表示
已核对两语言共用画面，工具会再次比较 RGBA 像素。`unknown` 保留语言未确认的官图。
不再把“官方独立”作为一种语言。缺少对应项只说明未确认配对，不证明另一语言不存在。
35 项同时有确认日文与语言待核官图，审核卡显示额外一列，保留全部来源，避免静默漏图。

用 [`export_static_review`](../../../../tools/provenance/export_static_review.py)
从本地清单投影身份，再用
[`build_static_review`](../../../../tools/images/build_static_review.py) 加显式本地资产映射
生成分类审核页和一张长 PNG。输入哈希、尺寸或共用像素不符就拒绝生成。
审核卡是缩略概览，不能替代原尺寸画面检查。

`source_manifest_sha256` 绑定本地来源清单；`refs` 是游戏卷与记录位置。
`source_resource_catalog_sha256` 绑定提供这些资源位置的源目录；
`sha256` / `size` 绑定审核图片。它们不是运行时 payload FNV 身份，也不能直接
转成安装表。V6 的 1,490 项历史账本继续保留，不用这份新选集覆盖。

## 运行时证据

[`pm-production-regression.json`](pm-production-regression.json) 由公开合成测试生成：
旧准入预期 7 个 hook 时拒绝底层实际安装的 9 个；新准入通过，覆盖直接／索引
surface 提交及正负 pitch。它不执行游戏私有解码器，不等于所有新增资源已实机通过。
完整故障说明见 [PM 图片准入修复](../../../../docs/postmortems/pm-image-admission-20260909.md)。

## 版本与其他 PR

第一轮采集后的 [入口追踪](../../../../docs/postmortems/pending-hook-entry-points-20260909.md)
及 [44 项逐项元数据](pending-script-routes.json) 已补齐：38 项有剧情／辅助脚本引用，
2 项 Logo 仍只有映射关系；PM 3 项仅证明预加载，1 项另有带状态判断的壁纸解锁
调用。40 项均不是已确认故障，44 项的实机待验证状态没有因静态引用而升级。

这份审核选集逐项匹配最新六张人工采用稿和 54 项术语新稿的 SHA-256，没有用
V6 或较早人工预览替代。五处未同步项现已补齐；
[`runtime-sync.json`](runtime-sync.json) 记录两款安装 DLL 的精确重建、普通表来源核对
和本机图片回读。2,791 项普通图及 68 项特殊图的 PNG、RGBA 和尺寸全部匹配；
另外四个保留的 PM 身份未读取图片。初次审计未修改安装目录；随后依据用户的
PM 相册崩溃转储修复语言绑定失效处理，并根据 PF 祭典实机日志修复缓冲区补齐与
局部画面覆盖。只更新两款 DLL，备份和安装回读均匹配。自动化未启动游戏；
用户重新启动后分别确认相册入口和祭典演出已恢复，临时诊断版已撤下。

相册入口曾因同地址 CInt 的类型身份变化而主动终止，见
[崩溃定位与修复边界](../../../../docs/postmortems/pm-album-selector-20260909.md)。
旧版本源码与实机配置身份保留在 `runtime-sync.json` 的 `pm_album_fix` 中；
两款当前构建记录均已更新，PF 旧版本身份在 `pf_festival_fix` 中保留。
[PF 祭典演出修复](../../../../docs/postmortems/pf-festival-presentation-20260909.md)
已完成针对性实机复测，不据此扩大为所有素材或所有局部格式都已实机通过。

默认构建与当前安装构建分开记录。当前安装使用已有的 `--speaker-color-candidate`
选项，重建 DLL 与本机文件逐字节相同：

| 游戏 | 默认构建证据 | 实机配置重建证据 |
| --- | --- | --- |
| PF | [pf-default.build.json](pf-default.build.json) | [pf-installed.build.json](pf-installed.build.json) |
| PM | [pm-default.build.json](pm-default.build.json) | [pm-installed.build.json](pm-installed.build.json) |

PF 安装时实际使用的 `headers` 与其 `source/generated` 副本不同，本次采用前者。
两款 DLL 均编入了跨游戏身份，因此 PM 表保留按编译游戏选择的封存视图：PF 版保留
1,594 个 PM 身份，PM 版为 1,598 个。不能把一个目录里较新的所有文件一并当作
另一款游戏的安装基线。完整源码与封存配置现可重建这两款运行时 DLL；这仍不包含
游戏本体、图片包或独立 PR 的未安装候选，也不自动成为可分发玩家补丁。

文本／字体候选在 [PR #14](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/pull/14)，
术语来源在 [PR #15](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/pull/15)，
CRmt 素材工具在 [PR #16](https://github.com/imnotsureyi-sys/muvluv-series-steam-cn-patch/pull/16)。
这些独立内容没有漏进静态图目录，也不应复制一份形成平行维护版本。
