#!/usr/bin/env python3
"""Strict decoder for standard AGES Cr6Ti image records.

Cr6Ti and CRip008 records share the serialized-object prefix ``00 04 45``.
They must therefore not be distinguished by that signature alone.  A standard
Cr6Ti record has this exact framing::

    0x2c-byte header + u32le payload_length_at_0x20 + 0x0000 trailer

The compressed pixel stream is LSB-first.  This module validates the complete
record framing, draw rectangle, every decoded run, the bitstream boundary, and
the zero padding at the end of the payload.  It intentionally does not handle
the two observed legacy 0x28-byte/flags=3 records.
"""

from __future__ import annotations

import argparse
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MAGIC = b"\x00\x04\x45"
HEADER_SIZE = 0x2C
TRAILER = b"\x00\x00"
MAX_ZERO_PADDING_BITS = 15  # the native stream is stored on a 16-bit boundary


@dataclass(frozen=True)
class Cr6TiHeader:
    width: int
    height: int
    x_offset: int
    y_offset: int
    draw_width: int
    draw_height: int
    kind: int
    depth: int
    flags: int
    payload_length: int
    header_size: int = HEADER_SIZE
    trailer_size: int = len(TRAILER)

    @property
    def exact_extent(self) -> int:
        return self.header_size + self.payload_length + self.trailer_size


@dataclass(frozen=True)
class DecodeStats:
    decoded_pixels: int
    literal_runs: int
    repeated_pixels: int
    copied_from_above: int
    delta_pixels: int
    consumed_bits: int
    payload_bits: int
    zero_padding_bits: int


@dataclass(frozen=True)
class DecodeResult:
    header: Cr6TiHeader
    rgba: bytes
    stats: DecodeStats


