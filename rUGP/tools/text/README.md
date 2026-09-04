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
[reviewed-text evidence](../../evidence/photon/text/reviewed/README.md).

## Read-only CRsa extraction

`extract_crsa_text.py` turns catalogued CRsa records into two deliberately different outputs:

- a **local audit CSV** containing source text and the existing adjacent/translation value for legal local review;
- a **portable translation template** containing stable identities, offsets, control metadata and source hashes, but no official source text.

It does not modify an ICI, RIO, RUO or game directory. It is not a CRsa writer and does not turn an unreviewed extraction into a player patch.

## 1. Build the resource catalog

First use the [read-only ICI/RIO catalog](../catalog/README.md). Keep the JSON because it binds each CRsa logical object to a declared volume, byte offset and extent:

```powershell
python -m rUGP.tools.catalog.rio_inventory `
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
python -m rUGP.tools.text.extract_crsa_text `
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
python -m rUGP.tools.text.extract_crsa_text `
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
python -m unittest rUGP.tests.formats.rio.test_crsa_text -v
python -m unittest rUGP.tests.text.test_extract_crsa_text -v
```

No real RIO or official Japanese script is stored in the test tree.

## CRsa display-gap audit and incremental candidates

`audit_crsa_display_gaps` scans every six-byte CRsa signature in all explicitly
bound volumes, independently of ICI membership. It records invalid signatures,
decoded payload identities, both UTF-16 parities, counted fields, exact CVMMsg3
references, unsupported cached-command shapes and class declarations. Its
outputs contain retail text and must stay in an ignored local directory.

`summarize_crsa_display_audit` re-evaluates that cache after parser changes and
exports a per-candidate decision ledger. A byte-pattern hit or unreferenced pool
string is not an authorized translation. It does not prove full Ocean cache
replay or gameplay reachability.

`build_crsa_display_increment` accepts a hash-bound JSON increment and produces
a new cumulative candidate RUO. It appends display strings, changes only selected
translation indices, preserves the original source/pool/suffix and inherited
routes, and checks the encrypted record and RUO readback. It never installs.
Use a current, reconciled base; a frozen overlay must not silently replace newer
routes. Existing reviewed IDs describe their original payload generation: do
not join them to new extraction coordinates without matching source hashes.

## Complete native-field audit for the pinned PF/PM builds

`audit_crsa_native_text` sequentially parses every command, native operation,
shared object cache, CString, pool cell and trailing reference. It consumes the
decrypted `.plain` files and `census.json` from the full-volume display-gap scan,
checks their exact block set, lengths and hashes, and uses the executable-bound
PF/PM descriptor catalog in `crsa_vm_schema.json`. Unknown classes, versions,
field types, invalid primary references or unexplained nonzero suffix bytes
fail the audit without resynchronizing to a later readable string.

```powershell
python -X utf8 -m rUGP.tools.text.audit_crsa_native_text `
  --game pf `
  --cache "X:\Work\crsa-gap\pf-before" `
  --overlay-cache "X:\Work\crsa-deep\pf-effective" `
  --overlay-manifest "X:\Work\crsa-deep\current-overlays.json" `
  --output "X:\Work\crsa-complete\PF"

python -X utf8 -m rUGP.tools.text.audit_crsa_native_text `
  --game pm `
  --cache "X:\Work\crsa-gap\pm-before" `
  --output "X:\Work\crsa-complete\PM"
```

The optional overlay cache must contain the current effective CRsa records and
their hash-bound manifest; a frozen overlay is not a substitute for current
routes. Use a dedicated generated-output directory. The auditor refreshes its
own ledgers on rerun and first marks `audit.json` incomplete, so a failed refresh
cannot leave an older complete result next to partially rewritten output.

`all-native-text.jsonl` preserves the original strings, including empty and
control fields. CSV ledgers distinguish current display-review candidates,
source-language annotations, inline fields, previously reviewed foreign text,
and unreferenced old pool cells. Every message language's primary, annotation
and directive fields are accounted for. Adjacent annotation recovery retains
the stale native index, its actual target, and body-key matching evidence; it
does not silently repair bindings or prove runtime reachability.

All generated ledgers contain retail text and belong in ignored local storage.
The default reviewed inputs are the six maintained PF/PM CSVs. Their identities
are checked against genuine source fields in the same block using the original
UTF-8/control-escaping hash contracts. New audit `field_id` values do not replace
existing stable IDs. The tool changes neither reviewed files nor game files.

The [2026-09-03 complete audit](../../docs/postmortems/crsa-native-text-20260903.md)
records 565 candidate field occurrences, including the first-round 40. The
maintainer-scoped work comprises 40 dialogue/prompt fields plus 265 annotation
fields; 260 armament-name parameters remain byte-identical and are excluded from
omission counts and write actions. The superseded 40-item manifests are rejected
by their old builder. `build_crsa_native_increment` builds the reviewed PF
cumulative RUO. `build_crsa_native_volume_patch` stages the reviewed fixed-extent
PM records in new copies of the affected clean volumes; it rejects inherited RUOs,
record growth and changes outside the selected record extents. The shared writer
uses fixed native or zero-filled pool storage first; a non-empty orphan slot or
pool extension must be named explicitly in the entry and is checked during full
native readback. The reviewed manifests and writeback contract are documented in the
[2026-09-04 increment record](../../docs/postmortems/crsa-native-increment-20260904.md).
