# Photon 1,490-image locale route closure

`routes_1490.v1.json` is the metadata-only authority that maps every approved
PF/PM Japanese/source asset identity to the endpoint actually selected for a
localized image. It contains 1,448 authenticated translation-peer routes and
42 authenticated shared/common endpoints.

The 42 entries do not mean “fall back to Japanese.” Their authenticated parent
and family evidence proves that no parallel locale endpoint exists and the
same logical resource is shared across locales. The JSON contains locators,
hashes, codec/geometry metadata, success/failure state and proof identities; it
does not contain the official image bytes or native-range binary attachments.
The public file was sanitized with
[`sanitize_route_closure.py`](../../tools/images/sanitize_route_closure.py):
1,355 private `outputs/`/`local-internal/` staging locators were removed while
logical archive filename/offset/extent, byte counts and SHA-256 identities were
retained. `artifact_locator_policy` records that boundary, so no path in this
file should be interpreted as a downloadable build input.

Run the public verifier against the separately locked V6 image authority:

```powershell
python rUGP/tools/images/verify_route_closure.py `
  rUGP/evidence/photon-image-routes-v1/routes_1490.v1.json `
  rUGP/evidence/photon-images-v6/manifest.json `
  --expect-routes-sha256 FCF0BF5CFA30836567722BA3E23D37F7B543D73901163E61E1CC5F5EC2FED579 `
  --expect-images-sha256 428ED401E27ED5A61FD8F8738B381884D8277981140B5A7133DB469ADFCB98F0
```

For slot-map authorities, `evidence_count` counts authenticated structural
observations. `evidence_sha256` is only the de-duplicated list of additional
external evidence artifacts, so its length need not equal `evidence_count`
and it may be empty. The non-empty `slot_map_sha256` binds the structural
evidence set; every hash that is present in `evidence_sha256` is still
validated as SHA-256. Handoff authorities instead bind their proof through
`semantic_peer_proven` and `route_handoff_v2_sha256`.

Passing this check proves complete semantic route closure and the exact
1,448/42 census. It does not promote rows whose own metadata says transport or
runtime authorization is still blocked; record size, native placement, decoded
surface timing, visual QA and package release remain independent gates.
