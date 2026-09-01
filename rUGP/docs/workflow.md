# rUGP workflow

This is the required investigation/build sequence, not a claim that one public command currently performs every step. The read-only catalog and supported CRsa extraction stages are public, but the repository does not yet bind every PF/PM payload into the final approved staging roots; [the research index](../../docs/research/README.md) records the exact boundary.

## 1. Freeze a clean installation

Record SHA-256 and byte size of the executable, every RIO volume, ICI, original resource DLL, and existing RUO state. Work from a copy or read-only handle. A Steam update creates a new unsupported baseline until re-audited.

When a matching clear-name Steam depot manifest is available, the
engine-neutral [`verify_steam_depot_manifest.py`](../../localization/tools/verify_steam_depot_manifest.py)
can additionally prove selected local files against its complete file/chunk
map. This is a content check, not Steam-signature authentication; see the
[source-baseline instructions](../../localization/new-locale.md#3-freeze-the-legal-source-baseline).

## 2. Decode the catalog

When an exact reader build is known to accept the target, use a verified ICI/RIO reader such as GARbro for an initial listing, then preserve the decoded class, logical path, volume, offset, extent, and parent/reference identity. The public [`rio_inventory.py`](../tools/catalog/README.md) supplies a read-only, portable catalog route for its supported ICI schema. Stock GARbro can reject PF/PM archives or lack a target class; that is a compatibility result, not permission to guess offsets. A listing is a map, not an extracted final asset.

## 3. Decode by record type

Route only a strictly identified record to `formats/images/` or `formats/rio/`. The [read-only CRsa text CLI](../tools/text/README.md) accepts catalogued extents and emits a local source audit or source-hash template for adjacent, counted-CString and supported CVMMsg3 layouts. The [image decoder](../formats/images/README.md) accepts one exact catalogued Cr6Ti/CRip007/CRip008 extent and creates a review PNG without writing the RIO. Warnings, PNGs and unreviewed templates are not writer authorization. Preserve a stable ID and source hash. Do not reinterpret every `00 04 45` object as Cr6Ti.

## 4. Author content

Translate from Japanese source authority and follow [`../localization/`](../../localization/). For images, approve a textless layer and deterministic typography before encoding. Preserve source codec where supported; a successful kind=3 test proves the implemented kind=3 subset, not every flag/profile in the world.

## 5. Encode and prove round trips

- decode official record and validate full extent;
- encode the localized candidate using the original structural template;
- decode the result with an independent path;
- compare RGBA/text, geometry, alpha, controls, untouched bytes and reference bindings;
- fail closed on an unsupported branch or oversize transport.

## 6. Select the runtime transport

Prefer a native/in-place or RUO route where the authenticated translation/common endpoint is known. Use the runtime only for routes whose actual decoded-surface or font behavior was separately measured. Never substitute the Japanese source slot just because it is easy to locate.

## 7. Package from a clean root

The Photon builder accepts explicit clean, sealed-runtime, stock-fixed, final-PF and final-PM roots. It validates pinned hashes, requires a fixed `SOURCE_DATE_EPOCH`, records the Python/NumPy/zlib environment, creates deterministic block deltas and ZIP metadata, and emits PF/PM as separate packages. A future player installer must additionally run and immediately revalidate the strict [Steam locale preflight](../packaging/README.md#steam-locale-preflight-for-a-future-installer); a saved JSON report alone is not write authorization. See [`../packaging/README.md`](../packaging/README.md).
