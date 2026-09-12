# 核查证据与公开范围

[总览](README.md) · [技术来源分类](provenance.md) · [完整蓝图](blueprint.md)

核查日期：2026-09-12。本目录公开技术结论、来源版本、文件身份和测量结果；不附官方游戏归档、第三方程序、原始私人会话或整套本地工作目录。

## 公开的核查结果

- [正式包路线核查](evidence/release-route-audit.json)：包版本、RIO／ICI 变化、RUO 映射、文本数量、追加区及发布身份。
- [CRip007 离线旧／新实现对比](evidence/crip007-readonly-replay.json)：实际样本身份、像素差异及验证范围。
- [RioX 二进制与六段机器码哈希](evidence/source-chain-summary.json)：来源链报告的选定字段，未附完整历史实验数据。
- [正式包固定文件身份](evidence/shipped-fixed-files.json)：实际 DLL、EXE、字体和 RUO 的大小及 SHA-256。

JSON 保留原核查的数值，移除了本机绝对路径；`local-record/…` 只是历史记录标识，并不是可下载文件。这些摘要是核查结果，不是无需原版输入即可完整重做全部实验的工具包。公开源码和上游固定版本链接分别列在两份正文中。

## 未公开的本地历史记录

下列引用记录了正文采用的历史证据及文件摘要。文件内容未在本次发布，因此读者只能核对公开摘要，不能仅凭 SHA-256 独立验证其内部结论。相应结论在正文中区分历史报告、离线测量和实机结果。

### L01

- 记录：7 月 7 日扩写记录
- 标识：`local-record/artifacts/photon_resource_patch/pf_ui_chn_patch/full_266_ui_text_20260706/single_quicksave_expand_live_test_20260707/live_write_report.json`
- SHA-256：`E16101C6C5C0FC11EE0A047B39D84320B8E067440A1B635F5B7A11D4BBB0F536`

### L02

- 记录：重定位清单
- 标识：`local-record/outputs/rio_rebuild_research_20260810/pf_quicksave_relocated_poc/rio_relocation_manifest.json`
- SHA-256：`0CE0EA335FDA3015816909B6409736A95EDD84988C0A05DCA6A8950B7011B9F1`

### L03

- 记录：RUO 原始研究结论
- 标识：`local-record/outputs/rio_rebuild_research_20260810/RUO_MINIMAL_WRITER_FINDINGS.md`
- SHA-256：`A6F74E573CD2851D7D3BE8A5895DFCDF8C49E89FF963F1C5C6F034293273470A`

### L04

- 记录：v1 使用说明
- 标识：`local-record/outputs/photon_complete_patch_v1/release/README_CN.md`
- SHA-256：`66BEED66E6BF0642CC26C19D8FD6BD10C5121A85E35DAE314DB5C85D22ECCE95`

### L05

- 记录：v1 构建清单
- 标识：`local-record/outputs/photon_complete_patch_v1/release/manifests/release_manifest.json`
- SHA-256：`94EDC2C80F2D0D634C13C67CA7C93BB6388D15610C001B600454F7F78C22AE67`

### L06

- 记录：最终固定范围处理
- 标识：`local-record/local-internal/player-patches-20260910/finalize_text_records.py`
- SHA-256：`AC8E48EF70839ECE2F19C830767C365D84B400C0B1158C10A09EB86E404033CF`

### L07

- 记录：写入组装副本
- 标识：`local-record/local-internal/player-patches-20260910/apply_staged_text.py`
- SHA-256：`97EDEBFD48C438B0B1CB9B0417DC41C360C12A05519DF19B2D07D302E387E3B1`

### L08

- 记录：最终清单
- 标识：`local-record/local-internal/player-patches-20260910/text-records-verified/records.json`
- SHA-256：`45F89987320BFE023DC3991A07D9D329118E470E2EC0666EBB0177C8E1018151`

### L09

- 记录：assemble_archives.py
- 标识：`local-record/local-internal/player-patches-20260910/assemble_archives.py`
- SHA-256：`44C1311DBE497AD10EC60D54648D4CE041F96D51BC60562746EEF68AB69F9CF4`

### L10

