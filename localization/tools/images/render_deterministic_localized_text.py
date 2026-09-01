from __future__ import annotations

"""Deterministic, family-profile-driven localized text compositor.

The source bitmap remains authoritative.  The compositor may only replace
pixels inside the union of the supplied old-text mask and the newly rendered
text/effect mask.  Pixels outside that union are copied byte-for-byte.
"""

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from localization.tools.safe_output import png_bytes, validate_new_outputs, write_new_files


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def rgba(value: Iterable[int]) -> tuple[int, int, int, int]:
    result = tuple(int(item) for item in value)
    if len(result) != 4 or any(not 0 <= item <= 255 for item in result):
        raise ValueError(f"invalid RGBA value: {result!r}")
    return result  # type: ignore[return-value]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_profile(profile: dict[str, Any]) -> None:
    if profile.get("schema") != "photon-deterministic-text-style/v2":
        raise ValueError("unsupported or missing profile schema")
    license_info = profile.get("license")
    if not isinstance(license_info, dict) or not license_info.get("font"):
        raise ValueError("V2 profiles must identify the font family")
    if license_info.get("spdx") != "OFL-1.1":
        raise ValueError("V2 profiles must use an OFL-1.1 font")
    render = profile["render"]
    if int(render.get("supersample", 0)) != 8:
        raise ValueError("V2 profiles must use exactly 8x supersampling")
    if not (0 < float(render["scale_x"]) <= 2):
        raise ValueError("scale_x must be in (0, 2]")
    if int(render["font_weight"]) < 1:
        raise ValueError("font_weight must be explicit and positive")
    if not render.get("font_path"):
        raise ValueError("font_path must be explicit")
    font_sha256 = str(render.get("font_sha256", "")).upper()
    if len(font_sha256) != 64 or any(char not in "0123456789ABCDEF" for char in font_sha256):
        raise ValueError("font_sha256 must be an explicit 64-character hexadecimal digest")
    if render.get("horizontal_align") not in ("center", "left", "right"):
        raise ValueError("unsupported horizontal_align")
    if render.get("vertical_align") not in ("center", "top", "bottom", "baseline"):
        raise ValueError("unsupported vertical_align")
    if render.get("vertical_align") == "baseline" and "baseline_px" not in render:
        raise ValueError("baseline alignment requires explicit baseline_px")
    rgba(render["fill"]["top_rgba"])
    rgba(render["fill"].get("bottom_rgba", render["fill"]["top_rgba"]))
    if render["fill"].get("gradient_scope", "canvas") not in ("canvas", "glyph_bbox"):
        raise ValueError("fill.gradient_scope must be 'canvas' or 'glyph_bbox'")
    gradient_gamma = float(render["fill"].get("gradient_gamma", 1.0))
    if not np.isfinite(gradient_gamma) or gradient_gamma <= 0:
        raise ValueError("fill.gradient_gamma must be a finite positive number")
    for layer in render.get("strokes", []):
        rgba(layer["rgba"])
        if float(layer["width_px"]) < 0:
            raise ValueError("stroke width cannot be negative")
    if render.get("shadow"):
        rgba(render["shadow"]["rgba"])


