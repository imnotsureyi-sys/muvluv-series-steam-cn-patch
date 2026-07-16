#!/usr/bin/env python3
"""Build the approved loose-file patch for The Imperial Capital Burns.

This creates a loose FPD overlay.  It never writes to the Steam installation
or the original pack.  Story EGPACKs are produced by the separate strict body
pipeline; this builder covers UI, fonts, telops, and JP-derived event cards.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import textwrap
import unicodedata
import xml.etree.ElementTree as ET

from phase1_assets import (
    copy_image_slot,
    detect_text_line_boxes,
    render_character_name_card,
    render_location_date_card,
    sha256,
)


PACK_SHA256 = "1D749713C01AE4E825A82FA2E75BF232303B1510708BBC9B7B98275315F7344F"
FONT_HASHES = {
    "SourceHanSansSC-Bold.otf": "DF560F379D55A0C9859ADD605DD67E0721955FDE3CD76C41C5F8D6CBA7823D41",
    "SourceHanSansSC.otf": "F1D8611151880C6C336AABEAC4640EF434FA13CBFBF1FFE82D0A71B2A5637256",
    "Font.cfg": "8F57946E48267F568B995B13B1F11E05225046424B3FFAAB13611EF28146EB17",
    "Font_en.cfg": "8F57946E48267F568B995B13B1F11E05225046424B3FFAAB13611EF28146EB17",
    "Font_zh_hans.cfg": "8F57946E48267F568B995B13B1F11E05225046424B3FFAAB13611EF28146EB17",
}
FONT_CONFIG_NAMES = (
    "Font.cfg",
    "Font_en.cfg",
    "Font_zh_hans.cfg",
)
FONT_BINARY_HASHES = {
    name: expected
    for name, expected in FONT_HASHES.items()
    if name not in FONT_CONFIG_NAMES
}
KNOWN_PREVIOUS_HASHES = {
    "root/assets/data/gui/textures/boot/00_note000_ja.webp": [
        "7B2761FE085D2B8C348FB3B12D8C7425343F20FDE96A07658E3C6688942DF83F"
    ],
    "root/assets/data/gui/textures/boot/00_v_note000_ja.webp": [
        "6BB3CC1D51640CB3ED641D3E4CEA9ABC4EEA8F6C5243D78C22AB3FC243A0926B"
    ],
}


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def run_checked(command: list[str]) -> None:
    completed = subprocess.run(command, text=True, encoding="utf-8", errors="replace")
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {command}")


def copy_fonts(
    source_root: Path,
    payload_font: Path,
    hashes: dict[str, str] = FONT_HASHES,
) -> None:
    payload_font.mkdir(parents=True, exist_ok=True)
    for name, expected_hash in hashes.items():
        source = source_root / name
        if not source.is_file():
            raise FileNotFoundError(source)
        if sha256(source) != expected_hash:
            raise ValueError(f"TDA font hash mismatch: {source}")
        target = payload_font / name
        shutil.copyfile(source, target)
        if sha256(target) != expected_hash:
            raise RuntimeError(f"font copy verification failed: {target}")


def font_config_text() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<FontConfigDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <FontParamList>
    <FontParam>
      <Label>Common</Label>
      <FamilyName>Source Han Sans SC</FamilyName>
      <Bold>false</Bold>
      <File>SourceHanSansSC.otf</File>
    </FontParam>
    <FontParam>
      <Label>Message</Label>
      <FamilyName>Source Han Sans SC</FamilyName>
      <Bold>false</Bold>
      <File>SourceHanSansSC.otf</File>
      <LineBreak>1.05</LineBreak>
    </FontParam>
    <FontParam>
      <Label>Speaker</Label>
      <FamilyName>Source Han Sans SC</FamilyName>
      <Bold>true</Bold>
      <File>SourceHanSansSC-Bold.otf</File>
    </FontParam>
    <FontParam>
      <Label>Hud</Label>
      <FamilyName>Source Han Sans SC</FamilyName>
      <Bold>true</Bold>
      <File>SourceHanSansSC-Bold.otf</File>
    </FontParam>
  </FontParamList>
</FontConfigDocument>
"""


def write_font_configs(font_root: Path) -> None:
    content = font_config_text().replace("\n", "\r\n").encode("utf-8")
    for name in FONT_CONFIG_NAMES:
        (font_root / name).write_bytes(content)


def copy_image_rows(source_root: Path, target_root: Path, rows: list[dict[str, str]]) -> None:
    for row in rows:
        copy_image_slot(source_root, target_root, row["source_en"], row["target_ja"])


def copy_tda_boot_notice_rows(
    source_root: Path, target_root: Path, rows: list[dict[str, str]]
) -> None:
    """Copy the hash-locked TDA Chinese notices into Imperial JP boot slots."""

    from PIL import Image

    allowed = {
        "00_note000_ja.webp": "boot/00_note000_ja.webp",
        "00_v_note000_ja.webp": "boot/00_v_note000_ja.webp",
    }
    if {row["source_tda"]: row["target_ja"] for row in rows} != allowed:
        raise ValueError("unexpected TDA boot-notice manifest")
    for row in rows:
        source = source_root / row["source_tda"]
        target = target_root / Path(*PurePosixPath(row["target_ja"]).parts)
        if not source.is_file():
            raise FileNotFoundError(source)
        if sha256(source) != row["sha256"]:
            raise ValueError(f"TDA boot-notice hash mismatch: {source}")
        with Image.open(source) as image:
            expected_size = (int(row["width"]), int(row["height"]))
            if image.size != expected_size:
                raise ValueError(
                    f"TDA boot-notice canvas mismatch: {source} {image.size}"
                )
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if sha256(target) != row["sha256"]:
            raise RuntimeError(f"TDA boot-notice copy verification failed: {target}")