- 记录：8 月 27 日安装输入
- 标识：`local-record/outputs/photon_patch_rootfix_v2/staging/packaging/authority_v6_final_partition_install_inputs_20260827_v2_fixed_ici/image_install_inputs_manifest.v1.json`
- SHA-256：`3D015B4BD8080F3D257CD20FC32E9D6BAF2C9B762434D6F5C85908293681DB70`

### L11

- 记录：PF 8 月 28 日清单
- 标识：`local-record/outputs/photon_patch_rootfix_v2/staging/packaging/pf_official_backing_repair_core_20260828_v2_titlefix/package_manifest.v1.json`
- SHA-256：`A05DA49F7DAD55F24EDFBA749E271AAD9BA4F6A4ED010823C77DD149BAFBAAF1`

### L12

- 记录：PM 8 月 30 日清单
- 标识：`local-record/outputs/photon_patch_rootfix_v2/staging/packaging/pm_official_backing_runtime_observed_repair_core_20260830_v3/package_manifest.v1.json`
- SHA-256：`33D8FDFEFFAE40396D2DF4DF097980222A5800176AC4B11D48557C8290D2E3A6`

### L13

- 记录：原始 PhotonCN 构建审计
- 标识：`local-record/outputs/photon_crsa_text_ruo/font_release/PhotonCN-font-audit.json`
- SHA-256：`B62BBFB76B18C37CB5DFE5A6C0A89964C0D24C491EC51F9BFD54917E3FAEF708`

### L14

- 记录：audit_routes.py
- 标识：`local-record/local-internal/photon-provenance-audit-20260912/blueprint/audit_routes.py`
- SHA-256：`E691799D839D646B2BBF884276660CDE372DFAA4754BBC7B5A4857517429A52F`

### L15

- 记录：原始 Cr6Ti 兼容性结论
- 标识：`local-record/outputs/photon_patch_rootfix_v2/staging/cr6ti_engine_compat_audit/FINDINGS.md`
- SHA-256：`7D415F477EC2CAB1C43F696513E980D37216ABC8D85A4E8E7F005E365DC57B95`

### L16

- 记录：官方样本 census
- 标识：`local-record/outputs/photon_patch_rootfix_v2/staging/cr6ti_engine_compat_audit/official_opcode_census.json`
- SHA-256：`9AE56BAAAF3E65CE5DCE172D4F45A2E11E2F667E0825BEB44502AA0DA29BF9B9`

### L17

- 记录：重放脚本
- 标识：`local-record/local-internal/photon-provenance-audit-20260912/full-recheck/replay_crip007.py`
- SHA-256：`2594E2AC6EAEE724D6A3EC7B3D2B9283A44DD979881A8F355DCF34E940BCF6C9`

### L18

- 记录：历史编码审核
- 标识：`local-record/outputs/photon_complete_patch_v1/staging/crip007_encoder_audit/FINDINGS.md`
- SHA-256：`C885A6D927F6FDADB5AE2E32DEA1BB44FEBDC7A063AB2103F623DD6B2DEE4123`

### L19

- 记录：随包 readme
- 标识：`local-record/local-internal/third-party-readonly/RioX-1.2.143.810/static/readme.txt`
- SHA-256：`24E4FD394D5BE5FD246B970E48D6DC03751BCBFBCF5F5440CEECE5323A3FF550`

### L20

- 记录：初期 CRmti 探针
- 标识：`local-record/local-internal/crmt-confession-pilot/probe_crmt.py`
- SHA-256：`3CF09BEDCEF3D7F75CEFDB9345F76ADD6D8218B6B4315154076B9F4B65DED97A`

### L21

- 记录：历史透明段验证
- 标识：`local-record/local-internal/crmt-goal/stage2-review-20260904.v1/transparency-correction-validation-v1.json`
- SHA-256：`4703ED05459BC09F6B5AC0F9F224DF947066AE41FAD6CB0D201245E80DDEC4E8`

### L22

- 记录：基础构建器
- 标识：`local-record/tools/font/build_photoncn_font.py`
- SHA-256：`86D346C0EABE7546C8804B40EF5A1F7086E0AAC9BBBEC307EA359C6625BF5F2B`
