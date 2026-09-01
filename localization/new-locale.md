# Starting a new language

This repository contains reusable localization components, but it does **not** yet provide a one-command, end-to-end pipeline from every clean game installation to a finished patch. Treat the existing Simplified Chinese work as an implemented language target and a set of proven components—not as a universal template whose text files can simply be renamed.

## 1. Choose the engine first

| Family | Games currently represented | Reusable pieces | Work still required for a new language |
| --- | --- | --- | --- |
| AGE2 | TDA00–03 and Imperial Capital Burns | EGPACK/FPD helpers, strict local-source/table joins for supported TDA layouts, shared QA rules, selected game builders and release notes | Establish a legal source baseline; adapt the table join to the game's schema; supply language-specific images/fonts; validate loose-overlay behavior and build-specific paths |
| rUGP / AGES | Photon Flowers and Photon Melodies | Read-only ICI/RIO catalogue and conservative CRsa extractor, narrow tested CRsa/RUO record primitives, selected Cr6Ti/CRip007/CRip008 codecs, guarded runtime components, stable public translation manifests, tests | Run the catalogue/text extraction against a legally owned supported build; bind the new translation to stable IDs/hashes; prove a safe writer and RUO/runtime route for each resource; perform real-game text/image/font QA |

Read the relevant workflow before creating files: [AGE2](../AGE2/docs/workflow.md) or [rUGP](../rUGP/docs/workflow.md). The current reproducibility boundary is summarized in the [research index](../docs/research/README.md).

## 2. Create a language identity

Use a BCP 47 language tag such as `ko`, `ru`, or `pt-BR`. Keep it distinct from the existing `zh-Hans` target in:

- translation filenames and columns;
- glossary filenames;
- game/version manifests;
- build output and release name;
- installer destination or selection logic, where the engine permits multiple targets.

Do not overwrite `zh-Hans.csv`, Chinese image masters, or Chinese release metadata to prototype another language.

## 3. Freeze the legal source baseline

Record the storefront, game version/build, executable and container hashes, extraction tool/version, and the exact files used to derive stable identities. Do not commit original proprietary archives, official text dumps, decrypted records, or redistributable-unknown game assets. The public-source boundary is described in [asset and release policy](../docs/project/asset-and-release-policy.md) and each engine's provenance document.

If a clear-name Steam depot manifest for the installed build is already
available to you, the read-only verifier can bind selected local files to its
file/chunk map without publishing local paths:

```powershell
python -m localization.tools.verify_steam_depot_manifest `
  --manifest "X:\DepotCache\example.manifest" `
  --file "obb/pack.bin=X:\Game\obb\pack.bin" `
  --file "Game.exe=X:\Game\Game.exe" `
  --output "X:\Work\steam-input-proof.json"
```

The manifest-relative name on the left must be exact. The command verifies
file size, full SHA-1 and every contiguous chunk SHA-1, records a separate
SHA-256, refuses encrypted/unsafe/ambiguous names, and never overwrites an
existing report. It does **not** download a manifest or validate Steam's
signature/authenticity; provenance of the manifest itself remains a separate
claim. When no reviewed manifest is available, publish explicit file hashes
and mark the Steam build/depot identity unknown instead of guessing it.

Public rUGP and current AGE2 dialogue tables use stable IDs and exact source hashes rather than reproducing the complete official Japanese script. Reconstruct the exact source field from your legal local extraction and stop on a hash mismatch. Other small source-bearing copy/glossary tables are reviewed separately; do not assume one schema or publication rule applies to both engines.

### Create a blank work template

Do not rename a Chinese table and leave Chinese in the new target column. The
engine-neutral exporter removes the existing localized-text column and creates
blank `target_text` cells instead:

```powershell
python -m localization.tools.create_locale_template rUGP/games/photonflowers/translations/reviewed/alternative.zh-Hans.csv work/ru/photonflowers-alternative.csv --target-locale ru --identity-column stable_id --source-hash-column source_text_sha256 --text-column translated_text --keep-column call_order --keep-column rio_file --keep-column scene
```

CSV and TSV schemas vary across AGE2, rUGP review sources and runtime contracts,
so the tool never guesses the identity, source-hash or old-text columns. Declare
them explicitly. Repeat `--keep-column` only for stable, non-prose context that
the new translator actually needs; unlisted columns are removed. Obvious
localized/full-text columns cannot be retained as context. For an AGE2 table,
for example, the mappings are commonly `id`, `source_text_sha256` and
`cn_text`, while `call_order`, `egpack`, `scene`, `speaker_jp`, review status and
audit flags may be deliberately retained when their publication policy allows.