def render_character_name_rows(
    source_root: Path,
    target_root: Path,
    font_path: Path,
    rows: list[dict[str, str]],
) -> None:
    for row in rows:
        relative = Path(row["target_ja"])
        render_character_name_card(
            source_root / relative,
            row["zh_cn"],
            font_path,
            target_root / relative,
        )


def normalize_location_date_reference(value: str) -> str | None:
    marker = "140_テロップ/"
    normalized = value.replace("\\", "/")
    if marker not in normalized:
        return None
    relative = normalized.split(marker, 1)[1]
    if not relative.startswith(("010_場所指定/", "020_日時指定/")):
        return None
    if relative.endswith(".avif"):
        relative = relative[:-5]
    if relative.endswith("_en"):
        relative = relative[:-3]
    if not relative.rsplit("/", 1)[-1].startswith("EVテロップ_"):
        return None
    return f"{relative}.avif"


def collect_location_date_calls(script_root: Path) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []
    for script in sorted(script_root.rglob("*.xml"), key=lambda path: path.as_posix()):
        scene = script.stem
        chapter = unicodedata.normalize("NFKC", scene.split("：", 1)[0])
        for element in ET.parse(script).getroot().iter():
            for attribute, value in element.attrib.items():
                relative = normalize_location_date_reference(value)
                if relative is None:
                    continue
                calls.append(
                    {
                        "kind": "location" if relative.startswith("010_") else "date",
                        "chapter": chapter,
                        "scene": scene,
                        "xml_line": element.get("__line__", ""),
                        "attribute": attribute,
                        "source_relative": relative,
                        "resource": value,
                    }
                )
    return calls


def find_location_date_references(script_root: Path) -> set[str]:
    """Collect normalized JP event-card slots actually referenced by XML."""

    return {row["source_relative"] for row in collect_location_date_calls(script_root)}


def render_location_date_rows(
    source_root: Path,
    target_root: Path,
    font_path: Path,
    rows: list[dict[str, str]],
) -> None:
    """Render every approved base card and its byte-identical technical EN slot."""

    for row in rows:
        relative = Path(*PurePosixPath(row["source_relative"]).parts)
        source = source_root / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        base = target_root / relative
        render_location_date_card(source, row["zh_cn"], font_path, base)
        en = base.with_name(f"{base.stem}_en{base.suffix}")
        shutil.copyfile(base, en)
        if sha256(base) != sha256(en):
            raise RuntimeError(f"event-card technical slot copy failed: {en}")


TELOP_REFERENCE_RE = re.compile(r"add_telop_([0-9]+(?:[ab])?)(?:_en)?")
TELOP_TAG_BYTES_RE = re.compile(rb"<chara\b[^>]*>", re.DOTALL)
TELOP_ID_BYTES_RE = re.compile(rb"add_telop_([0-9]+(?:[ab])?)(?:_en)?")
TELOP_POS_BYTES_RE = re.compile(rb'pos="([^"]+)"')
TELOP_STANDARD_POSITION = b"0,-1550,723"
TELOP_SHIFTED_POSITIONS = {b"0,-2145,723", b"0,-2170,723"}


def find_telop_references(script_root: Path) -> set[str]:
    return {row["asset_id"] for row in collect_telop_calls(script_root)}


def collect_telop_calls(script_root: Path) -> list[dict[str, str]]:
    calls: list[dict[str, str]] = []
    for script in sorted(script_root.rglob("*.xml"), key=lambda path: path.as_posix()):
        scene = script.stem
        chapter = unicodedata.normalize("NFKC", scene.split("：", 1)[0])
        for element in ET.parse(script).getroot().iter():
            for attribute, resource in element.attrib.items():
                for match in TELOP_REFERENCE_RE.finditer(resource):
                    calls.append(
                        {
                            "asset_id": match.group(1),
                            "chapter": chapter,
                            "scene": scene,
                            "xml_line": element.get("__line__", ""),
                            "attribute": attribute,
                            "resource": resource,
                        }
                    )
    return calls


def patch_telop_positions(source_root: Path, output_root: Path) -> dict[str, int]:
    """Normalize only shifted runtime add_telop coordinates.

    The localized XML remains byte-identical except for the ``pos`` value in
    ``chara`` tags that actually reference ``add_telop_*``.  Files without a
    required change are deliberately omitted from the loose overlay.
    """

    changed_files: dict[str, int] = {}
    for source in sorted(source_root.rglob("*.xml"), key=lambda path: path.as_posix()):
        original = source.read_bytes()
        replacements = 0

        def patch_tag(match: re.Match[bytes]) -> bytes:
            nonlocal replacements
            tag = match.group(0)
            if TELOP_ID_BYTES_RE.search(tag) is None:
                return tag
            positions = TELOP_POS_BYTES_RE.findall(tag)
            if len(positions) != 1:
                raise RuntimeError(f"add_telop tag must have exactly one position: {source}")
            position = positions[0]
            if position == TELOP_STANDARD_POSITION:
                return tag
            if position not in TELOP_SHIFTED_POSITIONS:
                raise RuntimeError(
                    f"unexpected add_telop position {position!r}: {source}"
                )
            patched, count = TELOP_POS_BYTES_RE.subn(
                b'pos="' + TELOP_STANDARD_POSITION + b'"', tag, count=1
            )
            if count != 1:
                raise RuntimeError(f"failed to patch add_telop position: {source}")
            replacements += 1
            return patched

        patched = TELOP_TAG_BYTES_RE.sub(patch_tag, original)
        if replacements:
            relative = source.relative_to(source_root)
            target = output_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(patched)
            if patched == original:
                raise RuntimeError(f"reported unchanged telop script: {source}")
            changed_files[relative.as_posix()] = replacements
    return changed_files


def write_telop_position_audit(changed_files: dict[str, int], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=("runtime_xml", "position_replacements"), delimiter="\t"
        )
        writer.writeheader()
        for relative, count in sorted(changed_files.items()):
            writer.writerow(
                {"runtime_xml": relative, "position_replacements": count}
            )


