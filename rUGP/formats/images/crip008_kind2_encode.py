#!/usr/bin/env python3
"""Encode an opaque image as a CRip008 kind=2 resource.

This intentionally favours simplicity and correctness over compression.  Every
row is emitted as one literal run and the output is converted to 8/8/8 channel
precision.  The resulting resource is usually much larger than the original,
which is acceptable when it is stored in an AGES ``.rio.ruo1`` redirect.

The PNG reader is dependency-free and accepts non-interlaced 8-bit PNG files.
An already-decoded native CRip008 pixel buffer can also be supplied for exact
codec round-trip tests.  Native kind=2 pixels are four bytes per pixel in the
order used by the game decoder: B, G, R, 0x80.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


HEADER_SIZE = 0x29
MAX_CODED_INT = 0x1FFF


@dataclass(frozen=True)
class Header:
    width: int
    height: int
    x_offset: int
    y_offset: int
    draw_width: int
    draw_height: int
    kind: int
    depth: int
    flags: int
    b_bits: int
    g_bits: int
    r_bits: int
    payload_length: int


def parse_header(data: bytes) -> Header:
    if len(data) < HEADER_SIZE:
        raise ValueError("CRip008 header is truncated")
    if data[:3] != b"\x00\x04\x45":
        raise ValueError(f"not a CRip008 record: magic={data[:3].hex()}")
    return Header(
        width=int.from_bytes(data[0x06:0x08], "little"),
        height=int.from_bytes(data[0x08:0x0A], "little"),
        x_offset=int.from_bytes(data[0x0A:0x0C], "little", signed=True),
        y_offset=int.from_bytes(data[0x0C:0x0E], "little", signed=True),
        draw_width=int.from_bytes(data[0x0E:0x10], "little"),
        draw_height=int.from_bytes(data[0x10:0x12], "little"),
        kind=data[0x12],
        depth=data[0x13],
        flags=data[0x16],
        b_bits=data[0x17],
        g_bits=data[0x18],
        r_bits=data[0x19],
        payload_length=int.from_bytes(data[0x1D:0x21], "little"),
    )


class MsbBitWriter:
    def __init__(self) -> None:
        self.output = bytearray()
        self.current = 0
        self.used = 0
        self.bit_count = 0

    def bit(self, value: int | bool) -> None:
        self.current = (self.current << 1) | (1 if value else 0)
        self.used += 1
        self.bit_count += 1
        if self.used == 8:
            self.output.append(self.current)
            self.current = 0
            self.used = 0

    def unsigned(self, value: int) -> None:
        # Inverse of CRip008 NativeMsbBitReader.read_int().  The decoder has a
        # two-table ceiling, so values above 8191 must never be emitted.
        if not 1 <= value <= MAX_CODED_INT:
            raise ValueError(f"CRip008 unsigned integer is out of range: {value}")
        for digit in bin(value)[3:]:
            self.bit(1)
            self.bit(digit == "1")
        self.bit(0)

    def signed(self, value: int) -> None:
        if value == 0:
            self.bit(0)
            return
        if abs(value) > MAX_CODED_INT:
            raise ValueError(f"CRip008 signed integer is out of range: {value}")
        self.bit(1)
        self.bit(value < 0)
        self.unsigned(abs(value))

    def finish(self) -> bytes:
        if self.used:
            self.output.append(self.current << (8 - self.used))
            self.current = 0
            self.used = 0
        return bytes(self.output)


class MsbBitReader:
    """Small reference reader used to verify every generated resource."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.bit_pos = 0

    def bit(self) -> int:
        byte_pos, bit_in_byte = divmod(self.bit_pos, 8)
        if byte_pos >= len(self.data):
            raise ValueError("CRip008 payload ended during verification")
        self.bit_pos += 1
        return (self.data[byte_pos] >> (7 - bit_in_byte)) & 1

    def unsigned(self) -> int:
        value = 1
        while self.bit():
            value = value * 2 + self.bit()
            if value > MAX_CODED_INT:
                raise ValueError("CRip008 integer exceeds native decoder range")
        return value

    def signed(self) -> int:
        if not self.bit():
            return 0
        negative = bool(self.bit())
        value = self.unsigned()
        return -value if negative else value


def clamp_relative(value: int, current: int, maximum: int = 0xFF) -> int:
    return max(-current, min(maximum - current, value))


