# Sealed generated runtime configuration

## Installed snapshots synchronized on 2026-09-09

The ordinary tables now contain 1,197 PF routes and 1,598 PM routes in the PM
build; the PF build retains its installed companion PM table of 1,594 entries.
Both binaries contain cross-game identities, even when a game does not use
those routes, so the PM table uses explicit `PHOTON_BUILD_PM` conditionals to
preserve each installed binary's inputs. The special table contains 68 entries
(17 PF / 51 PM, including PM-only tutorial entries).

The authority audit used the PF follow-up build's actual **headers** directory,
not its stale `source/generated` copy, and the later PM manual-adoption build's
generated directory. Their raw source hashes are recorded per game in
`provenance.json`; header bytes in Git use LF. All 2,795 selected ordinary rows
match their sealed manifests, and local readback verified 2,791 eligible
ordinary PNG/RGBA identities plus 68 special identities. Four reserved PM
identities were retained without probing their images.

The [synchronization evidence](../../evidence/photon/images/static-review-20260909/runtime-sync.json)
and paired build manifests prove byte-for-byte reproduction of both installed
DLLs with the existing speaker-color candidate flag. No image payload or
private generator input has been added to Git. Uninstalled review drafts are
not promoted into these tables.

## Regeneration boundary

These six headers are reviewed, hash-locked runtime configuration inputs. They
contain identities, sizes, geometry and routing metadata, but no game image
payloads. [`provenance.json`](provenance.json) records each file's exact bytes,
SHA-256, role and any sealed source-manifest identity embedded in the header.

The important limitation is explicit: the public repository currently has no
maintained deterministic generator plus complete publishable input set for
these headers. A clean clone can verify their hashes, stage the authorization
bit in a temporary directory, compile them, and reproduce the normalized DLL;
it cannot regenerate the tables independently. They are therefore classified
as **sealed reviewed configuration**, not as publicly reproducible generated
source.

Changing a header requires more than editing its checksum. A future update
must either publish a deterministic generator and redacted/hash-bound inputs,
or repeat the private authority audit and replace this provenance manifest in
the same reviewed change. Until then, docs and build manifests must preserve
the distinction between “reproducible compile from checked-in configuration”
and “reproducible generation of that configuration.”