def write_telop_chapter_checklist(
    calls: list[dict[str, str]], rows: list[dict[str, str]], output: Path
) -> None:
    evidence = {row["asset_id"]: row for row in rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "asset_id",
        "chapter",
        "scene",
        "xml_line",
        "attribute",
        "resource",
        "speaker_jp",
        "jp_voice",
        "jp_text",
        "zh_cn",
    )
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for call in calls:
            row = evidence[call["asset_id"]]
            writer.writerow(
                {
                    **call,
                    "speaker_jp": row["speaker_jp"],
                    "jp_voice": row["jp_voice"],
                    "jp_text": row["jp_text"],
                    "zh_cn": row["zh_cn"],
                }
            )


def write_telop_audit(
    rows: list[dict[str, str]], telop_dir: Path, output: Path
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "asset_id",
                "resource_file",
                "scene",
                "jp_voice",
                "jp_text",
                "zh_cn",
                "base_sha256",
                "en_slot_sha256",
            ),
            delimiter="\t",
        )
        writer.writeheader()
        for row in rows:
            asset_id = row["asset_id"]
            writer.writerow(
                {
                    "asset_id": asset_id,
                    "resource_file": row["resource_file"],
                    "scene": row["scene"],
                    "jp_voice": row["jp_voice"],
                    "jp_text": row["jp_text"],
                    "zh_cn": row["zh_cn"],
                    "base_sha256": sha256(telop_dir / f"add_telop_{asset_id}.webp"),
                    "en_slot_sha256": sha256(telop_dir / f"add_telop_{asset_id}_en.webp"),
                }
            )


def _wrap_line(draw, line: str, font, max_width: int) -> list[str]:
    if draw.textlength(line, font=font) <= max_width:
        return [line]
    pieces: list[str] = []
    current = ""
    for char in line:
        candidate = current + char
        if current and draw.textlength(candidate, font=font) > max_width:
            pieces.append(current)
            current = char
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def infer_telop_reference_layout(
    reference_root: Path, rows: list[dict[str, str]]
) -> tuple[tuple[int, int], int, set[str]]:
    from PIL import Image

    sizes: set[tuple[int, int]] = set()
    bottoms: set[int] = set()
    invalid: set[str] = set()
    for row in rows:
        asset_id = row["asset_id"]
        reference = reference_root / f"add_telop_{asset_id}_en.webp"
        try:
            with Image.open(reference) as image:
                rgba = image.convert("RGBA")
                bbox = rgba.getchannel("A").getbbox()
        except Exception:
            invalid.add(asset_id)
            continue
        if bbox is None:
            invalid.add(asset_id)
            continue
        sizes.add(rgba.size)
        bottoms.add(bbox[3])
        if abs(((bbox[0] + bbox[2]) / 2) - (rgba.width / 2)) > 1:
            raise RuntimeError(f"off-center EN telop reference: {asset_id} {bbox}")
    if sizes != {(1280, 720)} or bottoms != {673}:
        raise RuntimeError(f"unexpected EN telop layout consensus: sizes={sizes} bottoms={bottoms}")
    if len(rows) - len(invalid) != 71 or invalid != {"13", "20", "25"}:
        raise RuntimeError(f"unexpected telop reference validity set: {sorted(invalid)}")
    return (1280, 720), 673, invalid


def write_telop_layout_audit(
    rows: list[dict[str, str]],
    reference_root: Path,
    output_root: Path,
    invalid_references: set[str],
    output: Path,
) -> None:
    from PIL import Image

    output.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "asset_id",
        "scene",
        "reference_status",
        "reference_size",
        "reference_alpha_bbox",
        "output_size",
        "output_alpha_bbox",
        "canvas_result",
        "baseline_result",
        "center_result",
    )
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            asset_id = row["asset_id"]
            reference_size = ""
            reference_bbox = ""
            if asset_id in invalid_references:
                reference_status = "71-valid-EN-consensus"
            else:
                reference_status = "direct-EN-reference"
                with Image.open(reference_root / f"add_telop_{asset_id}_en.webp") as image:
                    reference_rgba = image.convert("RGBA")
                    reference_size = f"{reference_rgba.width}x{reference_rgba.height}"
                    reference_bbox = str(reference_rgba.getchannel("A").getbbox())
            with Image.open(output_root / f"add_telop_{asset_id}.webp") as image:
                rgba = image.convert("RGBA")
                bbox = rgba.getchannel("A").getbbox()
            if bbox is None:
                raise RuntimeError(f"empty Chinese telop: {asset_id}")
            canvas_ok = rgba.size == (1280, 720)
            baseline_ok = bbox[3] == 673
            center_ok = abs(((bbox[0] + bbox[2]) / 2) - 640) <= 12
            if not (canvas_ok and baseline_ok and center_ok):
                raise RuntimeError(f"Chinese telop layout mismatch: {asset_id} size={rgba.size} bbox={bbox}")
            writer.writerow(
                {
                    "asset_id": asset_id,
                    "scene": row["scene"],
                    "reference_status": reference_status,
                    "reference_size": reference_size,
                    "reference_alpha_bbox": reference_bbox,
                    "output_size": f"{rgba.width}x{rgba.height}",
                    "output_alpha_bbox": str(bbox),
                    "canvas_result": "pass",
                    "baseline_result": "pass",
                    "center_result": "pass",
                }
            )


