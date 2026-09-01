from __future__ import annotations

"""Recover smooth UI backgrounds beneath rasterized text.

This is intentionally conservative: it detects the neutral glyph core only in
an explicitly supplied text patch, expands that core to cover the original
outline/shadow, and solves a discrete harmonic interpolation inside that mask.
Pixels outside the audited mask, and the complete source alpha channel, remain
byte-identical to the official source image.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

from localization.tools.safe_output import png_bytes, write_new_files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def build_mask(
    source: Image.Image,
    patch: tuple[int, int, int, int],
    *,
    neutral_tolerance: int,
    fill_floor: int,
    fill_ceiling: int,
    dilate: int,
) -> Image.Image:
    rgba = np.asarray(source.convert("RGBA"), dtype=np.uint8)
    x0, y0, x1, y1 = patch
    if not (0 <= x0 < x1 <= source.width and 0 <= y0 < y1 <= source.height):
        raise ValueError("invalid text patch")
    roi = np.zeros(rgba.shape[:2], dtype=bool)
    roi[y0:y1, x0:x1] = True
    rgb = rgba[:, :, :3].astype(np.int16)
    spread = rgb.max(axis=2) - rgb.min(axis=2)
    luminance = rgb.mean(axis=2)
    seed = (
        roi
        & (rgba[:, :, 3] > 0)
        & (spread <= neutral_tolerance)
        & (luminance >= fill_floor)
        & (luminance <= fill_ceiling)
    )
    if not seed.any():
        raise ValueError("no neutral glyph-core pixels found in text patch")
    mask = Image.fromarray(seed.astype(np.uint8) * 255, "L")
    if dilate:
        mask = mask.filter(ImageFilter.MaxFilter(dilate * 2 + 1))
    mask_array = np.asarray(mask, dtype=np.uint8).copy()
    mask_array[~roi] = 0
    return Image.fromarray(mask_array, "L")


def harmonic_inpaint(
    source_rgb: np.ndarray,
    mask: np.ndarray,
    *,
    max_iterations: int,
    tolerance: float,
) -> tuple[np.ndarray, int, float]:
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("tolerance must be finite and positive")
    if not mask.any():
        raise ValueError("text mask is empty")
    if mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any():
        raise ValueError("text mask must not touch the canvas boundary")
    work = source_rgb.astype(np.float64).copy()

    # Seed holes from the closest known samples on the same row. This avoids
    # letting the original glyph colors influence the iterative solution.
    width = work.shape[1]
    x_axis = np.arange(width)
    for y in range(work.shape[0]):
        hole_x = np.flatnonzero(mask[y])
        if not len(hole_x):
            continue
        known_x = np.flatnonzero(~mask[y])
        for channel in range(3):
            work[y, hole_x, channel] = np.interp(
                hole_x, known_x, work[y, known_x, channel]
            )

    last_delta = float("inf")
    for iteration in range(1, max_iterations + 1):
        averaged = (
            work[:-2, 1:-1]
            + work[2:, 1:-1]
            + work[1:-1, :-2]
            + work[1:-1, 2:]
        ) * 0.25
        interior_mask = mask[1:-1, 1:-1]
        old = work[1:-1, 1:-1][interior_mask].copy()
        work[1:-1, 1:-1][interior_mask] = averaged[interior_mask]
        last_delta = float(np.max(np.abs(work[1:-1, 1:-1][interior_mask] - old)))
        if last_delta <= tolerance:
            break
    else:
        raise RuntimeError(
            f"harmonic interpolation did not converge within {max_iterations} iterations; "
            f"final delta={last_delta}, tolerance={tolerance}"
        )
    return np.clip(np.rint(work), 0, 255).astype(np.uint8), iteration, last_delta


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--asset-id", required=True)
    mask_source = parser.add_mutually_exclusive_group(required=True)
    mask_source.add_argument("--text-patch", nargs=4, type=int)
    mask_source.add_argument(
        "--mask",
        type=Path,
        help="Use an externally audited old-text mask instead of detecting one",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--neutral-tolerance", type=int, default=14)
    parser.add_argument("--fill-floor", type=int, default=210)
    parser.add_argument("--fill-ceiling", type=int, default=255)
    parser.add_argument("--dilate", type=int, default=9)
    parser.add_argument("--max-iterations", type=int, default=4000)
    parser.add_argument("--tolerance", type=float, default=0.01)
    args = parser.parse_args()

    if args.output_dir.exists():
        raise FileExistsError(args.output_dir)
    source = Image.open(args.source).convert("RGBA")
    if args.mask:
        mask_image = Image.open(args.mask).convert("L")
        if mask_image.size != source.size:
            raise ValueError("external mask dimensions differ from source")
        if not mask_image.getbbox():
            raise ValueError("external mask is empty")
    else:
        mask_image = build_mask(
            source,
            tuple(args.text_patch),
            neutral_tolerance=args.neutral_tolerance,
            fill_floor=args.fill_floor,
            fill_ceiling=args.fill_ceiling,
            dilate=args.dilate,
        )
    source_array = np.asarray(source, dtype=np.uint8)
    mask = np.asarray(mask_image, dtype=np.uint8) > 0
    recovered_rgb, iterations, final_delta = harmonic_inpaint(
        source_array[:, :, :3],
        mask,
        max_iterations=args.max_iterations,
        tolerance=args.tolerance,
    )
    output_array = source_array.copy()
    output_array[mask, :3] = recovered_rgb[mask]
    output = Image.fromarray(output_array, "RGBA")

    outside_exact = np.array_equal(output_array[~mask], source_array[~mask])
    alpha_exact = np.array_equal(output_array[:, :, 3], source_array[:, :, 3])
    if not outside_exact or not alpha_exact:
        raise AssertionError("source preservation invariant failed")

    output_path = args.output_dir / "clean_background.png"
    mask_path = args.output_dir / "old_text_mask.png"
    qa_path = args.output_dir / "qa.json"
    output_payload = png_bytes(output)
    mask_payload = png_bytes(mask_image)
    report = {
        "schema": "photon-deterministic-textless-background/v1",
        "asset_id": args.asset_id,
        # Keep durable QA portable.  Identity comes from asset_id + hashes;
        # workstation directories are deliberately not provenance.
        "source_file": args.source.name,
        "source_sha256": sha256_file(args.source),
        "output_file": output_path.name,
        "output_sha256": sha256_bytes(output_payload),
        "old_text_mask_file": mask_path.name,
        "old_text_mask_sha256": sha256_bytes(mask_payload),
        "old_text_mask_pixels": int(mask.sum()),
        "old_text_mask_bbox": list(mask_image.getbbox() or []),
        "text_patch": args.text_patch,
        "external_mask_file": args.mask.name if args.mask else None,
        "external_mask_sha256": sha256_file(args.mask) if args.mask else None,
        "detector": {
            "neutral_tolerance": args.neutral_tolerance,
            "fill_floor": args.fill_floor,
            "fill_ceiling": args.fill_ceiling,
            "dilate": args.dilate,
        },
        "solver": {
            "method": "four-neighbour discrete harmonic interpolation",
            "iterations": iterations,
            "final_max_delta": final_delta,
            "tolerance": args.tolerance,
        },
        "size_exact": output.size == source.size,
        "outside_old_text_mask_source_rgba_exact": outside_exact,
        "outside_old_text_mask_source_alpha_exact": True,
        "source_alpha_exact_everywhere": alpha_exact,
        "api_called": False,
    }
    qa_payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_new_files(
        {
            output_path: output_payload,
            mask_path: mask_payload,
            qa_path: qa_payload,
        },
        inputs=(args.source, *((args.mask,) if args.mask else ())),
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
