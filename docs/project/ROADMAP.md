# Roadmap

This roadmap separates published player results, reusable components, and work
that still requires exact game inputs or full-route validation.

## Published player results

- TDA00 Simplified Chinese beta0.1
- TDA01 Simplified Chinese beta0.2.2
- TDA02 Simplified Chinese beta0.1
- TDA03 Simplified Chinese beta0.1.6
- The Imperial Capital Burns Simplified Chinese beta0.1

These are historical test packages. New releases must add exact input-version
gates, manifests, font notices, checksums and reliable rollback rather than
assuming the old ZIPs already satisfy the current release policy.

Their current redistribution audit is `pending-remediation`: all five bundles
need font-license correction, some include copied official UI fallbacks, and
the Photon V6 research asset contains 19 byte-identical official-source images.
Replacement or quarantine must be decided before any of them is presented as a
current policy-compliant download.

## Reusable foundation now present

- independent AGE2 and legacy rUGP source/test trees;
- AGE2 portable translation snapshots with explicit structural-empty records,
  a strict local-source-to-EGPACK join and a text-free pending-review ledger;
- a read-only ICI/RIO catalogue, conservative CRsa extraction path and exact
  catalogued-image-to-PNG decoder;
- 57,547 reviewed Photon dialogue rows with source-hash identities;
- 1,490-image authority and semantic route closure;
- tested image codecs, RUO/CRsa primitives and pinned Photon runtime builds;
- reverse-engineering postmortems for 8311, CRsa, RUO, Cr6Ti, CRip007,
  CRip008, fonts, shared/common image routing, ICI resize metadata and image
  transport/runtime failures;
- engine-neutral new-locale, font-coverage and deterministic image workflows.
- an engine-neutral, read-only Steam depot-manifest content check for freezing
  selected local input files when a reviewed clear-name manifest is available;
- a machine-readable index for the five historical player packages, including
  exact archive identities, install roots and known safety limitations.
- a strict, path-redacted PF/PM Steam locale preflight and apply-time recheck
  contract for a future player installer.

## AGE2 priorities

1. Resolve every disagreement between maintained snapshots, historical
   branches and downloaded Release payloads by stable resource identity, and
   manually adjudicate the published text-free symbol/quotation queue.
2. Publish a complete per-game clean-install-to-overlay builder for TDA00–03
   and the later full-dialogue Imperial package, including image/font inputs.
3. Publish successor version-gated, manifest-bound packages only after
   clean-install, rollback and full-route game QA; keep historical ZIP bytes
   immutable and mark superseded versions clearly.

## Photon priorities

1. Convert a legally owned clean PF installation into every reviewed
   text/image/font binding and the sealed PF package roots with no workstation
   paths or undocumented staging step.
2. Repeat that proof independently for PM; shared libraries do not transfer
   package identity, hashes, installer approval or runtime evidence.
3. Build, audit, install, roll back and fully test the downloaded ZIP before
   publishing either game as a player patch.

## Documentation and internationalization

- add locale-specific examples as Korean, Russian or other teams exercise the
  generic template and report real engine constraints;
- keep the machine-readable support matrix and checksums current with every
  new player release;
- keep converting any newly decisive failed experiment into a small
  postmortem plus a regression test, not a dump of workstation probes.

## Repository publication hygiene

- migrate legacy source-bearing Release tags and the public branch history to a
  sanitized root only after making and verifying a recoverable private bundle;
- ask GitHub Support to purge hidden pull-request refs and cached objects that a
  normal branch/tag deletion cannot remove;
- keep Release-page deprecation, compatibility, rollback, and rights warnings
  synchronized with the machine-readable release index.

## Later games

Other Muv-Luv titles, including Sakura no Hana ga Saku Koro and The Queen of
Heart's Hypothesis, may be added only after their engine, source authority,
redistribution boundary, and maintenance owner are known. They are not
currently supported.