def write_location_date_layout_audit(
    rows: list[dict[str, str]],
    source_root: Path,
    output_root: Path,
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "kind",
        "source_relative",
        "jp_text",
        "zh_cn",
        "jp_line_boxes",
        "cn_line_boxes",
        "max_center_delta_px",
        "base_en_sha256_match",
        "result",
    )
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for row in rows:
            relative = Path(*PurePosixPath(row["source_relative"]).parts)
            source_boxes = detect_text_line_boxes(source_root / relative)
            base = output_root / relative
            output_boxes = detect_text_line_boxes(base)
            deltas = []
            for source_box, output_box in zip(source_boxes, output_boxes):
                deltas.extend(
                    (
                        abs((source_box[0] + source_box[2] - output_box[0] - output_box[2]) / 2),
                        abs((source_box[1] + source_box[3] - output_box[1] - output_box[3]) / 2),
                    )
                )
            en = base.with_name(f"{base.stem}_en{base.suffix}")
            hash_match = sha256(base) == sha256(en)
            result = (
                len(source_boxes) == len(output_boxes) == len(row["zh_cn"].split("|"))
                and max(deltas, default=0) <= 2
                and hash_match
            )
            if not result:
                raise RuntimeError(f"event-card audit failed: {relative}")
            writer.writerow(
                {
                    "kind": row["kind"],
                    "source_relative": row["source_relative"],
                    "jp_text": row["jp_text"],
                    "zh_cn": row["zh_cn"],
                    "jp_line_boxes": str(source_boxes),
                    "cn_line_boxes": str(output_boxes),
                    "max_center_delta_px": f"{max(deltas, default=0):.1f}",
                    "base_en_sha256_match": "yes",
                    "result": "pass",
                }
            )


def write_location_date_chapter_checklist(
    calls: list[dict[str, str]],
    rows: list[dict[str, str]],
    output: Path,
) -> None:
    translations = {row["source_relative"]: row for row in rows}
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = (
        "chapter",
        "scene",
        "xml_line",
        "kind",
        "source_relative",
        "jp_text",
        "zh_cn",
    )
    with output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        for call in calls:
            row = translations[call["source_relative"]]
            writer.writerow(
                {
                    "chapter": call["chapter"],
                    "scene": call["scene"],
                    "xml_line": call["xml_line"],
                    "kind": call["kind"],
                    "source_relative": call["source_relative"],
                    "jp_text": row["jp_text"],
                    "zh_cn": row["zh_cn"],
                }
            )


def render_telop(
    text: str,
    font_path: Path,
    output: Path,
    canvas_size: tuple[int, int] = (1280, 720),
    bottom_y: int = 673,
) -> None:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("Pillow is required to render the telop overlays") from exc

    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(font_path), 32)
    lines: list[str] = []
    for manual_line in text.split("|"):
        lines.extend(_wrap_line(draw, manual_line, font, canvas.width - 120))
    rendered = "\n".join(lines)
    spacing = 4
    stroke = 4
    bbox = draw.multiline_textbbox(
        (0, 0), rendered, font=font, spacing=spacing, align="center", stroke_width=stroke
    )
    height = bbox[3] - bbox[1]
    y = bottom_y - height - bbox[1]
    draw.multiline_text(
        (canvas.width // 2, y),
        rendered,
        font=font,
        fill=(255, 255, 255, 255),
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 255),
        spacing=spacing,
        align="center",
        anchor="ma",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="WEBP", lossless=True, method=6)


