# rUGP text tools

## Reviewed-table publication

`export_reviewed_translation.py` converts the exact seven-column private review
comparison into the six-column public contract: stable ID, RIO, scene, an exact
UTF-8 source-text SHA-256, and translated text. It rejects schema, order,
identity, source hash and row-count drift and omits `speaker_jp`/`jp_text`.
Read historical inputs as `git:<blob-sha1>` when exact pre-checkout bytes matter.
Use `--check` for a maintained table, a new output path for first creation, or
the explicit `--force` mode for an intentional atomic replacement; silent
overwrite is never the default.

`split_reviewed_translation.py` splits a canonical public table at contiguous
`rio_file` boundaries and proves that the shards reconstruct the input bytes.
The 36,176-row Shard of Spacetime authority uses this layout so individual Git
files remain reviewable. Exact commands and source identities are in the
[reviewed-text evidence](../../evidence/photon-reviewed-text-v1/README.md).

## Read-only CRsa extraction

`extract_crsa_text.py` turns catalogued CRsa records into two deliberately different outputs:

- a **local audit CSV** containing source text and the existing adjacent/translation value for legal local review;
- a **portable translation template** containing stable identities, offsets, control metadata and source hashes, but no official source text.

It does not modify an ICI, RIO, RUO or game directory. It is not a CRsa writer and does not turn an unreviewed extraction into a player patch.

## 1. Build the resource catalog

First use the [read-only ICI/RIO catalog](../catalog/README.md). Keep the JSON because it binds each CRsa logical object to a declared volume, byte offset and extent:

```powershell
python -m rugp.tools.catalog.rio_inventory `
  --ici "X:\Game\example.rio.ici" `
  --main-rio "X:\Game\example.rio" `
  --volume "X:\Game\example.rio.002" `
  --class-name CRsa `
  --output "X:\Work\crsa-catalog.json"
```

Do not publish a generated catalog or source audit until its content rights and path/name exposure have been reviewed.

## 2. Extract slots

Bind every declared volume name explicitly. The left side must match `nodes[].volume` in the catalog; the local file may have any filename:

```powershell
python -m rugp.tools.text.extract_crsa_text `
  --inventory "X:\Work\crsa-catalog.json" `
  --volume "example.rio=X:\Game\example.rio" `
  --volume "example.rio.002=X:\Game\example.rio.002" `
  --game-id example `
  --local-output "X:\Work\crsa-local-source-audit.csv" `
  --template-output "X:\Work\example.translation-template.csv"
```

`--game-id` becomes the stable-ID prefix. Use a short, fixed lowercase identifier and never reuse one identifier for two incompatible game builds.

The command requires each catalog extent to match the strictly decoded CRsa record. It refuses an output that names the inventory, a seed file or a RIO input. Its JSON status contains filenames and structural warnings, not absolute workstation paths or source strings.

Existing output CSVs are also refused by default. Pass `--force` only when you
intend to replace a previous generated audit/template; this flag never permits
overwriting an inventory, seed, or RIO input.

For a repeatable extraction of a pinned game build, add both automation gates:

```powershell
python -m rugp.tools.text.extract_crsa_text `
  --inventory "X:\Work\crsa-catalog.json" `
  --volume "example.rio=X:\Game\example.rio" `
  --game-id example `
  --template-output "X:\Work\example.translation-template.csv" `
  --expect-slots 1234 `
  --fail-on-warning
```

`--expect-slots N` requires exactly `N` extracted slots (`0` is valid when that
is the intended reviewed result). `--fail-on-warning` turns every structural
warning, including unresolved CVM layouts and ambiguous ASCII display pairs,
into a failure. Both checks run before either output is written, so a failed
gate cannot replace a previous file even when `--force` was requested. Establish
the expected count from a reviewed extraction; do not change it merely to make
CI pass.

## Optional source anchors

Conservative scanning intentionally misses some short or structurally ambiguous strings. A reviewed local seed CSV can anchor known source offsets:

```csv
rio_file,block_offset,payload_offset
example.rio,637744,444
```

Pass it with `--seeds`. Decimal and `0x`-prefixed offsets are accepted. Seeds are assertions about an exact source build, not fuzzy search terms; an invalid boundary stops that record instead of silently moving to nearby text.

## Supported read-only structures

- adjacent NUL-terminated UTF-16LE source/translation pairs, including reviewed seed expansion;
- serialized counted Unicode strings parsed by [`crsa.py`](../../formats/rio/crsa.py), including `\|` source/translation fields;
- CVMMsg3 command streams and direct indexed pools parsed by [`crsa_vm_pool.py`](../../formats/rio/crsa_vm_pool.py);
- exact-source deduplication of lower-confidence suffix aliases;
- both even and odd payload parity for NUL-terminated UTF-16 scanning.

The scanner reports ambiguous ASCII display pairs and unresolved CVM layouts. It does not guess a pool base, treat every readable UTF-16 run as dialogue, scan uncatalogued encrypted chunks, infer the active locale route, decide whether a value is safe to rewrite, or generate RUO/runtime files.

The portable template is an **unreviewed extraction template**, not a replacement for the maintained PF/PM production CSVs. A localization team must still verify source hashes, scene/route meaning, target locale, writer mode, capacity/control contract, runtime binding and in-game behavior.
All SHA-256 fields use 64-character upper-case hexadecimal, matching the other
public translation/evidence contracts. In this extractor,
`source_field_sha256` commits to the exact serialized source-field bytes between
`payload_offset` and `source_end`; `source_identity_sha256` commits to the
larger structure-specific identity span; `record_sha256` and `payload_sha256`
commit to the encrypted record and decrypted payload respectively. Do not
compare these directly with a manifest that explicitly hashes parsed UTF-8
text—the representation is part of every hash contract.

## Tests

All tests construct synthetic payloads, encrypted CRsa records, catalogs and RIO files at runtime:

```powershell
python -m unittest rugp.tests.formats.rio.test_crsa_text -v
python -m unittest rugp.tests.text.test_extract_crsa_text -v
```

No real RIO or official Japanese script is stored in the test tree.
