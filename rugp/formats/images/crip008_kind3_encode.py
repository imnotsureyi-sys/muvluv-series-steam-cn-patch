#!/usr/bin/env python3
"""Encode an RGBA image as a transparent CRip008 kind=3 resource.

The encoder deliberately uses a large, simple subset of the codec: 8/8/8
channels, one literal RGB segment per row, and alpha runs only for fully
transparent or fully opaque pixels.  Partial alpha is represented by the
format's native 1..31 codes.  This is intended for RUO overlays, so output
size is not constrained by the old archive extent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .crip008_kind2_encode import (
        HEADER_SIZE,
        MsbBitReader,
        MsbBitWriter,
        clamp_relative,
        parse_header,
        read_png_rgba,
        read_template,
    )
except ImportError:  # Direct script execution.
    from crip008_kind2_encode import (  # type: ignore
        HEADER_SIZE,
        MsbBitReader,
        MsbBitWriter,
        clamp_relative,
        parse_header,
        read_png_rgba,
        read_template,
    )


def rgba_to_native_kind3(rgba: bytes) -> bytes:
    """Convert review RGBA to the kind=3 native G,B,R,alpha-code layout."""
    native = bytearray(len(rgba))
    for pos in range(0, len(rgba), 4):
        red, green, blue, alpha = rgba[pos : pos + 4]
        alpha_code = min(32, max(0, round(alpha * 32 / 255)))
        native_alpha = 0x80 if alpha_code == 32 else alpha_code << 2
        native[pos : pos + 4] = bytes((green, blue, red, native_alpha))
    return bytes(native)


def native_alpha_code(alpha: int) -> int:
    if alpha in (0x80, 0xFF):
        return 32
    if alpha == 0:
        return 0
    if alpha & 3:
        raise ValueError(f"native kind=3 alpha is not representable: 0x{alpha:02X}")
    code = alpha >> 2
    if not 1 <= code <= 31:
        raise ValueError(f"native kind=3 alpha is out of range: 0x{alpha:02X}")
    return code


def encode_native_pixels(
    native_canvas: bytes,
    *,
    width: int,
    height: int,
    x_offset: int,
    y_offset: int,
    draw_width: int,
    draw_height: int,
) -> tuple[bytes, int]:
    if len(native_canvas) != width * height * 4:
        raise ValueError("native canvas size does not match the CRip008 header")
    if not (
        0 <= x_offset <= width
        and 0 <= y_offset <= height
        and 0 < draw_width <= width - x_offset
        and 0 < draw_height <= height - y_offset
    ):
        raise ValueError("kind=3 draw rectangle is outside the image canvas")

    writer = MsbBitWriter()
    for y in range(draw_height):
        row: list[tuple[int, int, int, int]] = []
        for x in range(draw_width):
            pos = ((y_offset + y) * width + x_offset + x) * 4
            c0, green, red, alpha = native_canvas[pos : pos + 4]
            row.append((c0, green, red, native_alpha_code(alpha)))

        visible_total = sum(alpha != 0 for _, _, _, alpha in row)
        first_visible = True
        alpha_state = 0
        rgb_state = 0
        green_acc = 0
        x = 0
        while x < draw_width:
            target_alpha = row[x][3]
            if target_alpha in (0, 32):
                run = 1
                while x + run < draw_width and row[x + run][3] == target_alpha:
                    run += 1
                writer.signed(target_alpha - alpha_state)
                writer.unsigned(run)
                alpha_state = target_alpha
                if target_alpha == 0:
                    x += run
                    continue
                visible_run = run
            else:
                writer.signed(target_alpha - alpha_state)
                alpha_state = target_alpha
                visible_run = 1

            for _ in range(visible_run):
                if first_visible:
                    writer.unsigned(visible_total)
                    first_visible = False
                    green_acc = 0
                target_c0, target_g, target_r, _ = row[x]
                current_c0 = rgb_state & 0xFF
                current_g = (rgb_state >> 8) & 0xFF
                current_r = (rgb_state >> 16) & 0xFF
                green = target_g - current_g
                green_base = clamp_relative(green_acc, current_g)
                raw_g = green - green_base
                green_acc = green
                c0_base = clamp_relative(green, current_c0)
                r_base = clamp_relative(green, current_r)
                c0_inc = (target_c0 - current_c0) - c0_base
                r_inc = (target_r - current_r) - r_base
                writer.bit(0)
                writer.signed(raw_g)
                writer.signed(c0_inc)
                writer.signed(r_inc)
                rgb_state = target_c0 | (target_g << 8) | (target_r << 16)
                x += 1

        if visible_total == 0 and x != draw_width:
            raise AssertionError("transparent-row encoder did not consume the row")
    return writer.finish(), writer.bit_count


def decode_generated_payload(
    payload: bytes,
    *,
    width: int,
    height: int,
    x_offset: int,
    y_offset: int,
    draw_width: int,
    draw_height: int,
) -> bytes:
    reader = MsbBitReader(payload)
    output = bytearray(width * height * 4)
    for y in range(draw_height):
        alpha = 0
        rgb = 0
        green_acc = 0
        repeat_count = 0
        repeat = True
        chunk_size = 0
        x = 0
        while x < draw_width:
            if chunk_size == 0:
                alpha += reader.signed()
                if not 0 <= alpha <= 32:
                    raise ValueError(f"decoded alpha {alpha} is invalid")
                if alpha in (0, 32):
                    chunk_size = reader.unsigned()
            if alpha == 0:
                x += chunk_size
                chunk_size = 0
                continue
            if alpha == 32:
                chunk_size -= 1
            if repeat_count == 0:
                repeat_count = reader.unsigned()
                repeat = not repeat
                green_acc = 0
            repeat_count -= 1
            if not repeat:
                if reader.bit():
                    raise ValueError("generated kind=3 payload unexpectedly copies above")
                raw_g = reader.signed()
                c0_inc = reader.signed()
                r_inc = reader.signed()
                current_c0 = rgb & 0xFF
                current_g = (rgb >> 8) & 0xFF
                current_r = (rgb >> 16) & 0xFF
                green_base = clamp_relative(green_acc, current_g)
                green = raw_g + green_base
                green_acc = green
                c0_base = clamp_relative(green, current_c0)
                r_base = clamp_relative(green, current_r)
                rgb = (
                    rgb
                    + c0_base
                    + c0_inc
                    + (green << 8)
                    + ((r_base + r_inc) << 16)
                ) & 0xFFFFFFFF
            out = ((y_offset + y) * width + x_offset + x) * 4
            native_alpha = 0x80 if alpha == 32 else alpha << 2
            output[out : out + 4] = bytes(
                (rgb & 0xFF, (rgb >> 8) & 0xFF, (rgb >> 16) & 0xFF, native_alpha)
            )
            x += 1
    return bytes(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    template = parser.add_mutually_exclusive_group(required=True)
    template.add_argument("--template-record", type=Path)
    template.add_argument("--template-rio", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    image = parser.add_mutually_exclusive_group(required=True)
    image.add_argument("--png", type=Path)
    image.add_argument("--native", type=Path, help="native G,B,R,A byte buffer")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    template_record = read_template(args)
    old_header = parse_header(template_record)
    if old_header.kind != 3:
        raise ValueError(f"template is CRip008 kind={old_header.kind}, not kind=3")
    draw_width = old_header.draw_width or old_header.width
    draw_height = old_header.draw_height or old_header.height

    if args.native:
        native = args.native.read_bytes()
        image_width, image_height = old_header.width, old_header.height
    else:
        image_width, image_height, rgba = read_png_rgba(args.png)
        native = rgba_to_native_kind3(rgba)
    if (image_width, image_height) != (old_header.width, old_header.height):
        raise ValueError(
            f"image is {image_width}x{image_height}; template is "
            f"{old_header.width}x{old_header.height}"
        )

    parameters = dict(
        width=old_header.width,
        height=old_header.height,
        x_offset=old_header.x_offset,
        y_offset=old_header.y_offset,
        draw_width=draw_width,
        draw_height=draw_height,
    )
    payload, bit_count = encode_native_pixels(native, **parameters)
    verified = decode_generated_payload(payload, **parameters)
    expected = bytearray(old_header.width * old_header.height * 4)
    for y in range(draw_height):
        start = ((old_header.y_offset + y) * old_header.width + old_header.x_offset) * 4
        end = start + draw_width * 4
        expected[start:end] = native[start:end]
    for pos in range(3, len(expected), 4):
        alpha = expected[pos]
        if alpha == 0xFF:
            expected[pos] = 0x80
    if verified != expected:
        raise AssertionError("internal CRip008 kind=3 round-trip verification failed")

    header = bytearray(template_record[:HEADER_SIZE])
    header[0x16] |= 0x02
    header[0x17:0x1A] = b"\x08\x08\x08"
    header[0x1D:0x21] = len(payload).to_bytes(4, "little")
    record = bytes(header) + payload
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(record)
    manifest_path = args.manifest or args.output.with_suffix(args.output.suffix + ".json")
    report = {
        "format": "CRip008",
        "kind": 3,
        "strategy": "one literal RGB segment per row; native alpha runs; 8/8/8 channels",
        "canvas": [old_header.width, old_header.height],
        "draw_rect": [
            old_header.x_offset,
            old_header.y_offset,
            draw_width,
            draw_height,
        ],
        "old_channel_bits": [old_header.b_bits, old_header.g_bits, old_header.r_bits],
        "new_channel_bits": [8, 8, 8],
        "old_payload_length": old_header.payload_length,
        "new_payload_length": len(payload),
        "new_record_length": len(record),
        "encoded_bit_count": bit_count,
        "pixel_roundtrip_exact_after_native_alpha_quantization": True,
        "sha256": hashlib.sha256(record).hexdigest(),
        "output": str(args.output.resolve()),
    }
    manifest_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
