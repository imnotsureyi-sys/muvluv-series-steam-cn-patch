# 图片本地化工作流 / Localized image workflow

[返回本地化入口](README.md) · [AGE2 五作 WebP 总览](../AGE2/games/README.md) · [Photon 1,490 图](../rUGP/evidence/photon/images/README.md) · [字体政策](fonts/README.md)

本项目的公开图片范围不只有 PF/PM 的 1,490 项：TDA00–03 与帝都燃烧篇五个历史
Release 另有 730 个 WebP 路径，均已建立逐项路径、尺寸、模式和 SHA-256 清单。730
是 ZIP 成员数，不是独立翻译图数量；实际去重、语言槽、官方 fallback 和权利状态必须
分别判断。

中文制作原则是：先固定源图身份与允许修改区域，再得到无字底，最后使用锁定字体做
确定性排字。GPT Image 2 只用于难以重建的无字底区域，不能让模型直接决定中文文案、
字体、排版或最终像素权威。下文保留英文细则，方便其他语言团队直接复用。

The objective is to replace readable text while preserving every unrelated pixel, alpha edge, state, and layout relationship as closely as the source permits.

## Canonical layers

For each resource keep these concepts distinct, even when some are not publishable:

1. **source identity** — game/version, resource path or record ID, dimensions, mode, and SHA-256;
2. **clean background/object** — source text removed without adding localized text;
3. **localized candidate** — deterministic text rendering over an approved clean layer;
4. **allowed-change mask** — pixels where change is authorized;
5. **diff and review record** — outside-mask equality, alpha/geometry checks, human status, and final hash.

Classify images by functional/style family—button state, name card, telop, map label—not by the date or batch that happened to generate them.

## Preferred reconstruction order

1. Reuse an exact official textless peer or another locale/state with identical art.
2. Reconstruct from a family consensus where multiple states expose the covered pixels.
3. Use deterministic local inpainting for small, texture-consistent regions.
4. Use an image-edit model only for the textless background/object and only inside a constrained mask.
5. Regenerate a full object only when it is visually independent and exact reconstruction is impossible.

Final localized typography should normally be rendered locally with a pinned, redistributable font. This keeps copy, font, size, tracking, stroke, glow, alignment, and line wrapping reviewable and repeatable.

## Image-model request contract

The historical Photon work used GPT Image 2 for selected difficult text-removal edits. A reusable request should say, in substance:

> Edit only the supplied mask. Remove the source-language lettering and reconstruct the obscured background from the surrounding object and supplied family references. Do not add translated text. Preserve canvas size, transparency, composition, colors, borders, shadows, glow, texture, and every pixel outside the mask.

Record model/version as observed, request ID, prompt/template revision, input hashes, mask hash, output hash, time, and review outcome. Never record the API key. Do not automatically retry: a timeout or moderation response may still correspond to a billed or completed request, so put it in an explicit reconciliation queue.

The prompt is evidence, not the asset authority. The reviewed output hash and its later deterministic typography/build steps are authoritative.

## Automated gates

- exact dimensions and color mode;
- unchanged RGBA pixels outside the allowed mask; alpha may change only inside the explicitly authorized text/effect mask;
- no unexpected opaque pixels on transparent canvases;
- expected text region/bounding box and safe margins;
- font coverage and no tofu glyphs;
- family/state consistency;
- hashes and manifest membership.

## Human QA

Review at native scale and magnified scale, on light/dark/checkerboard backgrounds when transparency is involved. Compare adjacent button states and in-game composition. Look for leftover source glyphs, halos, torn edges, color shifts, texture repetition, clipping, incorrect vertical/horizontal layout, and changes outside the intended object.

Rejected candidates remain local. Their reusable lesson belongs in a short failure record; their raw model batches do not belong in the maintained repository.

## Runnable tools

Install the pinned repository dependencies first:

```powershell
python -m pip install -r requirements-dev.txt
```

The maintained commands are under `localization/tools/images/`. They work on
ordinary PNG inputs and never read a game archive directly. Extract/decode the
legal local source with the appropriate AGE2 or rUGP tool first.

### 0. Inventory a historical patch ZIP

For an already published AGE2 patch, build a deterministic image-only
inventory without extracting or committing the binary WebP files:

```powershell
python -m localization.tools.images.inventory_release_images `
  work/patch.zip `
  AGE2/games/<game>/images/release-inventory.json `
  --game-id <game> --engine AGE2 --release-tag <tag> `
  --source-url <release-asset-url> `
  --expect-zip-sha256 <SHA256>
