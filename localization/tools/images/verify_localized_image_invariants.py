from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image

from localization.tools.safe_output import write_new_files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def bytes_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def bounding_box(mask: np.ndarray) -> list[int] | None:
    ys, xs = np.where(mask)
    if not len(xs):
        return None
    return [int(xs.min()), int(ys.min()), int(xs.max() + 1), int(ys.max() + 1)]


def verify(
    source_path: Path,
    candidate_path: Path,
    allowed_mask_path: Path,
    output_path: Path,
    *,
    asset_id: str,
) -> dict:
    source_image = Image.open(source_path).convert("RGBA")
    candidate_image = Image.open(candidate_path).convert("RGBA")
    allowed_image = Image.open(allowed_mask_path).convert("L")
    if source_image.size != candidate_image.size:
        raise AssertionError(
            f"size changed: source={source_image.size}, candidate={candidate_image.size}"
        )
    if source_image.size != allowed_image.size:
        raise AssertionError(
            f"mask size differs: source={source_image.size}, mask={allowed_image.size}"
        )

    source = np.asarray(source_image)
    candidate = np.asarray(candidate_image)
    allowed = np.asarray(allowed_image) > 0
    changed_channels = source != candidate
    changed = np.any(changed_channels, axis=2)
    alpha_changed = source[:, :, 3] != candidate[:, :, 3]
    alpha_changed_inside = alpha_changed & allowed
    alpha_changed_outside = alpha_changed & ~allowed
    outside_changed = changed & ~allowed
    inside_changed = changed & allowed
    if alpha_changed_outside.any():
        raise AssertionError(
            "alpha changed outside allowed mask at "
            f"{int(alpha_changed_outside.sum())} pixels, "
            f"bbox={bounding_box(alpha_changed_outside)}"
        )
    if outside_changed.any():
        raise AssertionError(
            f"pixels changed outside allowed mask: {int(outside_changed.sum())}, "
            f"bbox={bounding_box(outside_changed)}"
        )
    if not inside_changed.any():
        raise AssertionError("candidate contains no localized pixel changes")

    source_alpha = source_image.getchannel("A").tobytes()
    candidate_alpha = candidate_image.getchannel("A").tobytes()
    report = {
        "schema": "photon-localized-image-invariants/v1",
        "status": "pass",
        "asset_id": asset_id,
        "source_file": source_path.name,
        "source_sha256": sha256_file(source_path),
        "candidate_file": candidate_path.name,
        "candidate_sha256": sha256_file(candidate_path),
        "allowed_mask_file": allowed_mask_path.name,
        "allowed_mask_sha256": sha256_file(allowed_mask_path),
        "source_size": list(source_image.size),
        "candidate_size": list(candidate_image.size),
        "size_exact": True,
        "source_alpha_sha256": bytes_sha256(source_alpha),
        "candidate_alpha_sha256": bytes_sha256(candidate_alpha),
        "alpha_exact": source_alpha == candidate_alpha,
        "alpha_exact_everywhere": source_alpha == candidate_alpha,
        "outside_allowed_mask_alpha_exact": not alpha_changed_outside.any(),
        "alpha_changed_pixels": int(alpha_changed.sum()),
        "alpha_changed_pixels_inside_allowed_mask": int(alpha_changed_inside.sum()),
        "alpha_changed_pixels_outside_allowed_mask": int(alpha_changed_outside.sum()),
        "alpha_changed_bbox": bounding_box(alpha_changed),
        "alpha_changed_inside_allowed_mask_bbox": bounding_box(alpha_changed_inside),
        "alpha_changed_outside_allowed_mask_bbox": bounding_box(alpha_changed_outside),
        "outside_allowed_mask_exact": True,
        "allowed_mask_pixels": int(allowed.sum()),
        "changed_pixels": int(changed.sum()),
        "changed_pixels_inside_allowed_mask": int(inside_changed.sum()),
        "changed_bbox": bounding_box(changed),
        "changed_channel_counts": {
            "red": int(changed_channels[:, :, 0].sum()),
            "green": int(changed_channels[:, :, 1].sum()),
            "blue": int(changed_channels[:, :, 2].sum()),
            "alpha": int(changed_channels[:, :, 3].sum()),
        },
        "semantic_text_check": "pending_or_separately_user_approved",
        "typography_check": "pending_or_separately_user_approved",
    }
    write_new_files(
        {
            output_path: (
                json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            ).encode("utf-8")
        },
        inputs=(source_path, candidate_path, allowed_mask_path),
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--allowed-mask", type=Path, required=True)
    parser.add_argument("--asset-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(
        args.source,
        args.candidate,
        args.allowed_mask,
        args.output,
        asset_id=args.asset_id,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
