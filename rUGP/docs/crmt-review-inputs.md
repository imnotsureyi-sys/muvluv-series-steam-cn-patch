# CRmt 审核导出器：输入契约与合成复现

[CRmt 家族指南](crmt-family.md) · [当前公开清单](../evidence/photon/crmt/README.md)

`rUGP.tools.provenance.export_crmt_review_catalog` 是 **113／114 阶段账本格式的发布适配器**，
不是扫描器、自动语言识别器或安装器。输入需来自相同版本的目录普查及已经完成的人工审核。
它验证输入之间的一致性，不会凭空证明目录是全游戏的完整目录，也不会重新判断翻译是否获批。
不要把任意图片列表改几个标签就称为完成审核。

## 无游戏素材的可运行示例

在仓库根目录安装 `rUGP/requirements.txt`，执行：

```powershell
python -m rUGP.examples.crmt_review_fixture --output-dir output/crmt-synthetic
python -m rUGP.tools.provenance.export_crmt_review_catalog `
  --review output/crmt-synthetic/review.json `
  --expanded output/crmt-synthetic/expanded.json `
  --catalog output/crmt-synthetic/catalog.json `
  --volume-index output/crmt-synthetic/volume-index.json `
  --output output/crmt-synthetic/public.json
python -m unittest rUGP.tests.provenance.test_crmt_review_catalog -v
```

示例生成 3 个逻辑组、4 个物理目标，包含日英分开、日英共用改图、官图保留三种情况，
日文／中文 2 层、英文 1 层，用纯色合成像素构造，不含任何游戏字节。
输出中的审核标签只是模拟输入，并非真实游戏审核。两条生成命令都拒绝覆盖已有输出；
重复运行请自行指定新的目录与输出文件名。

真实的 49 组公开清单不能只靠这个合成示例重建：仍需个人游戏副本、获准的中文稿和私有审核账本。
示例的作用是让干净克隆能复现导出算法及错误拒绝行为，而非伪造真实数据。

## 四个必需输入

JSON 使用 UTF-8；以 `.gz` 结尾时读取 gzip JSON。下面列出导出器消费的字段，其他历史字段可保留但不构成证据。
所有 SHA-256 是 64 位大写十六进制。`path`／`record` 是本机可读文件路径；相对路径按**进程工作目录**解析，
不是按 JSON 所在目录解析。建议生成账本时使用绝对路径；发布输出不包含这些路径。

### `--review`：人工批准的逻辑组

根对象为 `{"rows": [...]}`，每行包含：

- `id`：唯一逻辑组 ID；`category`、`category_label`：分类。
- `games`：适用游戏列表；`relationship`：`有英文本地化` 或 `无英文本地化`。
- `official_japanese`：图片描述；`official_english`：图片描述或 `null`。
- `chinese`：审核批准的候选图片描述；`text`：审核文案。
- `treatment`：`中文改图`、`用户成图`、`复用官方日文` 或 `保留官方日文`。

图片描述为 `{path, image_id, sha256, width, height}`。官方 `image_id` 必须存在于目录资产清单，
尺寸及 PNG 哈希须一致。`chinese.sha256` 绑定批准稿；它是源稿身份，不等于编码后的 PNG 哈希。
`保留官方日文` 无替换记录；`复用官方日文` 则仍需将官图编码为明确目标的替换记录。

### `--expanded`：物理对象与完整缩放层

根对象为 `{"items": [...]}`。每项含与 review 相同的 `id/category/category_label/treatment`，以及 `branches`。
每个分支包含 `game`、`japanese`、`english`、`chinese`；`english` 可为 `null`，其余不可为空。

每个角色包含 `game`、`object_id`、`levels`。层描述为 `{path, sha256, level, width, height}`；
`level` 必须自 0 起按序完整列出，不能只给 L0，不能交换或重复层。层数不要求跨语言相等。

除官图保留外，`chinese` 还必须有：

- `record`：实际编码 CRmt 文件路径；`record_sha256`：整记录哈希。
- `approved_png_sha256`：对应 review 的批准候选哈希。

中文 `object_id` 必须是该分支英文目标；无独立英文时是日文对象。
导出器重新解码 `record`，逐层比较索引、尺寸及完整 RGBA 字节（包括透明像素）。
保留官图则逐层对照官方日文 PNG，不允许填写替换记录冒充保留。
批准稿与记录的关联仍依赖编码账本声明；这里的回读证明是“实际记录等于列出的完整解码图”，
不是对所有历史制图／缩放步骤的重新执行，也不替代视觉批准。

### `--catalog`：原始目录和语言对应证据

根对象有 `objects`、`assets`、`language_pairs` 三个数组：

- `objects`：`{game, crmt_id, volume_index, offset, extent, record_sha256, image_mp,
  external_image, related_crmt_ids, inline_levels}`。其中层为
  `{level, width, height, png_sha256, rgba_sha256}`。
  本适配器只接受 `external_image` 为空且 `related_crmt_ids` 为空的内嵌图片审核子集；其他对象需另行处理。
- `assets`：`{image_id, width, height, png_sha256, physical_uses}`；每个用途为
  `{game, crmt_id, role}`，这里消费 `role: "inline_top"` 的物理用途。
- `language_pairs`：`{pair_id, game, legacy_asset_id, japanese_crmt_id, english_crmt_id,
  japanese_image_ids, english_image_ids, relation}`；对应关系必须为 `confirmed_static_ja_en`。

日英分开组必须以逻辑 ID、游戏、日文对象、英文对象和图像 ID 同时闭合，并覆盖双方全部顶层物理用途。
日英共用组以冻结人工审核的“无英文本地化”结论和官方图的完整物理用途为依据，且不得与目录中的语言配对冲突。
**仅仅没找到配对不是“证明共用”**，此处假设提供的是此前已核实的目录及审核账本。
展开清单缺少任何预期分支、重复目标或换错英文对象均拒绝导出。

### `--volume-index`：分卷名

根对象为 `{"volumes": [{"volume": "example.rio"}, ...]}`。
`objects.volume_index` 是此数组的零起始索引。分卷名使用可移植文件名，不使用本机绝对路径。

## 可选运行证据与输出边界

可重复提供 `--runtime report.json`。目前只适配状态为
`ALL_PENDING_BATCH_NATIVE_CONTROLLED_DISPLAY_PASSED` 的批次：

- `results` 行包含 `asset_id/game/object_id`、`mips_verified`；行状态必须是
  `PASS_NATIVE_OWN_KEY_DISPLAY_AND_ALL_MIP_PAYLOADS`。
- `candidate/encoded_record/screenshot/payload_probe` 均为 `{path, sha256}`，文件须存在且哈希吻合。
- 候选及记录哈希须与当前目标一致。重复或不属于当前审核范围的运行证据拒绝导出。

输出沿用 `photon-crmt-review-catalog/1`，中文层现补充 `rgba_sha256`，与原有 `png_sha256` 并列。
PNG 哈希绑定文件；RGBA 哈希绑定完整解码画布。`input_sha256` 记录输入 JSON 身份。
未提供运行证据不升级为实机通过；截图或探针文件哈希吻合也不是对其内容重新判读。
本工具不证明原剧情所有出场条件，也不授权发布游戏图片或自动生成发布白名单。
