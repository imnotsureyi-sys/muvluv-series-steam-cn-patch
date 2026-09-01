# Photon reviewed dialogue sources v1

This evidence set publishes 57,547 reviewed Simplified Chinese dialogue rows
for four Photon story groups while omitting the complete official Japanese
text. It is intended for localization review, porting and future patch builds.
It is **not** a claim that every row is already bound to the current runtime.
The separate 69-row PF and 151-row PM `translations/zh-Hans.csv` files remain
the exact runtime-writing contracts.

## Scope

| Public table | Rows |
| --- | ---: |
| [Photonflowers / Alternative](../../games/photonflowers/translations/reviewed/alternative.zh-Hans.csv) | 6,033 |
| [Photonflowers / Extra](../../games/photonflowers/translations/reviewed/extra.zh-Hans.csv) | 6,931 |
| [Photonmelodies / Adoration + Resurrection](../../games/photonmelodies/translations/reviewed/adoration-resurrection.zh-Hans.csv) | 8,407 |
| [Photonmelodies / Shard of Spacetime](../../games/photonmelodies/translations/reviewed/shard-of-spacetime/) | 36,176 in three RIO-file shards |

The Adoration and Resurrection review was sealed as one historical comparison
and therefore remains one public authority.

## Public row contract

| Column | Meaning |
| --- | --- |
| `call_order` | One-based, contiguous encounter order in that review set. |
| `stable_id` | The historical `id`, preserved without rewriting. It binds the RIO, CRsa block and field offset. |
| `rio_file` | RIO segment containing the CRsa block. |
| `scene` | CRsa context (`crsa:<rio>@<block>`), retained for navigation without source prose. |
| `source_text_sha256` | SHA-256 of the exact parsed `jp_text` value, encoded as UTF-8 and rendered as upper-case hex. |
| `translated_text` | Reviewed Simplified Chinese text, including its inline rUGP control markers. |

The exporter requires the private input header to be exactly
`call_order,id,rio_file,scene,speaker_jp,jp_text,cn_text`. It rejects order
gaps, duplicate or malformed identities, RIO/scene mismatches, empty required
values, embedded U+0000, unexpected game prefixes, source-hash drift and
row-count drift. `speaker_jp` and `jp_text` are validation inputs only and are
never written to the public CSV.

`source_text_sha256` is calculated without Unicode normalization and without
rewriting controls or newlines inside a quoted CSV field. The manifest hashes
the exact sealed private CSV bytes before platform line-ending conversion.

## Reproduce or verify

The manifest records the private source byte count, SHA-256 and row count, but
does not publish a Git commit/path/blob locator for complete official Japanese
dialogue. Given the separately held legal comparison CSV matching those gates,
regenerate Alternative to a new path with:

```powershell
python -m rUGP.tools.text.export_reviewed_translation `
  "<private-alternative-comparison.csv>" `
  "<new-alternative.zh-Hans.csv>" `
  --expect-source-sha256 E8379CA3A3109AB71C1143FCE0660356AFDC13EA329D3621C0B6CF65B83354DB `
  --expect-id-prefix pf --expect-rows 6033
```

Existing outputs are refused by default; use `--check` to compare an existing
artifact and `--force` only for explicit atomic replacement. Apply the
corresponding identity and counts from `manifest.json` to the other three sets.
The hash gate fails closed if the private source bytes drift. Public CI verifies
all 57,547 sanitized rows, identities, source hashes and deterministic public
file bytes using copyright-safe fixtures; source-to-public regeneration requires
the sealed private inputs.

These tables do not include the complete official Japanese dialogue and do not
replace the need for a legally obtained game installation. Translation and
other derivative-content rights remain subject to the repository notice and
the applicable rights holders.

The 36,176-row Shard of Spacetime authority is split at exact `rio_file`
boundaries. Its largest current shard is 8,276,041 bytes (78.9% of the hard
10 MiB per-file gate), so CI also applies a 9 MiB early-warning ceiling to every
review table. Do not let `.rio.004` grow silently: before that ceiling, extend
the manifest/tool schema with deterministic contiguous part ranges inside the
same RIO. The canonical combined public CSV is 9,801,647 bytes and the sealed
private source is 11,374,564 bytes; neither combined form belongs in the tracked
tree. Keep the temporary combined output outside the repository (or in an
ignored work directory), then split it before adding files to Git.
After exporting its canonical combined CSV to a new local path, reproduce the
three public files with:

```powershell
python -m rUGP.tools.text.split_reviewed_translation `
  work/shard-of-spacetime.combined.zh-Hans.csv `
  --output-dir work/shard-of-spacetime
```

The manifest records each shard and the SHA-256/byte count of their canonical
combined form. Tests concatenate the shard rows in manifest order and require
that exact historical combined identity.