Every output row contains the canonical target locale and an empty target:

```text
<explicitly selected metadata>,target_locale,target_text
```

The tool rejects the existing `zh-Hans` target (including ambiguous bare `zh`
and common `zh-CN`/`zh-SG` aliases), duplicate identities, absent/invalid source
hashes, unsafe column mappings, unknown table formats and any existing output or
manifest. It also writes `<output>.manifest.json`, binding the exact input and
output hashes, column mapping and row count without recording an absolute
workstation path.

This file is a **translation work template**, not a writer input. It does not
contain Japanese dialogue and the removed Chinese translation is not source
authority. Join the legally extracted Japanese field locally by stable identity,
verify its hash, translate from that field, then validate and transform the
reviewed target text into the engine-specific writer schema as a separate step.

## 4. Translate and review

1. Create a locale-specific glossary; the current Chinese file is [`muv-luv.ja-zh-Hans.csv`](glossaries/muv-luv.ja-zh-Hans.csv).
2. Work in stable scene/resource order and preserve identity fields.
3. Follow the target-neutral parts of [translation](standards/translation.md), [terminology](standards/terminology.md), [review](standards/review.md), and [source-data](standards/source-data.md).
4. Define language-specific punctuation, typography, honorific, line-breaking, and naming rules in a locale document. The Chinese style decisions are examples, not requirements for Korean, Russian, or another target.
5. Keep unresolved meanings and technical constraints visible; do not silently use an English slot or an old fan translation as source authority.

## 5. Localize images and fonts

Follow the [image workflow](image-workflow.md): preserve source identity, create a reviewed textless layer where lawful, render localized typography deterministically, and record hashes and allowed-change masks. Publish only assets whose redistribution status has been reviewed.

For rUGP, first obtain an exact volume/offset/extent from the [ICI catalogue](../rUGP/tools/catalog/README.md), then use the [read-only record decoder](../rUGP/formats/images/README.md) to create a review PNG for a supported Cr6Ti/CRip007/CRip008 profile. Do not scan for magic bytes or treat a successfully decoded PNG as proof that the same extent can hold a localized re-encode.

An image-edit model is optional. If one is used for difficult text removal, preserve the request/template revision, model as observed, input/mask/output hashes, and review result. Do not publish API keys or raw failed/scratch batches. Ordinary text translation does not require publishing prompts.

Choose a redistributable font with target-language glyph coverage and include its license/notice in the release. Run the engine-neutral [`font_coverage.py`](tools/font_coverage.py) gate against the reviewed text before packaging. Font-file cmap coverage is only the first gate: family selection, runtime creation route, metrics, wrapping, clipping, and text embedded in images need separate tests.

## 6. Build by resource class

Do not treat “the text works” as proof that images, fonts, and packaging work. Maintain a manifest for each class:

- text identity, controls, capacity, encoding, and final runtime string;
- image identity, dimensions/alpha, route, source and final hashes;
- font file, family name, license, glyph/metric checks, and runtime route;
- package/overlay/runtime files, destinations, supported build hashes, and rollback steps.

AGE2 loose files and rUGP RIO/RUO/runtime routes are unrelated transports. Keep their builders, tests, and release payloads separate even when translation policy is shared.

For rUGP, choose the least invasive proven route for each resource: authenticated native/RUO replacement first, then a runtime hook only where actual font or decoded-surface behavior has been measured. A runtime release must pin host/plugin hashes and architecture, preserve source and a deterministic build command, fail closed on unknown inputs, expose enough telemetry to diagnose selection, and document exact rollback. AGE2's current supported route is static loose overlay; it does not inherit a hook merely because Photon needs one.

## 7. Verify and release

Before publishing, require:

- automated format, identity, control-code, image, font, and packaging checks relevant to the game;
- a clean-install test on every claimed game build;
- real-game passes covering dialogue, menus, save/load, representative image states, fonts, and rollback;
- a file manifest, SHA-256 checksums, exact install/uninstall instructions, supported-build statement, known limitations, and third-party notices;
- a release produced from a tag/commit by a documented command, or an explicit statement that a manual step remains.

If a clean-install-to-release step cannot be reproduced from public files, mark that row **partial** and document the missing source, mapping, builder, or runtime evidence. Do not describe component-level tests as an end-to-end build.
