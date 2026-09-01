# Repository architecture

The public repository is a maintainable source tree, not a mirror of the development workstation.

## Layer model

```text
human workflow                 localization/
                                  |
                 +----------------+----------------+
                 |                                 |
          static AGE2 path                  legacy rUGP path
             AGE2/                               rUGP/
      FPD -> EGPACK/WebP            RIO/ICI/RUO -> records -> runtime
                 |                                 |
          loose overlay                sealed-root package assembler
```

`localization/` may define terminology, review, locale naming, source-table contracts, and image QA. It contains no engine decoder or runtime. `AGE2/` and `rUGP/` are independently testable Python packages and may not import each other.

## What belongs in Git

- reviewed source code and generated source whose generator/input contract is documented;
- exceptionally, sealed generated configuration with no game payload bytes may be retained when an exact public provenance manifest verifies every file and explicitly says that public regeneration is unavailable;
- maintained/reviewed translation tables with stable identities and an honest runtime/release-authority status;
- small synthetic format fixtures generated during tests;
- manifests, hashes, dimensions, and provenance for non-tracked inputs;
- durable postmortems and release notes.

## What belongs in Releases

- player-facing patch ZIPs and installers;
- compiled runtime DLLs paired with corresponding source and build manifests;
- approved, redistribution-reviewed localized image bundles too large for normal Git review;
- machine-readable checksums and a supported-version statement.

## What remains local

- installed games and extracted original resources;
- API credentials, raw model responses, caches, and temporary review sites;
- failed image candidates and one-off bisect scripts after their conclusions are recorded;
- unreviewed package staging trees.

## Engine directories

Each engine owns its `games/`, `tools` or `formats`, and `tests`. rUGP additionally owns `runtime/`, `packaging/`, and `evidence/` because those concepts are part of its current release-candidate path; the clean-install-to-sealed-root bridge remains incomplete. AGE2 deliberately has no runtime-hook directory: its supported patch path is static loose-file overlay.

Each game owns translation data and release status. Sharing a parser never means sharing a package identity or declaring another game tested.

## Promotion test

A local artifact is promoted only when another contributor can identify why it
exists, run it without the original developer's directory layout, and verify a
narrow claim with declared inputs. A directory dump, model ledger, gallery,
probe, or successful one-machine staging tree is not promoted wholesale. Its
durable outcome should become one of: a supported CLI and synthetic regression,
a redacted/hash-bound authority table, a compact evidence manifest, a sealed
configuration with an explicit non-regeneration boundary, or a postmortem that
records the failed hypothesis and production rule. A reproducible compile from
checked-in sealed configuration must never be described as regeneration of
that configuration.
