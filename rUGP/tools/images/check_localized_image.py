"""Check a localized PNG's immutable pixels and transparency; never edit images.

Regions are explicitly allowed edits in source-pixel coordinates, with exclusive
right/bottom edges. A passing result is only a mechanical preflight: it cannot
prove translation, typography, layout, pixel-codec readback or runtime acceptance.
No resizing, normalization output, image writing or installation is performed.
"""
from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageChops, ImageDraw

MAX_PIXELS = 16_777_216
MAX_PNG_BYTES = 128 * 1024 * 1024


class LocalizedImageCheckError(ValueError):
    pass


def _require(value: bool, message: str) -> None:
    if not value:
        raise LocalizedImageCheckError(message)


def _load_png(payload: bytes) -> tuple[Image.Image, dict]:
    _require(0 < len(payload) <= MAX_PNG_BYTES, "PNG byte count exceeds the supported bounds")
    try:
        with Image.open(BytesIO(payload)) as opened:
            _require(opened.format == "PNG", "input must be PNG, not another image format")
            _require(opened.mode in ("RGBA", "RGB", "LA", "L", "P"), "unsupported PNG channel mode")
            _require(0 < opened.width * opened.height <= MAX_PIXELS, "PNG canvas exceeds the supported bounds")
            _require(getattr(opened, "n_frames", 1) == 1, "animated PNG is not a single CRmt top-level candidate")
            stores_alpha = "A" in opened.getbands() or "transparency" in opened.info
            rgba = opened.convert("RGBA")  # In-memory comparison only; never published as an edited image.
            mode, dimensions = opened.mode, list(opened.size)
    except (OSError, Image.DecompressionBombError) as exc:
        raise LocalizedImageCheckError("PNG is invalid or cannot be decoded safely") from exc
    alpha = rgba.getchannel("A")
    histogram = alpha.histogram()
    return rgba, {"png_bytes": len(payload), "png_sha256": hashlib.sha256(payload).hexdigest().upper(),
                  "mode": mode, "dimensions": dimensions, "stores_alpha": stores_alpha,
                  "rgba_sha256": hashlib.sha256(rgba.tobytes()).hexdigest().upper(),
                  "alpha_extrema": list(alpha.getextrema()), "transparent_pixels": histogram[0],
                  "nonopaque_pixels": sum(histogram[:255]),
                  "alpha_sha256": hashlib.sha256(alpha.tobytes()).hexdigest().upper()}


def _mask(size: tuple[int, int], regions: Sequence[Sequence[int]]) -> Image.Image:
    _require(isinstance(regions, (list, tuple)), "allowed regions must be a list or tuple")
    _require(len(regions) <= 1024, "too many allowed edit regions")
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for box in regions:
        _require(isinstance(box, (list, tuple)) and len(box) == 4 and all(type(x) is int for x in box),
                 "region requires four integer coordinates")
        left, top, right, bottom = box
        _require(0 <= left < right <= size[0] and 0 <= top < bottom <= size[1],
                 "allowed edit region is empty or outside the source canvas")
        draw.rectangle((left, top, right - 1, bottom - 1), fill=255)
    return mask


def _changed_mask(a: Image.Image, b: Image.Image) -> Image.Image:
    # RGBA difference.getbbox() alone can ignore RGB changes when alpha is equal.
    # Combine all four channels explicitly before counting or finding a bbox.
    channels = ImageChops.difference(a, b).split()
    combined = channels[0]
    for channel in channels[1:]:
        combined = ImageChops.lighter(combined, channel)
    return combined.point([0] + [255] * 255)


def _count(mask: Image.Image) -> int:
    return mask.histogram()[255]


def _bbox(mask: Image.Image) -> list[int] | None:
    box = mask.getbbox()
    return None if box is None else list(box)