class LsbBitReader:
    """Bounds-checked LSB-first bit reader used by the native Cr6Ti codec."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.bit_position = 0

    @property
    def remaining_bits(self) -> int:
        return len(self.data) * 8 - self.bit_position

    def bit(self) -> int:
        if self.bit_position >= len(self.data) * 8:
            raise ValueError(
                f"Cr6Ti bitstream ended at bit {self.bit_position} "
                f"of {len(self.data) * 8}"
            )
        byte_index, bit_index = divmod(self.bit_position, 8)
        self.bit_position += 1
        return (self.data[byte_index] >> bit_index) & 1

    def signed(self) -> int:
        if self.bit() == 0:
            return 0
        sign = -1 if self.bit() else 1
        value = 1
        for _ in range(6):
            if self.bit() == 0:
                return sign * value
            value = (value << 1) | self.bit()
        return sign * value

    def unsigned(self) -> int:
        if self.bit() == 0:
            return 0
        value = 1
        # Native streams only need short run lengths, but a hard ceiling also
        # prevents malformed data from creating an unbounded prefix loop.
        for _ in range(31):
            value = (value << 1) | self.bit()
            if self.bit() == 0:
                return value - 1
        raise ValueError("Cr6Ti unsigned code exceeds 31 continuation pairs")

    def validate_zero_padding(self) -> int:
        remaining = self.remaining_bits
        if remaining > MAX_ZERO_PADDING_BITS:
            raise ValueError(
                f"Cr6Ti decoder left {remaining} bits; expected at most "
                f"{MAX_ZERO_PADDING_BITS} alignment bits"
            )
        for pos in range(self.bit_position, len(self.data) * 8):
            if (self.data[pos >> 3] >> (pos & 7)) & 1:
                raise ValueError(f"Cr6Ti padding contains a set bit at payload bit {pos}")
        return remaining


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _clamp8(value: int) -> int:
    return max(0, min(255, value))


def parse_standard_cr6ti_record(record: bytes) -> Cr6TiHeader:
    """Parse and strictly identify one complete standard Cr6Ti record."""

    if len(record) < HEADER_SIZE + len(TRAILER):
        raise ValueError("standard Cr6Ti record is truncated")
    if record[:3] != MAGIC:
        raise ValueError(f"not an AGES image object: magic={record[:3].hex()}")

    width = _u16(record, 0x06)
    height = _u16(record, 0x08)
    x_offset = int.from_bytes(record[0x0A:0x0C], "little", signed=True)
    y_offset = int.from_bytes(record[0x0C:0x0E], "little", signed=True)
    draw_width = _u16(record, 0x0E) or width
    draw_height = _u16(record, 0x10) or height
    kind = record[0x12]
    depth = record[0x13]
    flags = record[0x16]
    payload_length = int.from_bytes(record[0x20:0x24], "little")
    header = Cr6TiHeader(
        width=width,
        height=height,
        x_offset=x_offset,
        y_offset=y_offset,
        draw_width=draw_width,
        draw_height=draw_height,
        kind=kind,
        depth=depth,
        flags=flags,
        payload_length=payload_length,
    )

    if width <= 0 or height <= 0:
        raise ValueError(f"invalid Cr6Ti canvas: {width}x{height}")
    if kind not in (2, 3):
        raise ValueError(f"unsupported standard Cr6Ti kind: {kind}")
    if (
        draw_width <= 0
        or draw_height <= 0
        or x_offset < 0
        or y_offset < 0
        or x_offset + draw_width > width
        or y_offset + draw_height > height
    ):
        raise ValueError(
            "Cr6Ti draw rectangle is outside its canvas: "
            f"canvas={width}x{height}, rect=({x_offset},{y_offset}) "
            f"{draw_width}x{draw_height}"
        )
    if payload_length <= 0:
        raise ValueError("Cr6Ti payload length at 0x20 is zero")
    if len(record) != header.exact_extent:
        raise ValueError(
            f"record extent {len(record)} does not equal the standard Cr6Ti "
            f"formula 0x2c + {payload_length} + 2 = {header.exact_extent}"
        )
    if record[-2:] != TRAILER:
        raise ValueError(f"standard Cr6Ti trailer is {record[-2:].hex()}, not 0000")
    return header


def is_exact_standard_cr6ti_record(record: bytes) -> bool:
    try:
        parse_standard_cr6ti_record(record)
    except ValueError:
        return False
    return True


def _put_rgba(output: bytearray, width: int, x: int, y: int, r: int, g: int, b: int, a: int) -> None:
    pos = (y * width + x) * 4
    # The native predictor variables are historically named r/g/b, while the
    # byte order reaching the renderer is b,g,r.  This conversion produces
    # conventional PNG RGBA and is visually verified against PF.
    output[pos : pos + 4] = bytes((b, g, r, a))


def _decode_kind2(payload: bytes, header: Cr6TiHeader) -> tuple[bytes, DecodeStats]:
    bits = LsbBitReader(payload)
    width = header.draw_width
    height = header.draw_height
    rect = bytearray(width * height * 4)
    previous_r = [0] * width
    previous_g = [0] * width
    previous_b = [0] * width
    literal_runs = repeated_pixels = copied_from_above = delta_pixels = 0

    for y in range(height):
        r = g = b = 0
        dr = dg = db = 0
        x = 0
        while x < width:
            literal_count = bits.unsigned() + 1
            if literal_count > width - x:
                raise ValueError(
                    f"Cr6Ti literal run {literal_count} exceeds row remainder "
                    f"{width - x} at y={y}, x={x}"
                )
            literal_runs += 1
            for _ in range(literal_count):
                if bits.bit():
                    r, g, b = previous_r[x], previous_g[x], previous_b[x]
                    dr = dg = db = 0
                    copied_from_above += 1
                else:
                    prediction = _clamp8(g + dg * 2) - g
                    dg = bits.signed()
                    dg = max(-128, min(127, dg + (prediction // 2)))
                    dr = db = dg
                    r = _clamp8(r + dr * 2)
                    g = _clamp8(g + dg * 2)
                    b = _clamp8(b + db * 2)
                    r = _clamp8(r + bits.signed() * 2)
                    b = _clamp8(b + bits.signed() * 2)
                    delta_pixels += 1

                previous_r[x], previous_g[x], previous_b[x] = r, g, b
                _put_rgba(rect, width, x, y, r, g, b, 0xFF)
                x += 1

            if x == width:
                continue
            repeat_count = bits.unsigned() + 1
            if repeat_count > width - x:
                raise ValueError(
                    f"Cr6Ti repeat run {repeat_count} exceeds row remainder "
                    f"{width - x} at y={y}, x={x}"
                )
            repeated_pixels += repeat_count
            for _ in range(repeat_count):
                previous_r[x], previous_g[x], previous_b[x] = r, g, b
                _put_rgba(rect, width, x, y, r, g, b, 0xFF)
                x += 1
            dr = dg = db = 0

    consumed = bits.bit_position
    padding = bits.validate_zero_padding()
    stats = DecodeStats(
        decoded_pixels=width * height,
        literal_runs=literal_runs,
        repeated_pixels=repeated_pixels,
        copied_from_above=copied_from_above,
        delta_pixels=delta_pixels,
        consumed_bits=consumed,
        payload_bits=len(payload) * 8,
        zero_padding_bits=padding,
    )
    return bytes(rect), stats


def _write_same_kind3_pixel(
    output: bytearray,
    width: int,
    x: int,
    y: int,
    r: int,
    g: int,
    b: int,
    alpha_code: int,
) -> None:
    alpha = 0xFF if alpha_code == 32 else alpha_code * 8
    _put_rgba(output, width, x, y, r, g, b, alpha)


def _decode_kind3(payload: bytes, header: Cr6TiHeader) -> tuple[bytes, DecodeStats]:
    """Decode the standard transparent branch used by PF/PM Cr6Ti."""

    bits = LsbBitReader(payload)
    width = header.draw_width
    height = header.draw_height
    rect = bytearray(width * height * 4)
    previous_r = [0] * width
    previous_g = [0] * width
    previous_b = [0] * width
    literal_runs = repeated_pixels = copied_from_above = delta_pixels = 0

    for y in range(height):
        r = g = b = 0
        alpha_code = 0
        dg = 0
        alpha_remaining = 0
        frame_remaining = 0
        frame_mode = True
        x = 0
        while x < width:
            alpha_remaining -= 1
            if alpha_remaining < 0:
                alpha_code += bits.signed()
                if not 0 <= alpha_code <= 32:
                    raise ValueError(
                        f"Cr6Ti alpha code {alpha_code} is invalid at y={y}, x={x}"
                    )
                if alpha_code == 0:
                    transparent_count = bits.unsigned() + 1
                    if transparent_count > width - x:
                        raise ValueError(
                            f"transparent run {transparent_count} exceeds row remainder "
                            f"{width - x} at y={y}, x={x}"
                        )
                    x += transparent_count
                    repeated_pixels += transparent_count
                    continue
                if alpha_code == 32:
                    alpha_remaining = bits.unsigned()

            frame_remaining -= 1
            if frame_remaining < 0:
                frame_mode = not frame_mode
                frame_remaining = bits.unsigned()
                dg = 0
                literal_runs += 1

            if frame_mode:
                if alpha_remaining < frame_remaining:
                    _write_same_kind3_pixel(rect, width, x, y, r, g, b, alpha_code)
                    previous_r[x], previous_g[x], previous_b[x] = r, g, b
                    x += 1
                    repeated_pixels += 1
                else:
                    if frame_remaining > 0:
                        alpha_remaining -= frame_remaining
                    run = frame_remaining + 1
                    if run > width - x:
                        raise ValueError(
                            f"frame run {run} exceeds row remainder {width - x} "
                            f"at y={y}, x={x}"
                        )
                    for _ in range(run):
                        _write_same_kind3_pixel(rect, width, x, y, r, g, b, alpha_code)
                        previous_r[x], previous_g[x], previous_b[x] = r, g, b
                        x += 1
                    repeated_pixels += run
                    frame_remaining = 0
            elif bits.bit():
                r, g, b = previous_r[x], previous_g[x], previous_b[x]
                _write_same_kind3_pixel(rect, width, x, y, r, g, b, alpha_code)
                previous_r[x], previous_g[x], previous_b[x] = r, g, b
                x += 1
                dg = 0
                copied_from_above += 1
            else:
                prediction = _clamp8(g + dg * 2) - g
                if prediction < -128:
                    prediction += 256
                if prediction > 127:
                    prediction -= 256
                dg = max(-128, min(127, prediction // 2 + bits.signed()))
                r = _clamp8(r + dg * 2)
                g = _clamp8(g + dg * 2)
                b = _clamp8(b + dg * 2)
                r = _clamp8(r + bits.signed() * 2) & 0xFE
                b = _clamp8(b + bits.signed() * 2) & 0xFE
                g &= 0xFE
                _write_same_kind3_pixel(rect, width, x, y, r, g, b, alpha_code)
                previous_r[x], previous_g[x], previous_b[x] = r, g, b
                x += 1
                delta_pixels += 1

    consumed = bits.bit_position
    padding = bits.validate_zero_padding()
    stats = DecodeStats(
        decoded_pixels=width * height,
        literal_runs=literal_runs,
        repeated_pixels=repeated_pixels,
        copied_from_above=copied_from_above,
        delta_pixels=delta_pixels,
        consumed_bits=consumed,
        payload_bits=len(payload) * 8,
        zero_padding_bits=padding,
    )
    return bytes(rect), stats


def decode_standard_cr6ti_record(record: bytes) -> DecodeResult:
    header = parse_standard_cr6ti_record(record)
    payload = record[HEADER_SIZE : HEADER_SIZE + header.payload_length]
    if header.kind == 2:
        rect, stats = _decode_kind2(payload, header)
    else:
        rect, stats = _decode_kind3(payload, header)

    canvas = bytearray(header.width * header.height * 4)
    row_size = header.draw_width * 4
    for y in range(header.draw_height):
        source = y * row_size
        target = ((header.y_offset + y) * header.width + header.x_offset) * 4
        canvas[target : target + row_size] = rect[source : source + row_size]
    return DecodeResult(header=header, rgba=bytes(canvas), stats=stats)


def read_exact_record(path: Path, offset: int, extent: int) -> bytes:
    if offset < 0 or extent <= 0:
        raise ValueError("offset and extent must be positive")
    with path.open("rb") as stream:
        stream.seek(offset)
        record = stream.read(extent)
    if len(record) != extent:
        raise ValueError(
            f"record at 0x{offset:X} is truncated: read {len(record)}, expected {extent}"
        )
    return record


def png_rgba_bytes(width: int, height: int, rgba: bytes) -> bytes:
    if len(rgba) != width * height * 4:
        raise ValueError("RGBA length does not match PNG dimensions")

    def chunk(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body))
            + kind
            + body
            + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
        )

    rows = bytearray()
    stride = width * 4
    for y in range(height):
        rows.append(0)
        rows.extend(rgba[y * stride : (y + 1) * stride])
    return b"".join(
        (
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(bytes(rows), 9)),
            chunk(b"IEND", b""),
        )
    )


def write_png_rgba(path: Path, width: int, height: int, rgba: bytes) -> None:
    png = png_rgba_bytes(width, height, rgba)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def pixel_summary(rgba: bytes) -> dict[str, object]:
    pixels = len(rgba) // 4
    channels = [rgba[index::4] for index in range(4)]
    return {
        "pixel_count": pixels,
        "channel_order": "RGBA",
        "minimum": [min(channel) for channel in channels],
        "maximum": [max(channel) for channel in channels],
        "mean": [sum(channel) / pixels for channel in channels],
        "unique_values": [len(set(channel)) for channel in channels],
        "all_black_rgb": all(not value for index, value in enumerate(rgba) if index % 4 != 3),
    }


def _parse_int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--offset", type=_parse_int, default=0)
    parser.add_argument("--extent", type=_parse_int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    # Keep the historical module entry point, but route publication through
    # the shared create-only decoder so it cannot leak absolute paths or
    # silently overwrite an earlier review artifact.
    from rUGP.tools.images.decode_record import main as safe_decode_main

    forwarded = [
        "--source", str(args.source),
        "--offset", str(args.offset),
        "--extent", str(args.extent),
        "--codec", "cr6ti",
        "--output", str(args.output),
    ]
    if args.manifest is not None:
        forwarded.extend(("--report", str(args.manifest)))
    return safe_decode_main(forwarded)


if __name__ == "__main__":
    raise SystemExit(main())