@lru_cache(maxsize=128)
def load_variable_font(
    path: Path,
    size_px: float,
    weight: int,
    supersample: int,
    expected_sha256: str,
) -> tuple[ImageFont.FreeTypeFont, dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    actual_sha256 = sha256_file(path)
    if actual_sha256 != expected_sha256.upper():
        raise ValueError(
            f"font SHA-256 mismatch for {path}: expected {expected_sha256.upper()}, "
            f"got {actual_sha256}"
        )
    font = ImageFont.truetype(str(path), max(1, round(size_px * supersample)))
    axes = font.get_variation_axes() if hasattr(font, "get_variation_axes") else []
    if not axes:
        raise ValueError(f"profile requires a variable font, but {path} has no axes")
    weight_axis_indices = []
    for index, candidate in enumerate(axes):
        name = candidate.get("name", b"")
        if isinstance(name, bytes):
            name = name.decode("ascii", errors="replace")
        if str(name).casefold() == "weight":
            weight_axis_indices.append(index)
    if len(weight_axis_indices) != 1:
        raise ValueError(
            f"font must expose exactly one Weight variation axis; found {len(weight_axis_indices)}"
        )
    weight_axis_index = weight_axis_indices[0]
    axis = axes[weight_axis_index]
    low, high = int(axis["minimum"]), int(axis["maximum"])
    if not low <= weight <= high:
        raise ValueError(f"weight {weight} outside font range {low}..{high}")
    axis_values = [float(candidate["default"]) for candidate in axes]
    axis_values[weight_axis_index] = float(weight)
    font.set_variation_by_axes(axis_values)
    lock = {
        "file": path.name,
        "sha256": actual_sha256,
        "weight_axis_index": weight_axis_index,
        "weight_axis_name": "Weight",
        "weight_axis_minimum": low,
        "weight_axis_default": float(axis["default"]),
        "weight_axis_maximum": high,
        "applied_weight": weight,
        "applied_axis_values": axis_values,
    }
    return font, lock


class TextMask:
    def __init__(
        self,
        image: Image.Image,
        width: int,
        height: int,
        baseline_from_top_hi: float,
    ) -> None:
        self.image = image
        self.width = width
        self.height = height
        # Nominal (un-offset) baseline within the tightly cropped, high-
        # resolution mask. Individual glyph_y_offsets_px values remain
        # relative to this shared baseline.
        self.baseline_from_top_hi = baseline_from_top_hi


def render_tracking_mask(
    text: str,
    font: ImageFont.FreeTypeFont,
    tracking_px: float,
    supersample: int,
    glyph_y_offsets_px: dict[str, float] | None = None,
) -> TextMask:
    if not text:
        raise ValueError("target text is empty")
    tracking = tracking_px * supersample
    offsets = glyph_y_offsets_px or {}
    glyphs: list[tuple[str, tuple[int, int, int, int], float, float]] = []
    left = float("inf")
    top = float("inf")
    right = float("-inf")
    bottom = float("-inf")
    cursor = 0.0
    for index, char in enumerate(text):
        # Measure and draw every character relative to one shared baseline.
        # The former ``anchor='lt'`` path aligned each glyph's visible top,
        # which made shorter glyphs such as 口 float above 窗 and also
        # displaced punctuation independently of the surrounding text.
        bbox = font.getbbox(char, stroke_width=0, anchor="ls")
        advance = float(font.getlength(char))
        y_offset = float(offsets.get(char, 0.0)) * supersample
        glyphs.append((char, bbox, cursor, y_offset))
        left = min(left, cursor + bbox[0])
        top = min(top, bbox[1] + y_offset)
        right = max(right, cursor + bbox[2])
        bottom = max(bottom, bbox[3] + y_offset)
        cursor += advance + (tracking if index + 1 < len(text) else 0)
    origin_x = int(np.floor(left))
    origin_y = int(np.floor(top))
    width = max(1, int(np.ceil(right)) - origin_x)
    height = max(1, int(np.ceil(bottom)) - origin_y)
    nominal_baseline_y = float(-origin_y)
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for char, bbox, xpos, y_offset in glyphs:
        draw.text(
            (round(xpos - origin_x), round(nominal_baseline_y + y_offset)),
            char,
            font=font,
            fill=255,
            anchor="ls",
        )
    crop = mask.getbbox()
    if crop is None:
        raise ValueError("font produced an empty text mask")
    mask = mask.crop(crop)
    return TextMask(
        mask,
        mask.width,
        mask.height,
        baseline_from_top_hi=nominal_baseline_y - crop[1],
    )


def resize_horizontal(mask: Image.Image, scale_x: float) -> Image.Image:
    width = max(1, round(mask.width * scale_x))
    if width == mask.width:
        return mask
    return mask.resize((width, mask.height), Image.Resampling.LANCZOS)


def place_mask(
    mask: Image.Image,
    canvas_size_hi: tuple[int, int],
    anchor_hi: tuple[float, float],
    horizontal_align: str,
    vertical_align: str,
    baseline_offset_hi: float | None = None,
) -> tuple[Image.Image, tuple[int, int]]:
    ax, ay = anchor_hi
    if horizontal_align == "center":
        x = round(ax - mask.width / 2)
    elif horizontal_align == "right":
        x = round(ax - mask.width)
    else:
        x = round(ax)
    if vertical_align == "center":
        y = round(ay - mask.height / 2)
    elif vertical_align == "baseline":
        if baseline_offset_hi is None:
            raise ValueError("baseline placement requires a baseline offset")
        y = round(ay - baseline_offset_hi)
    elif vertical_align == "bottom":
        y = round(ay - mask.height)
    else:
        y = round(ay)
    placed = Image.new("L", canvas_size_hi, 0)
    placed.paste(mask, (x, y), mask)
    return placed, (x, y)


def expand_mask(mask: Image.Image, radius: float, supersample: int) -> Image.Image:
    pixels = max(0, round(radius * supersample))
    if pixels <= 0:
        return mask.copy()
    # A square max filter is separable.  The previous Pillow MaxFilter path is
    # byte-identical, but becomes prohibitively slow on the mandatory 8x
    # canvases.  Two small NumPy shift/reduce passes preserve the exact square
    # morphology (including zero-valued canvas boundaries) at a fraction of
    # the cost and have no practical kernel-size limit.
    source = np.asarray(mask, dtype=np.uint8)
    height, width = source.shape
    horizontal_pad = np.pad(source, ((0, 0), (pixels, pixels)), constant_values=0)
    horizontal = np.zeros_like(source)
    for offset in range(pixels * 2 + 1):
        np.maximum(horizontal, horizontal_pad[:, offset : offset + width], out=horizontal)
    vertical_pad = np.pad(horizontal, ((pixels, pixels), (0, 0)), constant_values=0)
    result = np.zeros_like(source)
    for offset in range(pixels * 2 + 1):
        np.maximum(result, vertical_pad[offset : offset + height, :], out=result)
    return Image.fromarray(result, "L")


def subtract_mask(outer: Image.Image, inner: Image.Image) -> Image.Image:
    a = np.asarray(outer, dtype=np.int16)
    b = np.asarray(inner, dtype=np.int16)
    return Image.fromarray(np.clip(a - b, 0, 255).astype(np.uint8), "L")


def tint(mask: Image.Image, color: tuple[int, int, int, int]) -> Image.Image:
    layer = Image.new("RGBA", mask.size, color)
    combined = np.rint(
        np.asarray(mask, dtype=np.float64) * (color[3] / 255.0)
    ).astype(np.uint8)
    layer.putalpha(Image.fromarray(combined, "L"))
    return layer


def gradient_tint(
    mask: Image.Image,
    top: tuple[int, int, int, int],
    bottom: tuple[int, int, int, int],
    scope: str = "canvas",
    gamma: float = 1.0,
) -> Image.Image:
    height, width = mask.height, mask.width
    if scope == "glyph_bbox":
        bbox = mask.getbbox()
        if bbox is None:
            raise ValueError("cannot apply a glyph-bbox gradient to an empty mask")
        top_y, bottom_y = bbox[1], bbox[3] - 1
        if bottom_y <= top_y:
            blend = np.zeros((height,), dtype=np.float64)
        else:
            rows_y = np.arange(height, dtype=np.float64)
            blend = np.clip((rows_y - top_y) / (bottom_y - top_y), 0.0, 1.0)
    elif scope == "canvas":
        if height == 1:
            blend = np.zeros((1,), dtype=np.float64)
        else:
            blend = np.linspace(0.0, 1.0, height)
    else:
        raise ValueError(f"unsupported gradient scope: {scope}")
    if not np.isfinite(gamma) or gamma <= 0:
        raise ValueError("gradient gamma must be a finite positive number")
    blend = np.power(blend, gamma)
    top_a = np.asarray(top, dtype=np.float64)
    bottom_a = np.asarray(bottom, dtype=np.float64)
    rows = np.rint(top_a[None, :] * (1.0 - blend[:, None]) + bottom_a[None, :] * blend[:, None])
    arr = np.broadcast_to(rows[:, None, :], (height, width, 4)).copy().astype(np.uint8)
    coverage = np.asarray(mask, dtype=np.float64) / 255.0
    arr[:, :, 3] = np.rint(arr[:, :, 3].astype(np.float64) * coverage).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def shifted(mask: Image.Image, dx: int, dy: int) -> Image.Image:
    result = Image.new("L", mask.size, 0)
    result.paste(mask, (dx, dy))
    return result


def union_masks(masks: Iterable[Image.Image]) -> Image.Image:
    iterator = iter(masks)
    try:
        result = np.asarray(next(iterator), dtype=np.uint8).copy()
    except StopIteration:
        raise ValueError("at least one mask is required")
    for mask in iterator:
        result = np.maximum(result, np.asarray(mask, dtype=np.uint8))
    return Image.fromarray(result, "L")


def edge_clearance_px(
    bbox: tuple[int, int, int, int] | None,
    canvas_size: tuple[int, int],
) -> dict[str, int] | None:
    """Return clear pixels between a visible bounding box and each canvas edge.

    A value of zero is an explicit clipping-risk signal: visible glyph,
    stroke, or shadow pixels have reached that edge of the finite canvas.
    """

    if bbox is None:
        return None
    return {
        "left": int(bbox[0]),
        "top": int(bbox[1]),
        "right": int(canvas_size[0] - bbox[2]),
        "bottom": int(canvas_size[1] - bbox[3]),
    }


def touches_canvas_edge(clearance: dict[str, int] | None) -> bool:
    return bool(clearance is not None and any(value <= 0 for value in clearance.values()))


def composite_rgba(base: Image.Image, overlay: Image.Image) -> Image.Image:
    return Image.alpha_composite(base.convert("RGBA"), overlay.convert("RGBA"))


def render_effects(
    text: str, profile: dict[str, Any], canvas_size: tuple[int, int]
) -> tuple[Image.Image, Image.Image, dict[str, Any]]:
    render = profile["render"]
    ss = int(render["supersample"])
    hi_size = (canvas_size[0] * ss, canvas_size[1] * ss)
    font, font_lock = load_variable_font(
        Path(render["font_path"]),
        float(render["font_size_px"]),
        int(render["font_weight"]),
        ss,
        str(render["font_sha256"]),
    )
    raw = render_tracking_mask(
        text,
        font,
        float(render["tracking_px"]),
        ss,
        {str(key): float(value) for key, value in render.get("glyph_y_offsets_px", {}).items()},
    )
    glyph = resize_horizontal(raw.image, float(render["scale_x"]))
    anchor = render["anchor_px"]
    baseline_offset_hi = None
    if render["vertical_align"] == "baseline":
        # The mask is tightly cropped, so the profile stores the intended
        # baseline offset from the top of that cropped mask in native pixels.
        baseline_offset_hi = float(render["baseline_px"]) * ss
    glyph, origin_hi = place_mask(
        glyph,
        hi_size,
        (float(anchor[0]) * ss, float(anchor[1]) * ss),
        render["horizontal_align"],
        render["vertical_align"],
        baseline_offset_hi,
    )

    layers: list[Image.Image] = []
    effect_masks: list[Image.Image] = [glyph]
    shadow = render.get("shadow")
    if shadow:
        shadow_mask = expand_mask(glyph, float(shadow.get("spread_px", 0)), ss)
        blur = float(shadow.get("blur_px", 0)) * ss
        if blur > 0:
            shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(blur))
        dx = round(float(shadow["offset_px"][0]) * ss)
        dy = round(float(shadow["offset_px"][1]) * ss)
        shadow_mask = shifted(shadow_mask, dx, dy)
        layers.append(tint(shadow_mask, rgba(shadow["rgba"])))
        effect_masks.append(shadow_mask)

    for stroke in sorted(render.get("strokes", []), key=lambda item: float(item["width_px"]), reverse=True):
        expanded = expand_mask(glyph, float(stroke["width_px"]), ss)
        # Paint full shapes from widest to narrowest.  Each later, narrower
        # layer overwrites the center of the former one, leaving deterministic
        # concentric stroke rings without gaps.
        layers.append(tint(expanded, rgba(stroke["rgba"])))
        effect_masks.append(expanded)

    fill = render["fill"]
    layers.append(
        gradient_tint(
            glyph,
            rgba(fill["top_rgba"]),
            rgba(fill.get("bottom_rgba", fill["top_rgba"])),
            str(fill.get("gradient_scope", "canvas")),
            float(fill.get("gradient_gamma", 1.0)),
        )
    )
    overlay_hi = Image.new("RGBA", hi_size, (0, 0, 0, 0))
    for layer in layers:
        overlay_hi = composite_rgba(overlay_hi, layer)
    effect_hi = union_masks(effect_masks)
    overlay = overlay_hi.resize(canvas_size, Image.Resampling.LANCZOS)
    effect = effect_hi.resize(canvas_size, Image.Resampling.LANCZOS)
    # RGBA and L downsampling can round a fringe pixel differently.  The
    # allowed/effect mask must cover every pixel that the actual overlay can
    # modify, so include the native overlay alpha after both resizes.
    effect = union_masks((effect, overlay.getchannel("A")))
    bbox = effect.getbbox()
    glyph_native = glyph.resize(canvas_size, Image.Resampling.LANCZOS)
    glyph_bbox = glyph_native.getbbox()
    glyph_clearance = edge_clearance_px(glyph_bbox, canvas_size)
    effect_clearance = edge_clearance_px(bbox, canvas_size)
    metrics = {
        "supersample": ss,
        "variable_font_weight": int(render["font_weight"]),
        "font_lock": font_lock,
        "raw_text_size_hi": [raw.width, raw.height],
        "raw_baseline_from_top_hi": raw.baseline_from_top_hi,
        "scaled_text_size_hi": [glyph.getbbox()[2] - glyph.getbbox()[0], glyph.getbbox()[3] - glyph.getbbox()[1]],
        "placed_origin_hi": list(origin_hi),
        "glyph_bbox": list(glyph_bbox) if glyph_bbox else None,
        "glyph_edge_clearance_px": glyph_clearance,
        "glyph_touches_canvas_edge": touches_canvas_edge(glyph_clearance),
        "effect_bbox": list(bbox) if bbox else None,
        "effect_edge_clearance_px": effect_clearance,
        "effect_touches_canvas_edge": touches_canvas_edge(effect_clearance),
        "anchor_px": [float(anchor[0]), float(anchor[1])],
        "horizontal_align": render["horizontal_align"],
        "vertical_align": render["vertical_align"],
        "baseline_px": float(render["baseline_px"]) if "baseline_px" in render else None,
        "fill_gradient_scope": str(fill.get("gradient_scope", "canvas")),
        "fill_gradient_gamma": float(fill.get("gradient_gamma", 1.0)),
        "glyph_y_offsets_px": {
            str(key): float(value)
            for key, value in render.get("glyph_y_offsets_px", {}).items()
        },
    }
    return overlay, effect, metrics