def check_localized_png(
    source_png: bytes,
    candidate_png: bytes,
    allowed_regions: Sequence[Sequence[int]],
    *,
    preserve_alpha_everywhere: bool = False,
) -> dict:
    """Return measured facts and a mechanical verdict, without repairing pixels."""
    _require(type(preserve_alpha_everywhere) is bool, "alpha-preservation policy must be boolean")
    source, source_info = _load_png(source_png)
    candidate, candidate_info = _load_png(candidate_png)
    allowed = _mask(source.size, allowed_regions)
    dimensions_match = source.size == candidate.size
    needs_alpha = source_info["nonopaque_pixels"] > 0
    failures = []
    if not dimensions_match:
        failures.append("dimensions_changed")
    if needs_alpha and not candidate_info["stores_alpha"]:
        failures.append("source_transparency_has_no_candidate_storage")
    if needs_alpha and candidate_info["nonopaque_pixels"] == 0:
        failures.append("source_transparency_was_flattened")
    comparison = None
    if dimensions_match:
        changed = _changed_mask(source, candidate)
        inside = ImageChops.multiply(changed, allowed)
        outside = ImageChops.subtract(changed, allowed)
        alpha_changed = ImageChops.difference(source.getchannel("A"), candidate.getchannel("A"))
        alpha_changed = alpha_changed.point([0] + [255] * 255)
        alpha_outside = ImageChops.subtract(alpha_changed, allowed)
        comparison = {"changed_pixels": _count(changed), "changed_bbox": _bbox(changed),
                      "changed_inside_allowed_regions": _count(inside),
                      "changed_outside_allowed_regions": _count(outside), "outside_change_bbox": _bbox(outside),
                      "alpha_changed_pixels": _count(alpha_changed), "alpha_change_bbox": _bbox(alpha_changed),
                      "alpha_changed_outside_allowed_regions": _count(alpha_outside),
                      "candidate_pixels_identical_to_source": _count(changed) == 0}
        if comparison["changed_outside_allowed_regions"]:
            failures.append("protected_rgba_pixels_changed")
        if preserve_alpha_everywhere and comparison["alpha_changed_pixels"]:
            failures.append("alpha_changed_under_global_preservation_policy")
    return {"schema": "rugp-localized-image-preflight/1",
            "status": "FAIL" if failures else "PASS_MECHANICAL_CHECKS_ONLY", "failures": failures,
            "source": source_info, "candidate": candidate_info,
            "policy": {"allowed_regions": [list(box) for box in allowed_regions],
                       "region_coordinates": "source pixels; exclusive right and bottom",
                       "allowed_pixels": _count(allowed), "protected_pixels": source.width * source.height - _count(allowed),
                       "preserve_alpha_everywhere": preserve_alpha_everywhere},
            "dimensions_match": dimensions_match, "pixel_comparison": comparison,
            "pixel_comparison_skipped_reason": None if dimensions_match else "dimension mismatch; no resampling attempted",
            "inputs_modified": False, "images_written": 0, "game_files_written": 0,
            "translation_accepted": False, "layout_accepted": False, "runtime_accepted": False,
            "limits": ["Allowed regions are supplied by the reviewer, not inferred as automatically safe to alter.",
                       "Pixel checks cannot verify Chinese wording, faithful translation, typeface or texture inside allowed regions.",
                       "A mechanical pass does not approve CRmt encoding, RUO publication, installation or runtime display."]}


def _read_guarded(path: Path) -> tuple[bytes, tuple[int, int]]:
    before = path.stat()
    _require(0 < before.st_size <= MAX_PNG_BYTES, "PNG file size exceeds the supported bounds")
    raw = path.read_bytes()
    after = path.stat()
    identity = before.st_size, before.st_mtime_ns
    _require(identity == (after.st_size, after.st_mtime_ns) and len(raw) == before.st_size,
             "input changed while being read")
    return raw, identity


def _region(value: str) -> tuple[int, ...]:
    try:
        result = tuple(int(x.strip(), 0) for x in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("region must be left,top,right,bottom integers") from exc
    if len(result) != 4:
        raise argparse.ArgumentTypeError("region must have exactly four coordinates")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-png", type=Path, required=True)
    parser.add_argument("--candidate-png", type=Path, required=True)
    parser.add_argument("--region", type=_region, action="append", default=[],
                        help="allowed edit rectangle left,top,right,bottom; repeat as needed")
    parser.add_argument("--preserve-alpha-everywhere", action="store_true")
    args = parser.parse_args(argv)
    try:
        source, source_guard = _read_guarded(args.source_png)
        candidate, candidate_guard = _read_guarded(args.candidate_png)
        report = check_localized_png(source, candidate, args.region,
                                     preserve_alpha_everywhere=args.preserve_alpha_everywhere)
        for path, guard in ((args.source_png, source_guard), (args.candidate_png, candidate_guard)):
            stat = path.stat()
            _require((stat.st_size, stat.st_mtime_ns) == guard, "input changed during the image check")
        report["source_file"], report["candidate_file"] = args.source_png.name, args.candidate_png.name
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0 if not report["failures"] else 1
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "INVALID_INPUT", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