def create_preview(telop_dir: Path, output: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    selected = ["01", "04", "12", "19", "26", "33", "64", "66", "73", "85", "89", "97"]
    thumb_w, thumb_h = 480, 270
    margin, label_h = 12, 28
    sheet = Image.new("RGB", (thumb_w * 3 + margin * 4, (thumb_h + label_h) * 4 + margin * 5), "#20242b")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.load_default(size=18)
    for index, asset_id in enumerate(selected):
        row, col = divmod(index, 3)
        x = margin + col * thumb_w + col * margin
        y = margin + row * (thumb_h + label_h + margin)
        frame = Image.new("RGBA", (1280, 720), (8, 12, 18, 255))
        frame.alpha_composite(Image.open(telop_dir / f"add_telop_{asset_id}.webp").convert("RGBA"))
        frame.thumbnail((thumb_w, thumb_h))
        sheet.paste(frame.convert("RGB"), (x, y))
        draw.text((x + 8, y + thumb_h + 3), f"add_telop_{asset_id}", font=label_font, fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def create_ui_preview(textures: Path, output: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    selected = [
        "title/01_bt000_ja.webp",
        "title/01_bt010_ja.webp",
        "title/01_bt020_ja.webp",
        "title/01_bt030_ja.webp",
        "title/01_bt040_ja.webp",
        "main/13_bt020_ja.webp",
        "main/13_bt030_ja.webp",
        "main/13_bt040_ja.webp",
        "main/13_bt050_ja.webp",
        "option/11_title000_ja.webp",
        "load/04_title000_ja.webp",
        "save/06_title000_ja.webp",
        "backlog/15_title000_ja.webp",
        "control/14_title000_ja.webp",
        "gallery/09_title000_ja.webp",
        "boot/00_note000_ja.webp",
    ]
    cell_w, cell_h = 360, 190
    margin, label_h = 12, 26
    sheet = Image.new("RGB", (cell_w * 4 + margin * 5, cell_h * 4 + margin * 5), "#20242b")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.load_default(size=15)
    for index, relative in enumerate(selected):
        row, col = divmod(index, 4)
        x = margin + col * (cell_w + margin)
        y = margin + row * (cell_h + margin)
        tile = Image.new("RGBA", (cell_w, cell_h - label_h), (8, 12, 18, 255))
        image = Image.open(textures / Path(relative)).convert("RGBA")
        image.thumbnail((cell_w - 20, cell_h - label_h - 16))
        tile.alpha_composite(image, ((cell_w - image.width) // 2, (tile.height - image.height) // 2))
        sheet.paste(tile.convert("RGB"), (x, y))
        draw.text((x + 5, y + cell_h - label_h + 3), relative, font=label_font, fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def create_location_date_preview(
    card_root: Path, rows: list[dict[str, str]], output: Path
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    thumb_w, thumb_h, label_h = 256, 144, 22
    columns = 5
    row_count = (len(rows) + columns - 1) // columns
    sheet = Image.new("RGB", (thumb_w * columns, (thumb_h + label_h) * row_count), "#20242b")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.load_default(size=16)
    for index, row in enumerate(rows):
        relative = Path(*PurePosixPath(row["source_relative"]).parts)
        image = Image.open(card_root / relative).convert("RGB")
        image.thumbnail((thumb_w, thumb_h))
        y, x = divmod(index, columns)
        left, top = x * thumb_w, y * (thumb_h + label_h)
        sheet.paste(image, (left, top))
        draw.text((left + 5, top + thumb_h + 2), f"{index + 1:02d} {row['kind']}", font=label_font, fill="white")
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, optimize=True)


def write_installers(output: Path) -> None:
    """Write the same minimal distribution shell used by the TDA patches."""
    install_bat = r'''@echo off
setlocal
set "TARGET=%LOCALAPPDATA%\ancr\tm\data"
robocopy "%~dp0payload" "%TARGET%" /E
if %ERRORLEVEL% LEQ 7 exit /b 0
exit /b %ERRORLEVEL%
'''
    readme = """《The Imperial Capital Burns / 帝都燃烧篇》简体中文补丁 beta0.1

Windows 安装：
1. 完全退出游戏并解压补丁。
2. 双击 install.bat。
3. 脚本会把 payload 内的 root 目录复制到 %LOCALAPPDATA%\\ancr\\tm\\data，并自动合并覆盖。

Windows 手动安装：
打开 payload 文件夹，只把其中的 root 目录复制到 %LOCALAPPDATA%\\ancr\\tm\\data，选择合并并覆盖。
不要把 payload 文件夹本身套进 data，也不要修改 Steam 游戏目录中的 obb\\pack.bin。

Steam Deck：见 SteamDeck手动安装.txt。
翻译依据：仅 JP 原文，不使用 EN 文本、旧中文或模糊匹配兜底。
"""
    steam_deck = """《帝都燃烧篇》Steam Deck 手动安装说明

1. 进入 Steam Deck 桌面模式，并完全退出游戏。
2. 至少启动过一次游戏后，在文件管理器中开启“显示隐藏文件”。
3. 打开补丁的 payload 文件夹，复制里面的 root 目录。
4. 打开下面的 data 目录，把 root 粘贴进去，选择合并目录并覆盖同名文件：
   /home/deck/.local/share/Steam/steamapps/compatdata/2630300/pfx/drive_c/users/steamuser/AppData/Local/ancr/tm/data/
5. 如果游戏装在 microSD 卡或其他 Steam 库，就进入该库的 steamapps/compatdata/2630300，再按后面的相同路径找到 AppData/Local/ancr/tm/data/。
6. 复制完成后直接启动游戏。

注意：复制的是 payload 里面的 root，不是把 payload 整个套进 data。不要修改 Steam 游戏目录中的 obb/pack.bin。
"""
    (output / "install.bat").write_text(install_bat, encoding="ascii", newline="\r\n")
    (output / "README.txt").write_text(readme, encoding="utf-8-sig")
    (output / "SteamDeck手动安装.txt").write_text(steam_deck, encoding="utf-8-sig")
    return

    install = r'''param(
    [string]$GameDir = ""
)
$ErrorActionPreference = "Stop"
$ExpectedPack = "1D749713C01AE4E825A82FA2E75BF232303B1510708BBC9B7B98275315F7344F"
if ([string]::IsNullOrWhiteSpace($GameDir)) {
    $Candidates = Get-PSDrive -PSProvider FileSystem | ForEach-Object {
        @(
            (Join-Path $_.Root "Steam\steamapps\common\The Imperial Capital Burns"),
            (Join-Path $_.Root "SteamLibrary\steamapps\common\The Imperial Capital Burns"),
            (Join-Path $_.Root "Program Files (x86)\Steam\steamapps\common\The Imperial Capital Burns")
        )
    }
    $GameDir = $Candidates | Where-Object {
        $CandidatePack = Join-Path $_ "obb\pack.bin"
        (Test-Path -LiteralPath $CandidatePack -PathType Leaf) -and
        ((Get-FileHash -LiteralPath $CandidatePack -Algorithm SHA256).Hash -eq $ExpectedPack)
    } | Select-Object -First 1
    if ([string]::IsNullOrWhiteSpace($GameDir)) {
        throw "未自动找到匹配版本的 Steam 游戏目录。请在 PowerShell 中使用 -GameDir 指定路径。"
    }
}
$Pack = Join-Path $GameDir "obb\pack.bin"
if (-not (Test-Path -LiteralPath $Pack -PathType Leaf)) { throw "找不到原版 pack.bin：$Pack" }
if ((Get-FileHash -LiteralPath $Pack -Algorithm SHA256).Hash -ne $ExpectedPack) {
    throw "pack.bin 版本不匹配；安装已中止。"
}
$TargetRoot = Join-Path $env:LOCALAPPDATA "ancr\tm\data"
$Manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot "payload-manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$AllowedPrevious = @{}
if ($null -ne $Manifest.allowed_previous_sha256) {
    foreach ($Property in $Manifest.allowed_previous_sha256.PSObject.Properties) {
        $AllowedPrevious[$Property.Name] = @($Property.Value)
    }
}
$PayloadRoot = Join-Path $PSScriptRoot "payload"
$ManifestPaths = @($Manifest.files | ForEach-Object { $_.path -replace '\\', '/' })
$PayloadPaths = @(Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File -Force | ForEach-Object {
    $_.FullName.Substring($PayloadRoot.Length + 1) -replace '\\', '/'
})
$Unexpected = @($PayloadPaths | Where-Object { $_ -notin $ManifestPaths })
if ($Unexpected.Count -ne 0) { throw "payload 存在清单外文件：$($Unexpected -join ', ')" }
foreach ($Item in $Manifest.files) {
    $Source = Join-Path $PayloadRoot ($Item.path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) { throw "补丁文件缺失：$Source" }
    $SourceInfo = Get-Item -LiteralPath $Source
    if ($SourceInfo.Length -ne [int64]$Item.size) { throw "补丁文件大小校验失败：$Source" }
    if ((Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash -ne $Item.sha256) {
        throw "补丁文件校验失败：$Source"
    }
    $Target = Join-Path $TargetRoot ($Item.path -replace '/', '\')
    if (Test-Path -LiteralPath $Target -PathType Leaf) {
        $Existing = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash
        if ($Existing -ne $Item.sha256) {
            $Previous = @($AllowedPrevious[$Item.path])
            if ($Existing -notin $Previous) { throw "目标已有不同文件，未覆盖：$Target" }
        }
    }
}
New-Item -ItemType Directory -Force -Path $TargetRoot | Out-Null
Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot "payload") -Force |
    Copy-Item -Destination $TargetRoot -Recurse -Force
Write-Host "《帝都燃烧篇》汉化补丁安装完成。"
'''
    uninstall = r'''
$ErrorActionPreference = "Stop"
$TargetRoot = Join-Path $env:LOCALAPPDATA "ancr\tm\data"
$Manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot "payload-manifest.json") -Raw -Encoding UTF8 | ConvertFrom-Json
foreach ($Item in $Manifest.files) {
    $Target = Join-Path $TargetRoot ($Item.path -replace '/', '\')
    if (Test-Path -LiteralPath $Target -PathType Leaf) {
        $Existing = (Get-FileHash -LiteralPath $Target -Algorithm SHA256).Hash
        if ($Existing -eq $Item.sha256) { Remove-Item -LiteralPath $Target -Force }
        else { Write-Warning "保留已变化的文件：$Target" }
    }
}
Write-Host "《帝都燃烧篇》汉化补丁已卸载。"
'''
    install_bat = r'''@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" pause
exit /b %RESULT%
'''
    readme = """《The Imperial Capital Burns / 帝都燃烧篇》汉化补丁

安装：退出游戏后双击 install.bat。安装器会先验证 Steam 版原始 pack.bin、补丁文件清单及已有文件冲突，再写入 %LOCALAPPDATA%\\ancr\\tm\\data。
补丁使用松散覆盖文件，不修改 Steam 游戏目录中的 obb\\pack.bin。

卸载：PowerShell 运行 uninstall.ps1。卸载器只删除哈希仍与本补丁一致的文件，保留后来被修改的文件。
Steam Deck：见 STEAM_DECK_MANUAL.txt。
翻译依据：仅 JP 原文；不使用 EN 文本、旧中文或模糊匹配兜底。
"""
    steam_deck = """《帝都燃烧篇》Steam Deck 手动安装说明

1. 进入 Steam Deck 桌面模式，先完全退出游戏。
2. 在文件管理器中开启“显示隐藏文件”。
3. 打开补丁的 payload 文件夹，里面有 .smash 和 root 两个目录。
4. 把 .smash 和 root 直接复制到下面的 data 目录，选择“合并目录并覆盖同名文件”：
   ~/.local/share/Steam/steamapps/compatdata/2630300/pfx/drive_c/users/steamuser/AppData/Local/ancr/tm/data
5. 如果游戏安装在 microSD 或其他 Steam 库，就进入该库的 steamapps/compatdata/2630300，再按相同路径找到 AppData/Local/ancr/tm/data。
6. 复制完成后直接启动游戏。

注意：复制的是 payload 里面的 .smash 和 root，不是把 payload 整个套进 data。不要修改 Steam 游戏目录里的 obb/pack.bin。
"""
    (output / "install.ps1").write_text(install, encoding="utf-8-sig")
    (output / "install.bat").write_text(install_bat, encoding="ascii", newline="\r\n")
    (output / "uninstall.ps1").write_text(uninstall, encoding="utf-8-sig")
    (output / "README.txt").write_text(readme, encoding="utf-8-sig")
    (output / "STEAM_DECK_MANUAL.txt").write_text(steam_deck, encoding="utf-8-sig")


def write_manifest(output: Path) -> None:
    payload = output / "payload"
    files = []
    for path in sorted(p for p in payload.rglob("*") if p.is_file()):
        files.append(
            {
                "path": path.relative_to(payload).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "title": "The Imperial Capital Burns - Chinese loose overlay",
        "original_pack_sha256": PACK_SHA256,
        "translation_source": "Japanese only",
        "allowed_previous_sha256": KNOWN_PREVIOUS_HASHES,
        "files": files,
    }
    (output / "payload-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def validate_character_name_cards(
    texture_root: Path, rows: list[dict[str, str]]
) -> None:
    from PIL import Image

    expected = {Path(row["target_ja"]) for row in rows}
    actual = {
        path.relative_to(texture_root)
        for path in (texture_root / "option").glob("11_name*_ja.webp")
        if path.is_file()
    }
    if actual != expected:
        missing = sorted(path.as_posix() for path in expected - actual)
        extra = sorted(path.as_posix() for path in actual - expected)
        raise RuntimeError(f"character-card set mismatch: missing={missing} extra={extra}")

    for relative in sorted(expected):
        path = texture_root / relative
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            if rgba.size != (224, 96):
                raise RuntimeError(f"wrong character-card canvas: {path} {rgba.size}")
            if rgba.getchannel("A").getbbox() is None:
                raise RuntimeError(f"character card has empty alpha: {path}")


def validate_location_date_cards(
    card_root: Path, rows: list[dict[str, str]]
) -> None:
    from PIL import Image

    expected: set[Path] = set()
    for row in rows:
        relative = Path(*PurePosixPath(row["source_relative"]).parts)
        expected.add(relative)
        expected.add(relative.with_name(f"{relative.stem}_en{relative.suffix}"))
    actual = {path.relative_to(card_root) for path in card_root.rglob("*.avif")}
    if actual != expected:
        missing = sorted(path.as_posix() for path in expected - actual)
        extra = sorted(path.as_posix() for path in actual - expected)
        raise RuntimeError(f"location/date card set mismatch: missing={missing} extra={extra}")

    for row in rows:
        relative = Path(*PurePosixPath(row["source_relative"]).parts)
        base = card_root / relative
        en = base.with_name(f"{base.stem}_en{base.suffix}")
        with Image.open(base) as image:
            if image.size != (1280, 720):
                raise RuntimeError(f"wrong event-card canvas: {base} {image.size}")
            rgb = image.convert("RGB")
            if any(rgb.getpixel(point) != (0, 0, 0) for point in ((0, 0), (1279, 0), (0, 719), (1279, 719))):
                raise RuntimeError(f"event-card black canvas damaged: {base}")
        if len(detect_text_line_boxes(base)) != len(row["zh_cn"].split("|")):
            raise RuntimeError(f"event-card line layout mismatch: {base}")
        if sha256(base) != sha256(en):
            raise RuntimeError(f"event-card base/EN technical slots differ: {relative}")


def validate_tda_boot_notices(
    texture_root: Path, rows: list[dict[str, str]]
) -> None:
    from PIL import Image

    for row in rows:
        path = texture_root / Path(*PurePosixPath(row["target_ja"]).parts)
        if sha256(path) != row["sha256"]:
            raise RuntimeError(f"TDA boot-notice payload mismatch: {path}")
        with Image.open(path) as image:
            if image.size != (int(row["width"]), int(row["height"])):
                raise RuntimeError(f"wrong TDA boot-notice canvas: {path} {image.size}")


def validate(
    output: Path,
    image_rows: list[dict[str, str]],
    boot_notice_rows: list[dict[str, str]],
    data_spec_image_rows: list[dict[str, str]],
    character_name_rows: list[dict[str, str]],
    telop_rows: list[dict[str, str]],
    location_date_rows: list[dict[str, str]],
    telop_position_files: dict[str, int],
) -> None:
    from PIL import Image

    assets = output / "payload" / "root" / "assets"
    payload = assets / "data"
    files = [p for p in (output / "payload").rglob("*") if p.is_file()]
    expected_count = (
        len(image_rows)
        + len(boot_notice_rows)
        + len(data_spec_image_rows)
        + len(character_name_rows)
        + len(telop_rows) * 2
        + len(location_date_rows) * 2
        + len(FONT_HASHES)
        + 1
        + len(telop_position_files)
    )
    if len(files) != expected_count:
        raise RuntimeError(f"payload file count: expected {expected_count}, got {len(files)}")
    allowed_telop_root = assets / "data_spec" / "adv" / "game" / "chr" / "00no_text_telop"
    allowed_runtime_script_root = (
        assets / "data_spec" / "adv" / "game" / "scr" / "localized"
    )
    allowed_data_spec_gui_root = assets / "data_spec" / "gui" / "textures"
    allowed_event_card_root = (
        assets
        / "data_spec"
        / "adv"
        / "game"
        / "bg"
        / "30イベント絵"
        / "010_TEイベント絵"
        / "050_帝都燃ゆ"
        / "140_テロップ"
    )
    for path in files:
        if "voice" in path.parts:
            raise RuntimeError(f"story/speaker asset leaked into payload: {path}")
        if "scr" in path.parts:
            try:
                relative_script = path.relative_to(allowed_runtime_script_root).as_posix()
            except ValueError as exc:
                raise RuntimeError(
                    f"unapproved story asset leaked into payload: {path}"
                ) from exc
            if relative_script not in telop_position_files:
                raise RuntimeError(f"unapproved story asset leaked into payload: {path}")
        if (
            "data_spec" in path.parts
            and path.parent != allowed_telop_root
            and allowed_data_spec_gui_root not in path.parents
            and allowed_runtime_script_root not in path.parents
            and allowed_event_card_root not in path.parents
        ):
            raise RuntimeError(f"unapproved data_spec asset leaked into payload: {path}")
    telop_dir = allowed_telop_root
    validate_tda_boot_notices(payload / "gui" / "textures", boot_notice_rows)
    validate_character_name_cards(allowed_data_spec_gui_root, character_name_rows)
    validate_location_date_cards(allowed_event_card_root, location_date_rows)
    for row in telop_rows:
        asset_id = row["asset_id"]
        base = telop_dir / f"add_telop_{asset_id}.webp"
        en = telop_dir / f"add_telop_{asset_id}_en.webp"
        with Image.open(base) as image:
            if image.size != (1280, 720):
                raise RuntimeError(f"wrong telop canvas: {base} {image.size}")
        if sha256(base) != sha256(en):
            raise RuntimeError(f"base/EN technical slots differ: {asset_id}")
    for name, expected in FONT_BINARY_HASHES.items():
        if sha256(payload / "gui" / "font" / name) != expected:
            raise RuntimeError(f"TDA font validation failed: {name}")
    expected_config = font_config_text()
    for name in FONT_CONFIG_NAMES:
        if (payload / "gui" / "font" / name).read_text(encoding="utf-8") != expected_config:
            raise RuntimeError(f"Imperial font-role config validation failed: {name}")
def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--gui-root", required=True, type=Path)
    parser.add_argument("--data-spec-gui-root", required=True, type=Path)
    parser.add_argument("--uistring-dec", required=True, type=Path)
    parser.add_argument("--tda-font-root", required=True, type=Path)
    parser.add_argument("--tda-boot-root", required=True, type=Path)
    parser.add_argument("--fsnr-main", required=True, type=Path)
    parser.add_argument("--jp-script-root", required=True, type=Path)
    parser.add_argument("--telop-reference-root", required=True, type=Path)
    parser.add_argument("--location-date-card-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main() -> int:
    args = create_parser().parse_args()

    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite build directory: {args.output}")
    args.output.mkdir(parents=True)
    phase = args.repo / "chapters" / "imperial-capital-burns" / "phase1"
    payload_assets = args.output / "payload" / "root" / "assets"
    payload_data = payload_assets / "data"
    textures = payload_data / "gui" / "textures"

    image_rows = read_tsv(phase / "image_ui_copy.tsv")
    copy_image_rows(args.gui_root, textures, image_rows)
    boot_notice_rows = read_tsv(phase / "boot_notice_tda.tsv")
    copy_tda_boot_notice_rows(args.tda_boot_root, textures, boot_notice_rows)

    data_spec_image_rows = read_tsv(phase / "image_ui_copy_data_spec.tsv")
    data_spec_textures = payload_assets / "data_spec" / "gui" / "textures"
    copy_image_rows(args.data_spec_gui_root, data_spec_textures, data_spec_image_rows)

    payload_font_root = payload_data / "gui" / "font"
    copy_fonts(args.tda_font_root, payload_font_root)
    write_font_configs(payload_font_root)
    font_path = args.tda_font_root / "SourceHanSansSC-Bold.otf"
    character_name_rows = read_tsv(phase / "character_name_cards_ja_zh.tsv")
    render_character_name_rows(
        args.data_spec_gui_root,
        data_spec_textures,
        font_path,
        character_name_rows,
    )

    work = args.output / "build-work"
    work.mkdir()
    patched_dec = work / "uistring.epk_dec"
    patcher = args.repo / "tools" / "uistring" / "patch_uistring.py"
    run_checked(
        [
            sys.executable,
            str(patcher),
            str(args.uistring_dec),
            "--changes",
            str(phase / "uistring_ja_zh.tsv"),
            "--output",
            str(patched_dec),
        ]
    )
    run_checked([str(args.fsnr_main), "enc", str(patched_dec)])
    encoded = work / "uistring.epk_enc"
    target_epk = payload_data / "epk" / "uistring.epk"
    target_epk.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(encoded, target_epk)

    telop_rows = read_tsv(phase / "telop_ja_zh.tsv")
    manifest_telops = {row["asset_id"] for row in telop_rows}
    referenced_telops = find_telop_references(args.jp_script_root)
    if manifest_telops != referenced_telops:
        missing = sorted(referenced_telops - manifest_telops)
        extra = sorted(manifest_telops - referenced_telops)
        raise RuntimeError(f"telop reference mismatch: missing={missing} extra={extra}")
    calls = collect_telop_calls(args.jp_script_root)
    canvas_size, bottom_y, invalid_references = infer_telop_reference_layout(
        args.telop_reference_root, telop_rows
    )
    telop_dir = payload_assets / "data_spec" / "adv" / "game" / "chr" / "00no_text_telop"
    for row in telop_rows:
        asset_id = row["asset_id"]
        base = telop_dir / f"add_telop_{asset_id}.webp"
        render_telop(row["zh_cn"], font_path, base, canvas_size, bottom_y)
        shutil.copyfile(base, telop_dir / f"add_telop_{asset_id}_en.webp")

    location_date_rows = read_tsv(phase / "location_date_cards_ja_zh.tsv")
    manifest_cards = {row["source_relative"] for row in location_date_rows}
    referenced_cards = find_location_date_references(args.jp_script_root)
    if manifest_cards != referenced_cards:
        missing = sorted(referenced_cards - manifest_cards)
        extra = sorted(manifest_cards - referenced_cards)
        raise RuntimeError(f"location/date reference mismatch: missing={missing} extra={extra}")
    event_card_root = (
        payload_assets
        / "data_spec"
        / "adv"
        / "game"
        / "bg"
        / "30イベント絵"
        / "010_TEイベント絵"
        / "050_帝都燃ゆ"
        / "140_テロップ"
    )
    render_location_date_rows(
        args.location_date_card_root,
        event_card_root,
        font_path,
        location_date_rows,
    )
    write_location_date_layout_audit(
        location_date_rows,
        args.location_date_card_root,
        event_card_root,
        args.output / "preview" / "location-date-card-layout-audit.tsv",
    )
    write_location_date_chapter_checklist(
        collect_location_date_calls(args.jp_script_root / "localized"),
        location_date_rows,
        args.output / "preview" / "location-date-card-chapter-checklist.tsv",
    )
    write_telop_audit(
        telop_rows,
        telop_dir,
        args.output / "preview" / "telop-audit.tsv",
    )
    write_telop_chapter_checklist(
        calls,
        telop_rows,
        args.output / "preview" / "telop-chapter-checklist.tsv",
    )
    write_telop_layout_audit(
        telop_rows,
        args.telop_reference_root,
        telop_dir,
        invalid_references,
        args.output / "preview" / "telop-layout-audit.tsv",
    )
    localized_script_root = args.jp_script_root / "localized"
    if not localized_script_root.is_dir():
        raise FileNotFoundError(localized_script_root)
    runtime_script_root = (
        payload_assets / "data_spec" / "adv" / "game" / "scr" / "localized"
    )
    telop_position_files = patch_telop_positions(
        localized_script_root, runtime_script_root
    )
    if len(telop_position_files) != 7 or sum(telop_position_files.values()) != 26:
        raise RuntimeError(
            "unexpected telop position patch scope: "
            f"files={len(telop_position_files)} replacements="
            f"{sum(telop_position_files.values())}"
        )
    write_telop_position_audit(
        telop_position_files,
        args.output / "preview" / "telop-position-audit.tsv",
    )

    validate(
        args.output,
        image_rows,
        boot_notice_rows,
        data_spec_image_rows,
        character_name_rows,
        telop_rows,
        location_date_rows,
        telop_position_files,
    )
    create_preview(telop_dir, args.output / "preview" / "telop-contact-sheet.png")
    create_ui_preview(textures, args.output / "preview" / "image-ui-contact-sheet.png")
    create_location_date_preview(
        event_card_root,
        location_date_rows,
        args.output / "preview" / "location-date-card-contact-sheet.png",
    )
    shutil.rmtree(work)
    write_installers(args.output)
    print(f"built {args.output}")
    print(f"payload files: {len(list((args.output / 'payload').rglob('*.*')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
