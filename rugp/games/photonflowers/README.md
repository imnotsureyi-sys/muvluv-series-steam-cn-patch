# Muv-Luv photonflowers

- Locale in this repository: Simplified Chinese (`zh-Hans`)
- Player-ready release: not yet published
- Canonical runtime-bound table: [`translations/zh-Hans.csv`](translations/zh-Hans.csv), 69 rows
- Reviewed dialogue authorities: [`Alternative`](translations/reviewed/alternative.zh-Hans.csv), 6,033 rows; [`Extra`](translations/reviewed/extra.zh-Hans.csv), 6,931 rows
- Image authority: shared PF/PM [Photon V6 manifest](../../evidence/photon-images-v6/manifest.json)

The 69-row runtime table contains the localized/runtime values and stable IDs, offsets, capacities, controls and source hashes needed by the current exact writer. The larger reviewed tables preserve the complete reviewed Chinese work with stable identities and exact source hashes, but are not a claim that all 12,964 rows are already bound to that writer. All public tables intentionally omit complete official source strings and workstation paths; see the [reviewed-text evidence](../../evidence/photon-reviewed-text-v1/README.md).

PF has its own clean input hashes, generated runtime configuration, package, installer and QA status. It may share reviewed format/runtime code with PM, but PM's successful test never authorizes PF automatically.

The source tree and the separate 1,490-image backup release are not an installable player patch. A PF release requires a clean-clone runtime/package rebuild, exact input validation, downloaded-asset install test and full-route review.
