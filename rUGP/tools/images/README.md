# rUGP image tools

## Current static review

```powershell
python -m rUGP.tools.images.build_static_review --catalog "X:\review-input\catalog.json" --asset-map "X:\review-input\PRIVATE-asset-map.json" --font "X:\fonts\cjk.ttf" --output "X:\review-output\new-review" --atlas --columns 10
python -m rUGP.tools.images.verify_pm_production --zig "X:\zig\zig.exe" --output "X:\checks\new-pm-regression"
```

The first tool needs Pillow and an explicit local font with the required glyphs.
It performs no game discovery or installation. Its schema is documented by the
[current metadata catalog](../../evidence/photon/images/static-review-20260909/README.md).
The private asset map is a JSON object mapping each uppercase SHA-256 to a local
filename (absolute, or relative to that map). Generate it with the
[provenance exporter](../provenance/export_static_review.py). Do not commit it.

Missing, changed or wrongly sized inputs and falsely declared shared language
images fail validation before rendering. Existing output directories are rejected.
If generation fails, its partial output directory is not a finished review: use
a new directory on retry and require `verification.json`. Cards retain equal scale
across each row's language panels but are thumbnails, not native-resolution QA.
An additional unclassified official image is shown in a fourth panel when a
confirmed Japanese reference already occupies the first one. Declared counts
must match the complete row set; an omitted row cannot silently retain stale totals.
The atlas streams horizontal strips; `--columns` accepts 1–10. Derived PNGs and
HTML are local-only artifacts. The HTML uses no external service or library.

The PM regression requires Windows and Zig 0.16.0. It exercises real production
admission and sidecar surface transactions; it does not execute the proprietary
decoder or run a game. See the [failure analysis](../../docs/postmortems/pm-image-admission-20260909.md).

## Resource tools

### Private CRip008 binding replay

```powershell
python -m rUGP.tools.images.replay_crip008_routes --manifest "X:\private\manifest.json" --pf-root "X:\games\PF" --pm-root "X:\games\PM" --zig "X:\zig\zig.exe" --output "X:\checks\new-crip008-replay"
```

Requires Windows, Zig 0.16.0, the private installation manifest with detailed
`runtime_identity` entries, original archives, and installed exact sidecars.
The runner verifies record/payload/PNG hashes and runs the production C
prepare/commit functions for each detailed CRip008 binding. It does not start
or modify a game. Output includes private payloads and executables: keep the
whole output directory local and ignored. A failed run's `progress.json` is
not a completed report; require `verification.json` and zero required failures.

Each binding receives 48 cases: direct/indexed entry, both stride signs, tight
or padded rows, exact length, +2/+3/+4 bytes, wrong identity, and mutation
between prepare/commit. +2/+3 rejection is recorded as a safe coverage gap;
it is not evidence of a retail caller failure. Tests check pixel identity,
outside-rectangle preservation, row/outer guards, and no premature writes.
Runtime initialization, assembly wrappers, original decoders and actual caller
arguments are outside this fixture. See the [49-binding result and remaining
checks](../../docs/postmortems/crip008-batch-replay-20260909.md).

### Remaining offline checks and later capture preparation

```powershell
python -m rUGP.tools.images.replay_cr6ti_routes --manifest "X:\private\manifest.json" --pf-root "X:\games\PF" --pm-root "X:\games\PM" --zig "X:\zig\zig.exe" --output "X:\checks\new-cr6ti-replay"
python -m rUGP.tools.images.verify_native_sites --pf-exe "X:\games\PF\Muv-Luv_PF.exe" --pm-exe "X:\games\PM\Muv-Luv_PM.exe" --zig "X:\zig\zig.exe" --output "X:\checks\new-native-sites"
python -m rUGP.tools.images.prepare_native_diagnostics --zig "X:\zig\zig.exe" --output "X:\checks\new-diagnostics"
python -m rUGP.tools.images.reconcile_native_trace --manifest "X:\private\manifest.json" --trace "X:\capture\session.ndjson" --game PF --capture-build-sha256 <captured-DLL-SHA256> --output "X:\checks\new-trace-report"
```

These commands never install DLLs or launch games. Cr6Ti replay authenticates
payloads and installed sidecars, tests both C decoder entry families, active-scope
and decoder-member recovery, copy and blend modes, stride directions and row
padding. Owner objects and original decoder writes are synthetic. Five standard
records and four inline parents lack predeclared whole-record hashes; payload
SHA-256/FNV and parsed geometry remain required. Newly measured record hashes
are labelled accordingly. Keep output payloads and binaries local and ignored.

The site fixture maps EXE bytes as non-executable data and invokes actual native
and selector preconditions with one-byte negative controls. Four assembly decoder
wrappers run with a synthetic decoder and disabled write gate, checking registers,
return values, stack arguments and in-flight balance. This does not execute the
original decoder or test a live selector owner graph.

Diagnostic preparation builds each game twice using existing instrumentation;
output DLLs are diagnostic-only and remain local. The trace stops at 8,192 events
per process. Before a future capture, select the game/session, record its DLL
identity, and preserve/restore the normal installed file. A capped or untriggered
capture cannot establish full coverage. Only prepare failures and commit outcomes
are logged, so successful prepare is inferred from a verified commit.

Reconciliation requires one identified capture, matches exact identities (plus
labelled CRip008 zero-padding candidates), and credits a commit only with
successful write/readback fields. Identical repeated events are not double-counted;
contradictory sessions are rejected. Unseen, ambiguous and failed bindings remain
separate. See the [completed offline audit](../../docs/postmortems/offline-hook-audit-20260909.md).

### Other tools

- [`decode_record.py`](decode_record.py) is the read-only first-step tool: combine an exact ICI-catalogued volume/offset/extent with the matching supported codec and create a review PNG plus portable JSON evidence.
- [`sanitize_route_closure.py`](sanitize_route_closure.py) projects a private route-working set into the path-redacted public route contract.
- [`verify_route_closure.py`](verify_route_closure.py) verifies the frozen 1,490-row Photon route closure.
- [`build_static_review.py`](build_static_review.py) verifies a portable current catalog against explicit local images, then generates categorized HTML cards and an optional streamed full PNG atlas.
- [`verify_pm_production.py`](verify_pm_production.py) reproduces the PM 7/9-hook admission failure and verifies the repair using only a synthetic Windows host and artwork.

Codec implementations and their proven boundaries live in [`rUGP/formats/images`](../../formats/images/README.md). These tools do not infer a locale peer, choose a writer or authorize a package merely because an image decodes successfully.
