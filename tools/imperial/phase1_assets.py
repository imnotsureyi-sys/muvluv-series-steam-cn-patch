#!/usr/bin/env python3
"""Small, strict helpers shared by the Imperial Capital Burns phase-one build."""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import shutil


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def _safe_relative(value: str) -> Path:
    posix = PurePosixPath(value)
    if posix.is_absolute() or ".." in posix.parts:
        raise ValueError(f"unsafe relative path: {value}")
    return Path(*posix.parts)


def copy_image_slot(
    source_root: Path, payload_root: Path, source_relative: str, target_relative: str
) -> Path:
    """Copy an existing EN bitmap byte-for-byte into its JP asset slot.

    English is used only as a pre-existing visual asset here.  This helper
    deliberately accepts no textual translation input.
    """

    if not source_relative.lower().endswith("_en.webp"):
        raise ValueError("image source must be an _en.webp asset")
    if not target_relative.lower().endswith("_ja.webp"):
        raise ValueError("image target must be a _ja.webp slot")

    source = source_root / _safe_relative(source_relative)
    target = payload_root / _safe_relative(target_relative)
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if sha256(source) != sha256(target):
        raise RuntimeError(f"image copy verification failed: {target}")
    return target


def render_character_name_card(
    template_path: Path, text: str, font_path: Path, output: Path
) -> Path:
    """Render one Chinese name into the original JP card's text band.

    The layout follows the verified TDA name-card workflow: preserve the
    original canvas, derive the occupied text band from its alpha channel,
    fit a TDA Source Han Sans font, center the replacement, and write a
    lossless transparent WebP.  No English text is read by this function.
    """

    try:
        from PIL import Image, ImageDraw, ImageFilter, ImageFont
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("Pillow is required to render character cards") from exc

    if not text.strip():
        raise ValueError("character-card text must not be empty")
    if not template_path.name.lower().endswith("_ja.webp"):
        raise ValueError("character-card template must be a JP WebP slot")

    with Image.open(template_path) as source:
        template = source.convert("RGBA")
    bbox = template.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"JP card has no alpha evidence: {template_path}")

    effect_margin = 4
    left = max(2 + effect_margin, bbox[0] + effect_margin)
    top = max(0, bbox[1] - 2)
    right = min(template.width - 2 - effect_margin, bbox[2] - effect_margin)
    bottom = min(template.height, bbox[3] + 2)
    if right <= left:
        raise ValueError(f"JP card text band is too narrow: {template_path}")
    max_width = right - left
    max_height = bottom - top
    measure = ImageDraw.Draw(Image.new("RGBA", template.size))

    fitted = None
    for size in range(42, 11, -1):
        font = ImageFont.truetype(str(font_path), size)
        text_bbox = measure.textbbox((0, 0), text, font=font, stroke_width=1)
        width = text_bbox[2] - text_bbox[0]
        height = text_bbox[3] - text_bbox[1]
        if width <= max_width and height <= max_height:
            fitted = (font, text_bbox, width, height)
            break
    if fitted is None:
        raise ValueError(f"character-card text does not fit: {text!r} in {template_path.name}")

    font, text_bbox, width, height = fitted
    x = round((left + right - width) / 2 - text_bbox[0])
    y = round((top + bottom - height) / 2 - text_bbox[1])
    rendered = Image.new("RGBA", template.size, (0, 0, 0, 0))

    glow = Image.new("RGBA", template.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.text(
        (x, y),
        text,
        font=font,
        fill=(255, 144, 26, 220),
        stroke_width=2,
        stroke_fill=(178, 74, 0, 230),
    )
    glow = glow.filter(ImageFilter.GaussianBlur(1.0))
    rendered.alpha_composite(glow)

    draw = ImageDraw.Draw(rendered)
    draw.text(
        (x + 1, y + 1),
        text,
        font=font,
        fill=(92, 31, 0, 155),
        stroke_width=1,
        stroke_fill=(110, 39, 0, 180),
    )
    draw.text(
        (x, y),
        text,
        font=font,
        fill=(255, 253, 241, 255),
        stroke_width=1,
        stroke_fill=(178, 74, 0, 255),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    rendered.save(output, format="WEBP", lossless=True, quality=100, method=6)
    return output


def detect_text_line_boxes(
    image_path: Path, threshold: int = 60
) -> list[tuple[int, int, int, int]]:
    """Return the visible text boxes on a black Imperial event-card canvas.

    Coordinates use Pillow's exclusive right/bottom convention.  A gap of up
    to three rows is kept inside a line so punctuation and antialiasing do not
    accidentally split one Japanese source line into several bands.
    """

    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("Pillow is required to inspect location/date cards") from exc

    with Image.open(image_path) as source:
        gray = source.convert("L")
    if gray.size != (1280, 720):
        raise ValueError(f"event-card canvas must be 1280x720: {image_path}")

    mask = gray.point(lambda value: 255 if value > threshold else 0, mode="1")
    active_rows: list[int] = []
    for y in range(mask.height):
        if mask.crop((0, y, mask.width, y + 1)).getbbox() is not None:
            active_rows.append(y)
    if not active_rows:
        raise ValueError(f"event card has no visible JP text: {image_path}")

    row_bands: list[tuple[int, int]] = []
    start = previous = active_rows[0]
    for y in active_rows[1:]:
        if y - previous > 3:
            row_bands.append((start, previous + 1))
            start = y
        previous = y
    row_bands.append((start, previous + 1))

    boxes: list[tuple[int, int, int, int]] = []
    for top, bottom in row_bands:
        band_bbox = mask.crop((0, top, mask.width, bottom)).getbbox()
        if band_bbox is None:  # pragma: no cover - guarded by active rows
            continue
        boxes.append((band_bbox[0], top + band_bbox[1], band_bbox[2], top + band_bbox[3]))
    return boxes


def render_location_date_card(
    template_path: Path, text: str, font_path: Path, output: Path
) -> Path:
    """Redraw a Chinese location/date card from the Japanese AVIF geometry.

    The Japanese bitmap is the only layout source.  Each ``|``-separated
    Chinese line is fitted inside the corresponding JP line box, centered on
    the exact same point, and rendered in opaque white on a 1280x720 black
    canvas using the caller-provided Source Han Sans Bold font.
    """

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("Pillow with AVIF support is required") from exc

    lines = [line.strip() for line in text.split("|")]
    if not lines or any(not line for line in lines):
        raise ValueError("location/date card lines must not be empty")
    source_boxes = detect_text_line_boxes(template_path)
    if len(lines) != len(source_boxes):
        raise ValueError(
            f"location/date card line count mismatch: {len(lines)} Chinese lines, "
            f"{len(source_boxes)} JP lines in {template_path.name}"
        )

    measure = ImageDraw.Draw(Image.new("RGB", (1280, 720), (0, 0, 0)))
    placements = []
    for line, source_box in zip(lines, source_boxes):
        left, top, right, bottom = source_box
        max_width = right - left
        max_height = bottom - top
        fitted = None
        for size in range(max(12, max_height * 2), 7, -1):
            font = ImageFont.truetype(str(font_path), size)
            text_bbox = measure.textbbox((0, 0), line, font=font)
            width = text_bbox[2] - text_bbox[0]
            height = text_bbox[3] - text_bbox[1]
            if width <= max_width and height <= max_height:
                fitted = (font, text_bbox, width, height)
                break
        if fitted is None:
            raise ValueError(f"event-card text does not fit: {line!r} in {template_path.name}")

        font, text_bbox, width, height = fitted
        center_x = (left + right) / 2
        center_y = (top + bottom) / 2
        x = round(center_x - width / 2 - text_bbox[0])
        y = round(center_y - height / 2 - text_bbox[1])
        placements.append([line, font, x, y])

    output.parent.mkdir(parents=True, exist_ok=True)
    output_boxes = []
    for _attempt in range(5):
        canvas = Image.new("RGB", (1280, 720), (0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for line, font, x, y in placements:
            draw.text((x, y), line, font=font, fill=(255, 255, 255))
        canvas.save(
            output,
            format="AVIF",
            quality=100,
            subsampling="4:4:4",
            speed=6,
        )
        output_boxes = detect_text_line_boxes(output)
        if len(output_boxes) != len(source_boxes):
            break
        corrections = []
        for source_box, output_box in zip(source_boxes, output_boxes):
            corrections.append(
                (
                    round((source_box[0] + source_box[2] - output_box[0] - output_box[2]) / 2),
                    round((source_box[1] + source_box[3] - output_box[1] - output_box[3]) / 2),
                )
            )
        if all(abs(dx) <= 1 and abs(dy) <= 1 for dx, dy in corrections):
            break
        for placement, (dx, dy) in zip(placements, corrections):
            placement[2] += dx
            placement[3] += dy

    if len(output_boxes) != len(source_boxes):
        raise RuntimeError(f"rendered event-card line detection failed: {output}")
    for source_box, output_box in zip(source_boxes, output_boxes):
        source_center = (
            (source_box[0] + source_box[2]) / 2,
            (source_box[1] + source_box[3]) / 2,
        )
        output_center = (
            (output_box[0] + output_box[2]) / 2,
            (output_box[1] + output_box[3]) / 2,
        )
        if any(abs(a - b) > 2 for a, b in zip(source_center, output_center)):
            raise RuntimeError(f"rendered event-card center drift: {output}")
        if (
            output_box[2] - output_box[0] > source_box[2] - source_box[0]
            or output_box[3] - output_box[1] > source_box[3] - source_box[1]
        ):
            raise RuntimeError(f"rendered event-card text exceeds JP bounds: {output}")
    return output
