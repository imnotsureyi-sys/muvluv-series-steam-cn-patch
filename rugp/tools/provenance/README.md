# Photon provenance tools

These commands preserve the chain between private, legally extracted project
inputs and public metadata without copying official game images or containers
into Git. They are fail-closed, never overwrite an existing output, hash their
inputs, redact workstation paths and verify that source files do not change
during a run.

## Verify the published V6 image authority

Download the Photon V6 image ZIP from its GitHub Release, install
`rugp/requirements.txt`, then run:

```powershell
python rugp/tools/provenance/verify_photon_images_v6.py `
  "X:\downloads\MuvLuv_Photon_PF_PM_CN_Images_1490_20260824_v6.zip" `
  --output "X:\work\verification.json"
```

The verifier discovers the archive's top-level prefix, checks the pinned ZIP/authority identities, member counts, paths, hashes, dimensions, RGBA identities, and native-record authority rules. It does not extract into the repository or treat a review PNG as a replacement for a native record. An optional JSON report must be a new path that does not alias the ZIP or manifest; complete report bytes are atomically published.

## Export a sanitized private project snapshot

`export_portable_photon_snapshot.py` converts a production-state manifest and
paired translation ledgers into path-redacted metadata. The default mode copies
no image. `--copy-candidates` may copy only current localized candidate PNGs
into a content-addressed, private LFS-ready snapshot; it never copies official
JP/EN images, Steam RIO volumes, display references, QA screenshots or runtime
backups.

```powershell
python rugp/tools/provenance/export_portable_photon_snapshot.py `
  --workspace-root . `
  --production-state "<private-production-state.json>" `
  --ledger-json "<private-translation-ledger.json>" `
  --ledger-csv "<private-translation-ledger.csv>" `
  --output "<new-private-snapshot-directory>" `
  --expected-state-sha256 "<PINNED_SHA256>" `
  --expected-ledger-json-sha256 "<PINNED_SHA256>" `
  --expected-ledger-csv-sha256 "<PINNED_SHA256>"
```

Add `--copy-candidates` only when producing private controlled storage. The
result is not automatically cleared for a public Git commit or Release.

## Audit CN / official JP / official EN bindings

`audit_photon_locale_bindings.py` verifies the production entries against the
classification manifest, canonical official source tree, the private snapshot
above and, optionally, the public 1,490-route closure. The metadata-only result
records exact native identities, codecs, kinds, extents, hashes and unresolved
gaps while copying zero images.

```powershell
python rugp/tools/provenance/audit_photon_locale_bindings.py `
  --workspace-root . `
  --production-state "<private-production-state.json>" `
  --classification "<private-classification.json>" `
  --canonical-root "<private-canonical-source-root>" `
  --candidate-snapshot "<private-snapshot-directory>" `
  --vertical-evidence-root "<optional-private-evidence-root>" `
  --route-closure rugp/evidence/photon-image-routes-v1/routes_1490.v1.json `
  --output "<new-metadata-only-audit-directory>" `
  --expected-state-sha256 "<PINNED_SHA256>" `
  --expected-classification-sha256 "<PINNED_SHA256>" `
  --expected-route-closure-sha256 "FCF0BF5CFA30836567722BA3E23D37F7B543D73901163E61E1CC5F5EC2FED579"
```

Without `--route-closure`, plausible English peers remain unproven. With it,
the command requires the exact normalized 1,490-source set: 1,448 translation
peers must target a different authenticated native identity, while 42
shared/common routes must prove a common endpoint. A missing decoded target PNG
is reported as missing rather than fabricated.

The private production state, classification, candidate PNGs and official
source images are intentionally not in this repository. Therefore a clean
clone can run the synthetic tests and verify the public route/V6 authorities,
but cannot regenerate this historical binding audit without the separately
held, hash-locked inputs.

## Tests

```powershell
python -m unittest -v `
  rugp.tests.provenance.test_export_portable_photon_snapshot `
  rugp.tests.provenance.test_audit_photon_locale_bindings `
  rugp.tests.provenance.test_verify_photon_images_v6
```
