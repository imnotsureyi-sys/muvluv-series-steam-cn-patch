# Muv-Luv photonmelodies

- Locale in this repository: Simplified Chinese (`zh-Hans`)
- Player-ready release: not yet published
- Canonical runtime-bound table: [`translations/zh-Hans.csv`](translations/zh-Hans.csv), 151 rows
- Reviewed dialogue authorities: [`Adoration + Resurrection`](translations/reviewed/adoration-resurrection.zh-Hans.csv), 8,407 rows; [`Shard of Spacetime`](translations/reviewed/shard-of-spacetime/), 36,176 rows in three RIO-file shards
- Image authority: shared PF/PM [Photon V6 manifest](../../evidence/photon-images-v6/manifest.json)

The 151-row runtime table is a portable production contract: stable object identity, source hashes, localized authority, exact runtime value, controls, capacity and binding route. The larger reviewed tables preserve all 44,583 reviewed Chinese rows with stable identities and exact source hashes, but still require extraction/binding before they become a complete writer input. Complete official source strings remain outside the public tables and must be reconstructed from a legally installed game; see the [reviewed-text evidence](../../evidence/photon-reviewed-text-v1/README.md).

PM's CRsa path exposed the AGES Internal Error 8311 issue; the production rule and controlled evidence are preserved in [`../../docs/postmortems/error-8311.md`](../../docs/postmortems/error-8311.md). Embedded U+0000 padding in a counted CString is forbidden even when all static checksums and extents are correct.

The repository components are not a player installer. PM must pass its own clean-root package rebuild, hash gates, install/rollback and full-route QA before a public patch release.