def encode_native_pixels(native: bytes, width: int, height: int) -> tuple[bytes, int]:
    expected = width * height * 4
    if len(native) != expected:
        raise ValueError(f"native pixel length {len(native)} != {expected}")

    writer = MsbBitWriter()
    for y in range(height):
        writer.unsigned(width)
        state = 0
        green_acc = 0
        for x in range(width):
            index = (y * width + x) * 4
            target_b0, target_g, target_r, alpha = native[index : index + 4]
            if alpha not in (0x80, 0xFF):
                raise ValueError(
                    f"kind=2 is opaque; native alpha at ({x},{y}) is 0x{alpha:02X}"
                )

            current_b0 = state & 0xFF
            current_g = (state >> 8) & 0xFF
            current_r = (state >> 16) & 0xFF

            green = target_g - current_g
            green_base = clamp_relative(green_acc, current_g)
            raw_g = green - green_base
            green_acc = green

            # flags bit 1 (predict R/B from G) is retained/enforced below.
            b_base = clamp_relative(green, current_b0)
            r_base = clamp_relative(green, current_r)
            b_inc = (target_b0 - current_b0) - b_base
            r_inc = (target_r - current_r) - r_base

            writer.bit(0)  # do not copy the pixel from the previous row
            writer.signed(raw_g)
            writer.signed(b_inc)
            writer.signed(r_inc)
            state = target_b0 | (target_g << 8) | (target_r << 16)

    return writer.finish(), writer.bit_count


def decode_generated_payload(payload: bytes, width: int, height: int) -> bytes:
    """Decode the exact 8/8/8 literal subset emitted by this module."""
    reader = MsbBitReader(payload)
    output = bytearray(width * height * 4)
    for y in range(height):
        literal_count = reader.unsigned()
        if literal_count != width:
            raise ValueError(f"unexpected literal count {literal_count} on row {y}")
        state = 0
        green_acc = 0
        for x in range(width):
            if reader.bit():
                raise ValueError("generated payload unexpectedly uses above-row copy")
            raw_g = reader.signed()
            b_inc = reader.signed()
            r_inc = reader.signed()

            current_b0 = state & 0xFF
            current_g = (state >> 8) & 0xFF
            current_r = (state >> 16) & 0xFF
            green_base = clamp_relative(green_acc, current_g)
            green = raw_g + green_base
            green_acc = green
            b_base = clamp_relative(green, current_b0)
            r_base = clamp_relative(green, current_r)
            state = (
                state
                + b_base
                + b_inc
                + (green << 8)
                + ((r_base + r_inc) << 16)
            ) & 0xFFFFFFFF
            out = (y * width + x) * 4
            output[out : out + 4] = bytes(
                (state & 0xFF, (state >> 8) & 0xFF, (state >> 16) & 0xFF, 0x80)
            )
    return bytes(output)


def paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    dl = abs(estimate - left)
    da = abs(estimate - above)
    du = abs(estimate - upper_left)
    if dl <= da and dl <= du:
        return left
    return above if da <= du else upper_left


def read_png_rgba(path: Path) -> tuple[int, int, bytes]:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG file: {path}")
    pos = 8
    ihdr: tuple[int, int, int, int, int, int, int] | None = None
    idat = bytearray()
    palette: bytes | None = None
    transparency: bytes | None = None
    while pos + 12 <= len(data):
        length = int.from_bytes(data[pos : pos + 4], "big")
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if pos + 12 + length > len(data):
            raise ValueError("PNG chunk is truncated")
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.extend(body)
        elif kind == b"PLTE":
            palette = bytes(body)
        elif kind == b"tRNS":
            transparency = bytes(body)
        elif kind == b"IEND":
            break
        pos += 12 + length
    if ihdr is None:
        raise ValueError("PNG has no IHDR")
    width, height, depth, colour_type, compression, filtering, interlace = ihdr
    if depth != 8 or compression != 0 or filtering != 0 or interlace != 0:
        raise ValueError(
            "only non-interlaced 8-bit PNG is supported "
            f"(depth={depth}, compression={compression}, filter={filtering}, "
            f"interlace={interlace})"
        )
    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if colour_type not in channels_by_type:
        raise ValueError(f"unsupported PNG colour type: {colour_type}")
    channels = channels_by_type[colour_type]
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    if len(raw) != height * (stride + 1):
        raise ValueError("PNG decompressed size does not match IHDR")

    scanlines = bytearray(height * stride)
    src = 0
    for y in range(height):
        filter_type = raw[src]
        src += 1
        row_start = y * stride
        for x in range(stride):
            value = raw[src]
            src += 1
            left = scanlines[row_start + x - channels] if x >= channels else 0
            above = scanlines[row_start + x - stride] if y else 0
            upper_left = (
                scanlines[row_start + x - stride - channels]
                if y and x >= channels
                else 0
            )
            if filter_type == 1:
                value = (value + left) & 0xFF
            elif filter_type == 2:
                value = (value + above) & 0xFF
            elif filter_type == 3:
                value = (value + ((left + above) >> 1)) & 0xFF
            elif filter_type == 4:
                value = (value + paeth(left, above, upper_left)) & 0xFF
            elif filter_type != 0:
                raise ValueError(f"unsupported PNG row filter: {filter_type}")
            scanlines[row_start + x] = value

    rgba = bytearray(width * height * 4)
    for pixel in range(width * height):
        source = pixel * channels
        target = pixel * 4
        if colour_type == 0:
            gray = scanlines[source]
            rgba[target : target + 4] = bytes((gray, gray, gray, 0xFF))
        elif colour_type == 2:
            rgba[target : target + 3] = scanlines[source : source + 3]
            rgba[target + 3] = 0xFF
        elif colour_type == 3:
            index = scanlines[source]
            if palette is None or index * 3 + 3 > len(palette):
                raise ValueError("PNG palette index is invalid")
            rgba[target : target + 3] = palette[index * 3 : index * 3 + 3]
            rgba[target + 3] = (
                transparency[index]
                if transparency is not None and index < len(transparency)
                else 0xFF
            )
        elif colour_type == 4:
            gray, alpha = scanlines[source : source + 2]
            rgba[target : target + 4] = bytes((gray, gray, gray, alpha))
        else:
            rgba[target : target + 4] = scanlines[source : source + 4]
    return width, height, bytes(rgba)