def reconstruct_background(
    source: Image.Image, background: Image.Image | None, old_mask: Image.Image
) -> Image.Image:
    if background is None:
        if old_mask.getbbox() is not None:
            raise ValueError("old text mask is non-empty, so --clean-background is required")
        return source.copy()
    if background.size != source.size:
        raise ValueError("clean background size differs from source")
    # Only old locale-text pixels are accepted from the clean background.
    return Image.composite(background.convert("RGBA"), source.convert("RGBA"), old_mask)


def render_localized(
    *,
    source_path: Path,
    clean_background_path: Path | None,
    old_text_mask_path: Path,
    target_text: str,
    profile_path: Path,
    output_path: Path,
    allowed_mask_path: Path,
    qa_path: Path,
    additional_input_paths: Iterable[Path] = (),
) -> dict[str, Any]:
    inputs = [source_path, old_text_mask_path, profile_path, *additional_input_paths]
    if clean_background_path is not None:
        inputs.append(clean_background_path)
    validate_new_outputs(
        (output_path, allowed_mask_path, qa_path),
        inputs=inputs,
    )
    profile = load_json(profile_path)
    configured_font = Path(profile.get("render", {}).get("font_path", ""))
    if configured_font and not configured_font.is_absolute():
        profile["render"]["font_path"] = str(
            (profile_path.resolve(strict=True).parent / configured_font).resolve(strict=False)
        )
    validate_profile(profile)
    source = Image.open(source_path).convert("RGBA")
    old_mask = Image.open(old_text_mask_path).convert("L")
    if old_mask.size != source.size:
        raise ValueError("old text mask size differs from source")
    background = (
        Image.open(clean_background_path).convert("RGBA")
        if clean_background_path is not None
        else None
    )
    base = reconstruct_background(source, background, old_mask)
    overlay, new_effect_mask, metrics = render_effects(target_text, profile, source.size)
    rendered = composite_rgba(base, overlay)
    allowed = union_masks((old_mask, new_effect_mask))

    source_arr = np.asarray(source, dtype=np.uint8)
    rendered_arr = np.asarray(rendered, dtype=np.uint8)
    allowed_arr = np.asarray(allowed, dtype=np.uint8) > 0
    # Hard guard: every non-allowed pixel is restored from the official source.
    rendered_arr = rendered_arr.copy()
    rendered_arr[~allowed_arr] = source_arr[~allowed_arr]
    candidate = Image.fromarray(rendered_arr, "RGBA")

    outside_exact = bool(np.array_equal(rendered_arr[~allowed_arr], source_arr[~allowed_arr]))
    changed = np.any(rendered_arr != source_arr, axis=2)
    outside_changed = int(np.count_nonzero(changed & ~allowed_arr))
    if not outside_exact or outside_changed:
        raise AssertionError("renderer changed pixels outside the allowed text-union mask")

    candidate_payload = png_bytes(candidate)
    allowed_payload = png_bytes(allowed)
    report: dict[str, Any] = {
        "schema": "photon-deterministic-text-render-qa/v2",
        "status": "pass",
        "profile_id": profile.get("profile_id"),
        "source_file": source_path.name,
        "source_sha256": sha256_file(source_path),
        "profile_file": profile_path.name,
        "profile_sha256": sha256_file(profile_path),
        "clean_background_file": clean_background_path.name if clean_background_path else None,
        "clean_background_sha256": (
            sha256_file(clean_background_path) if clean_background_path else None
        ),
        "target_text": target_text,
        "output_file": output_path.name,
        "output_sha256": sha256_bytes(candidate_payload),
        "allowed_mask_file": allowed_mask_path.name,
        "allowed_mask_sha256": sha256_bytes(allowed_payload),
        "size_exact": candidate.size == source.size,
        "outside_allowed_mask_exact": outside_exact,
        "outside_allowed_mask_changed_pixels": outside_changed,
        "changed_pixels": int(np.count_nonzero(changed)),
        "allowed_pixels": int(np.count_nonzero(allowed_arr)),
        "source_alpha_preserved_outside_allowed": bool(
            np.array_equal(rendered_arr[:, :, 3][~allowed_arr], source_arr[:, :, 3][~allowed_arr])
        ),
        "metrics": metrics,
    }
    qa_payload = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    write_new_files(
        {
            output_path: candidate_payload,
            allowed_mask_path: allowed_payload,
            qa_path: qa_payload,
        },
        inputs=inputs,
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--clean-background", type=Path)
    parser.add_argument("--old-text-mask", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--target-text")
    group.add_argument("--target-text-file", type=Path)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allowed-mask", type=Path, required=True)
    parser.add_argument("--qa", type=Path, required=True)
    args = parser.parse_args()
    target = (
        args.target_text_file.read_text(encoding="utf-8").strip()
        if args.target_text_file
        else args.target_text
    )
    report = render_localized(
        source_path=args.source,
        clean_background_path=args.clean_background,
        old_text_mask_path=args.old_text_mask,
        target_text=target,
        profile_path=args.profile,
        output_path=args.output,
        allowed_mask_path=args.allowed_mask,
        qa_path=args.qa,
        additional_input_paths=((args.target_text_file,) if args.target_text_file else ()),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
