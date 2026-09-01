# Reverse-engineering and reproducibility index

[Repository README](../../README.md) · [AGE2](../../AGE2/README.md) · [AGE2 postmortems](../../AGE2/docs/postmortems/README.md) · [legacy rUGP](../../rUGP/README.md) · [rUGP postmortems](../../rUGP/docs/postmortems/README.md) · [Prior work](../research/references.md)

This index separates three different claims:

1. **Documented observation** — a result was seen on an exact legal game build and its reusable conclusion was recorded.
2. **Synthetic regression** — public code can reproduce a narrow format/property without copyrighted game data.
3. **End-to-end patch reproduction** — a clean legal installation can be transformed into a tested player package using only documented public steps and separately supplied redistributable inputs.

The first two are substantially present. The third is still partial and varies by game.

## What came from prior work, and what was independently audited

| Area | Prior work used | This project's contribution | Boundary |
| --- | --- | --- | --- |
| rUGP archive model | [GARbro](https://github.com/morkt/GARbro), AFHook and historical rUGP material | A maintained MIT-licensed Python port of GARbro's object-directory reader, plus PF/PM-specific class labels, volume mapping, identities, parent bindings, route census and runtime probes | The direct port and notice are isolated in [`rio_inventory.py`](../../rUGP/tools/catalog/rio_inventory.py); it is a read-only catalogue, not a repacker |
| Hook architecture | [AFHook](https://github.com/eplightning/afhook) | Exact-build proxy, font route, guarded decoded-surface paths, telemetry and fail-closed checks | AFHook supplied a conceptual predecessor, not this runtime's game-specific addresses/tables |
| rUGP terminology | rugptools and alterdec/RioX references | Strict PF/PM format implementations and controlled tests | Licensing is unclear for parts of the historical material, so its source was not copied |
| AGE2 FPD v2 | [FatePackageManager](https://github.com/DaZombieKiller/FatePackageManager) | Strict path/range/stored-and-output-length checks and filtered extraction for this repository | FPD v2 entries expose no per-file CRC; bind the complete `pack.bin` separately, and supply the reviewed `Scrambler.cs` key schedule explicitly |
| Translation/image workflow | Mature patch repositories listed in [references.md](../research/references.md) | Stable identities, review layers, image authority, release and incident policy | No other game's translation or image assets were imported |

See [`THIRD_PARTY.md`](../legal/THIRD_PARTY.md) for license observations and the pinned GARbro, AFHook, rugptools and FatePackageManager revisions. Directly ported or parsed upstream files are additionally bound by content hash; a moving project URL alone is never treated as a build lock.

## Legacy rUGP research map

| Investigation | Durable conclusion | Public implementation/tests | Runtime evidence boundary |
| --- | --- | --- | --- |
| [AGES Internal Error 8311](../../rUGP/docs/postmortems/error-8311.md) | Embedded `U+0000` inside a counted CString is rejected even when static CRsa structure/checksums pass | [`export_translation_sources.py`](../../rUGP/tools/text/export_translation_sources.py), [`test_public_manifest.py`](../../rUGP/tests/text/test_public_manifest.py), [`test_export_translation_sources.py`](../../rUGP/tests/text/test_export_translation_sources.py) | F/M/N differential was an exact-build game experiment; public tests enforce the resulting rule, not the proprietary runtime itself |
| [CRsa/CVM text](../../rUGP/docs/postmortems/crsa-text.md) | Adjacent, direct counted strings and indexed VM pools require different discovery/boundary/capacity rules | [Read-only CRsa extraction guide](../../rUGP/tools/text/README.md), [`extract_crsa_text.py`](../../rUGP/tools/text/extract_crsa_text.py), [`crsa.py`](../../rUGP/formats/rio/crsa.py), [`crsa_vm_pool.py`](../../rUGP/formats/rio/crsa_vm_pool.py), and synthetic tests | Conservative extraction does not infer writer capacity/runtime binding; append/rewire remains experimental |
| [RUO overlay](../../rUGP/docs/postmortems/ruo-overlay.md) | Existing object identities can be redirected to larger complete records, but multiple independent RUOs are not safely stackable | [`ruo.py`](../../rUGP/formats/rio/ruo.py) and its synthetic tests | RUO structure does not prove the embedded record or runtime selection |
| [Cr6Ti extent](../../rUGP/docs/postmortems/cr6ti.md) | Serialized extent and archive placement padding are different quantities; two legacy records use an explicit profile | Cr6Ti codecs/tests and the 1,490-image manifests | Proven PF profiles do not imply every rUGP Cr6Ti variant |
| [CRip007](../../rUGP/docs/postmortems/crip007.md) | The reviewed grayscale route preserves the header contract while using 8-bit channels to avoid antialias quantization | Strict/independent decoders and [`test_crip007_encode.py`](../../rUGP/tests/formats/images/test_crip007_encode.py) | Four exact source profiles do not authorize unrelated flags |
| [CRip008](../../rUGP/docs/postmortems/crip008.md) | Header framing, MSB integer stream, draw rectangle, predictor and kind-specific alpha behavior were reconstructed from samples plus native behavior | [`formats/images/`](../../rUGP/formats/images/), especially [`test_crip008_encode.py`](../../rUGP/tests/formats/images/test_crip008_encode.py) | One passing kind/profile does not authorize every CRip008 flag/profile |
| [Photon font runtime](../../rUGP/docs/postmortems/font-runtime.md) | File coverage, family selection, registry routes, GDI requests and image-rasterized text are separate layers | [`runtime/`](../../rUGP/runtime/), [`test_build.py`](../../rUGP/tests/runtime/test_build.py) | CI proves reproducible binaries and static contracts; actual GDI/game behavior still requires the pinned 32-bit game build |
| [42 shared/common images](../../rUGP/docs/postmortems/shared-common-images.md) | 1,448 translation peers and 42 authenticated common endpoints have different semantic routes | [Photon V6 evidence](../../rUGP/evidence/photon/images/), [route closure](../../rUGP/evidence/photon/routes/README.md), [metadata-only binding audit](../../rUGP/tools/provenance/README.md), verifier, generated runtime tables and runtime source | Route authority does not by itself prove transport fit or visual correctness |
| [ICI resize metadata](../../rUGP/docs/postmortems/ici-resize-metadata.md) | Resizing requires two `CInstallSource` sizes, bitmap growth and preservation of unknown wrapper metadata bits | Recorded clean/candidate differential and independent static decoding; the reusable invariant is documented | The corrected candidates were never launched in AGES and remain release-false; no general production writer is claimed |
| [Image transport/runtime](../../rUGP/docs/postmortems/image-transport-runtime.md) | Correct pixels, semantic endpoint, physical extent/parent and final decoded surface are separate gates | 1,490-route closure, native-capacity census, controlled one-record runtime probes and guarded runtime design | Semantic ownership is complete; clean-install transport and full visual approval remain partial |

The [postmortem index](../../rUGP/docs/postmortems/README.md) states what each incident does and does not prove.

## rUGP extraction and packaging boundary

The conceptual chain is:

```text
ICI/reference graph
  -> RIO volume + offset/extent + parent identity
  -> typed CRsa/Cr6Ti/CRip record
  -> reviewed text or image authority
  -> verified native record, RUO route, or pinned runtime route
  -> game-specific staged roots
  -> deterministic player package
```

Public code now covers the supported ICI directory schema through the [RIO catalogue guide](../../rUGP/tools/catalog/README.md) and [`rio_inventory.py`](../../rUGP/tools/catalog/rio_inventory.py), can feed catalogued CRsa extents into the [read-only text extractor](../../rUGP/tools/text/README.md), and can turn one exact catalogued supported [image record](../../rUGP/formats/images/README.md) into a review PNG. It also covers many record codecs, RUO primitives, runtime builds, evidence verification, the private-snapshot/binding-audit method and final packaging from sealed roots. It does **not yet** turn every clean PF/PM installation into the complete reviewed text/image/font authorities and approved staging roots in one supported chain.

GARbro remains a useful GUI/source reference and may list supported rUGP variants when the base RIO and matching ICI are accepted. Stock builds can reject a target archive or omit newer classes. For a reproducible non-GUI inventory, use the maintained read-only [`rio_inventory.py`](../../rUGP/tools/catalog/rio_inventory.py) port with the matching ICI and explicit RIO volumes; its synthetic tests and attribution are public. A catalogue only locates records: pass supported CRsa extents to the separate read-only extractor and image records to their exact codec. An unsupported record or failed extent check must never be worked around by guessing offsets.

The existing Photon package builder is therefore accurately described as a reproducible transformation of **already sealed, hash-locked input roots**, not yet as the complete public extraction/localization pipeline. See [`rUGP/packaging/README.md`](../../rUGP/packaging/README.md).

A separate strict [Steam locale preflight](../../rUGP/packaging/README.md#steam-locale-preflight-for-a-future-installer) now proves the observed PF/PM app IDs and dual `english` language fields and retains an in-memory seal for immediate pre-write revalidation. It deliberately grants no write authorization and does not infer a policy for Muv-Luv or Alternative.

## AGE2 research map and boundary

The AGE2 path is simpler but still layered:

```text
pack.bin (FPD v2)
  -> filtered root/assets extraction
  -> EGPACK text / WebP image / decrypted UI text / font and config inputs
  -> same-path loose overlay under the exact game's LocalAppData tree
```

- [`AGE2/tools/fpd/`](../../AGE2/tools/fpd/) parses and extracts selected FPD entries with strict checks. It does not claim production `pack.bin` repacking.
- [`AGE2/tools/egpack/`](../../AGE2/tools/egpack/) exports language fields, performs exact-slot replacements and verifies authorized byte changes for the supported TDA00–03 layouts.
- [`AGE2/tools/text/`](../../AGE2/tools/text/README.md) redacts full source dialogue to exact hashes and explicit `text`/`structural_empty` records; the latter are verified empty engine slots and produce no write. The [text-free review ledger](../../AGE2/evidence/translations/review-ledger/README.md) preserves unresolved audit identities/categories without copying either source or target lines.
- [`AGE2/tools/uistring/patch_uistring.py`](../../AGE2/tools/uistring/patch_uistring.py) patches an **already decrypted** UI text file; it does not implement FSNr EPK encryption/decryption.
- TDA00–03 publish maintained dialogue snapshots, but no complete per-game public builder currently converts every reviewed table/image/font input into their historical Release ZIPs.
- The Imperial Capital Burns publishes more image/text inventory and a `build_phase1.py`, but that phase-one builder alone does not reproduce the later full-dialogue beta package.

The [AGE2 incident index](../../AGE2/docs/postmortems/README.md) preserves the
failures and distinctions that changed production rules: the TDA03 cross-game
achievement map, LocalAppData overlay versus `pack.bin`, five structural empty
records, the retired lossy font-glyph workaround, and the difference between a
public translation snapshot and a reproducible historical Release. These are
durable conclusions and regression boundaries, not a dump of every temporary
probe or proprietary input.

## Running the public regressions

From a clean checkout with Python 3.12:

```powershell
python -m pip install -r requirements-dev.txt
python -m unittest discover -s AGE2/tests -p "test_*.py" -v
python -m unittest discover -s rUGP/tests -p "test_*.py" -v
python -m unittest discover -s localization/tests -p "test_*.py" -v
python -m unittest discover -s .github/scripts/tests -p "test_*.py" -v
python -m compileall -q AGE2 rUGP localization .github/scripts
python .github/scripts/verify_repository.py
```

Native Photon runtime reproduction additionally requires Zig 0.16.0 and the commands in [`rUGP/runtime/README.md`](../../rUGP/runtime/README.md). These four test suites require no copyrighted game archives. Conversely, passing them does not constitute player-package or in-game approval.

For a legally held installation and a separately obtained clear-name Steam
depot manifest, [`verify_steam_depot_manifest.py`](../../localization/tools/verify_steam_depot_manifest.py)
provides a read-only file/chunk identity check shared by both engine paths. It
does not authenticate Steam's signature or infer a missing build identity.

## A rigorous reverse-engineering method without AI

The durable method is conventional and repeatable:

1. Freeze exact inputs and hashes.
2. Obtain a trustworthy directory/reference identity before interpreting payload bytes.
3. Compare multiple official samples and executable/runtime behavior.
4. Name fields cautiously and reject ambiguous framing.
5. Build a strict decoder that consumes the complete proven extent.
6. Create tiny synthetic inputs that isolate one branch at a time.
7. Implement only the inverse operations that have independent readback.
8. Change one variable in an exact-build game probe.
9. Record failed hypotheses, the decisive differential, the production rule and a regression test.

An AI agent can shorten searching and coding iterations. It does not replace the sample provenance, controlled differential, independent decoder, exact-build test or human visual/linguistic review.