```

The result records archive/payload paths, dimensions, mode, byte count,
content hash and filename locale hint. It is evidence of historical package
contents, not proof that every member was newly localized or separately
redistributable.

### 1. Build a textless layer

For a small, texture-consistent label, give the detector an audited
`left top right bottom` rectangle. The command creates
`clean_background.png`, `old_text_mask.png`, and `qa.json` in a new output
directory; it refuses to reuse an existing directory.

```powershell
python -m localization.tools.images.build_deterministic_textless_background `
  --source work/source.png `
  --asset-id "game:stable-resource-id" `
  --text-patch 120 40 360 105 `
  --output-dir work/textless
```

If automatic neutral-glyph detection is unsuitable, pass a separately reviewed
grayscale mask with `--mask`. Do not use harmonic filling for artwork whose
hidden structure cannot be inferred from its immediate surroundings; use an
official peer/family consensus or a constrained text-removal edit instead.

### 2. Render target-language text deterministically

Create a versioned style profile that pins the variable-font file by SHA-256,
weight, size, tracking, anchor, alignment, fill, strokes, shadow, and font
license identity. The renderer verifies the font hash, renders at 8x, emits the
candidate and allowed-change mask, and restores every outside-mask pixel from
the source before saving.

```powershell
python -m localization.tools.images.render_deterministic_localized_text `
  --source work/source.png `
  --clean-background work/textless/clean_background.png `
  --old-text-mask work/textless/old_text_mask.png `
  --target-text-file work/translation.txt `
  --profile work/style-profile.json `
  --output work/candidate.png `
  --allowed-mask work/allowed-mask.png `
  --qa work/render-qa.json
```

The current `photon-deterministic-*` schema names are retained for compatibility
with the reviewed Photon work. The programs themselves are engine-neutral PNG
authoring tools. A profile is not portable until its font and license can be
obtained lawfully by another builder.

### 3. Prove the single-image invariants

```powershell
python -m localization.tools.images.verify_localized_image_invariants `
  --source work/source.png `
  --candidate work/candidate.png `
  --allowed-mask work/allowed-mask.png `
  --asset-id "game:stable-resource-id" `
  --output work/invariant-qa.json
```

This gate proves size, alpha, mask confinement, and hashes. It deliberately
does not claim that the wording, typography, encoder, resource route, or
in-game composition is correct.

The renderer may legitimately change alpha where a new anti-aliased glyph,
stroke, or shadow lies inside the allowed mask. The invariant gate therefore
requires exact RGBA (including alpha) outside that mask and reports alpha
changes inside and outside separately; it does not require global alpha
identity.

### 4. Check font coverage

Before rendering a batch, audit the visible target-language code points. Name
the translated column explicitly when a table does not use a recognized field:

```powershell
python -m localization.tools.font_coverage `
  work/TargetFont.ttf `
  AGE2/games/tda00/translations/ja-zh-Hans.csv `
  --column cn_text `
  --output work/font-coverage.json
```

For a `.ttc` or `.otc` collection, add the zero-based `--face-index` selected
by the game/profile. The tool intentionally refuses to union cmap coverage
across faces, because that could pass even though no single runtime face has
all required glyphs.

Coverage is only a cmap gate. It does not prove game font selection, shaping,
metrics, wrapping, clipping, or glyphs that were already rasterized into an
image.

### 5. Review a style family

`verify_localized_group_consistency.py` accepts a reviewed JSON specification
containing one approved representative, explicit tolerances, and measured
metrics for every member. It catches outliers but always leaves contact-sheet
review pending:

```powershell
python -m localization.tools.images.verify_localized_group_consistency `
  --spec work/family-spec.json `
  --output work/family-qa.json
```

This last command validates supplied measurements; it does not infer semantic
equivalence or choose the representative. Until a project's metric-extraction
recipe is documented, treat those measurements as reviewed inputs rather than
automatically generated truth.

All commands in this section refuse to overwrite an input or an existing
output/report. Use a new staging path for each run, then promote the reviewed
hash; delete or archive an obsolete staging artifact explicitly rather than
letting a rerun replace it silently.

## Publication boundary

Git should retain the stable copy table, resource identity, source/output
hashes, masks or profiles only when their redistribution has been reviewed,
deterministic tools, and durable QA conclusions. Original game images, failed
candidates, raw model request/response ledgers, credentials, caches, and bulk
comparison galleries remain local. Approved localized image bytes may be
published as a separately hashed Release asset when the project has explicitly
reviewed that redistribution; a manifest alone must not pretend those bytes are
available from a clean clone.
