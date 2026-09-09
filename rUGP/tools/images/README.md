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

- [`decode_record.py`](decode_record.py) is the read-only first-step tool: combine an exact ICI-catalogued volume/offset/extent with the matching supported codec and create a review PNG plus portable JSON evidence.
- [`sanitize_route_closure.py`](sanitize_route_closure.py) projects a private route-working set into the path-redacted public route contract.
- [`verify_route_closure.py`](verify_route_closure.py) verifies the frozen 1,490-row Photon route closure.
- [`build_static_review.py`](build_static_review.py) verifies a portable current catalog against explicit local images, then generates categorized HTML cards and an optional streamed full PNG atlas.
- [`verify_pm_production.py`](verify_pm_production.py) reproduces the PM 7/9-hook admission failure and verifies the repair using only a synthetic Windows host and artwork.

Codec implementations and their proven boundaries live in [`rUGP/formats/images`](../../formats/images/README.md). These tools do not infer a locale peer, choose a writer or authorize a package merely because an image decodes successfully.
