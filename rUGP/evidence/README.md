# Public rUGP evidence

This directory stores compact, durable authority records whose bulk inputs cannot or should not live in Git.

- `photon-text-v1/manifest.json` binds the two canonical runtime-bound PF/PM text tables and the sealed private audit from which they were exported.
- `photon-reviewed-text-v1/` binds 57,547 reviewed Simplified Chinese dialogue rows across the four Photon story groups, redacted to stable IDs, exact source hashes and translated text. These are review/porting authorities, not all runtime bindings.
- `photon-images-v6/` binds the approved 1,490-image release, including the distinction between exact candidate PNGs and native-record authorities.
- `photon-image-routes-v1/` proves the semantic endpoint for all 1,490 images: 1,448 translation peers and 42 authenticated shared/common routes. It does not by itself authorize a packaging/runtime transport.

Evidence is read-only input to a build. New experiments belong in local staging until reviewed and sealed; do not overwrite an existing authority to make a later candidate appear approved.