def rgba_to_native(rgba: bytes, *, allow_transparency: bool) -> bytes:
    native = bytearray(len(rgba))
    for pos in range(0, len(rgba), 4):
        red, green, blue, alpha = rgba[pos : pos + 4]
        if alpha != 0xFF and not allow_transparency:
            pixel = pos // 4
            raise ValueError(
                f"kind=2 is opaque but PNG pixel {pixel} has alpha={alpha}; "
                "flatten the image first or pass --discard-alpha"
            )
        native[pos : pos + 4] = bytes((blue, green, red, 0x80))
    return bytes(native)


def read_template(args: argparse.Namespace) -> bytes:
    if args.template_record:
        data = args.template_record.read_bytes()
        header = parse_header(data)
        needed = HEADER_SIZE + header.payload_length
        if len(data) < needed:
            raise ValueError(f"template record is truncated: {len(data)} < {needed}")
        return data[:needed]
    with args.template_rio.open("rb") as stream:
        stream.seek(args.offset)
        head = stream.read(HEADER_SIZE)
        header = parse_header(head)
        payload = stream.read(header.payload_length)
    if len(payload) != header.payload_length:
        raise ValueError("template RIO resource is truncated")
    return head + payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    template = parser.add_mutually_exclusive_group(required=True)
    template.add_argument("--template-record", type=Path)
    template.add_argument("--template-rio", type=Path)
    parser.add_argument("--offset", type=lambda value: int(value, 0), default=0)
    image = parser.add_mutually_exclusive_group(required=True)
    image.add_argument("--png", type=Path)
    image.add_argument("--native", type=Path, help="native B,G,R,A byte buffer")
    parser.add_argument("--discard-alpha", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    template_record = read_template(args)
    old_header = parse_header(template_record)
    if old_header.kind != 2:
        raise ValueError(f"template is CRip008 kind={old_header.kind}, not kind=2")
    if old_header.flags & 0x08:
        raise ValueError("kind=2 flag8 branch is not supported")

    if args.native:
        native = args.native.read_bytes()
        image_width, image_height = old_header.width, old_header.height
    else:
        image_width, image_height, rgba = read_png_rgba(args.png)
        native = rgba_to_native(rgba, allow_transparency=args.discard_alpha)
    if (image_width, image_height) != (old_header.width, old_header.height):
        raise ValueError(
            f"image is {image_width}x{image_height}; template is "
            f"{old_header.width}x{old_header.height}"
        )

    payload, bit_count = encode_native_pixels(native, old_header.width, old_header.height)
    verified = decode_generated_payload(payload, old_header.width, old_header.height)
    expected = bytearray(native)
    for pos in range(3, len(expected), 4):
        expected[pos] = 0x80
    if verified != expected:
        raise AssertionError("internal CRip008 encode/decode verification failed")

    header = bytearray(template_record[:HEADER_SIZE])
    header[0x16] |= 0x02  # use the predictor branch implemented above
    header[0x16] &= ~0x08
    header[0x17:0x1A] = b"\x08\x08\x08"
    header[0x1D:0x21] = len(payload).to_bytes(4, "little")
    record = bytes(header) + payload
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(record)

    manifest_path = args.manifest or args.output.with_suffix(args.output.suffix + ".json")
    report = {
        "format": "CRip008",
        "kind": 2,
        "strategy": "one literal run per row; 8/8/8 channels; no above-row copies or repeats",
        "width": old_header.width,
        "height": old_header.height,
        "old_channel_bits": [old_header.b_bits, old_header.g_bits, old_header.r_bits],
        "new_channel_bits": [8, 8, 8],
        "old_payload_length": old_header.payload_length,
        "new_payload_length": len(payload),
        "new_record_length": len(record),
        "encoded_bit_count": bit_count,
        "pixel_roundtrip_exact": True,
        "sha256": hashlib.sha256(record).hexdigest(),
        "output": str(args.output.resolve()),
    }
    manifest_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
