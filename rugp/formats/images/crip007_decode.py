#!/usr/bin/env python3
"""Decode the legacy CRip007-style RGB branch embedded in PF/PM.

This kind-2 branch has no separately coded alpha plane.  The AGES7 decoder
writes BGR32 pixels with native opacity ``0x80`` in the high byte, including
black ``0x80000000``.  Crucially, vertical prediction masks the pixel with
``0x00FFFFFF`` before testing/subtracting the RGB baseline.  Treating the high
byte as part of the predictor corrupts every later scanline.
"""

from __future__ import annotations


class MsbBitReader:
    """Minimal MSB-first reader for the audited legacy stream."""

    def __init__(self, data: bytes):
        self.data = data
        self.index = 0
        self.bits = 0
        self.cached = 0

    def bits_value(self, count: int) -> int:
        while self.cached < count:
            if self.index >= len(self.data):
                raise EOFError("CRip007 bitstream ended early")
            self.bits = (self.bits << 8) | self.data[self.index]
            self.index += 1
            self.cached += 8
        self.cached -= count
        return (self.bits >> self.cached) & ((1 << count) - 1)

    def bit(self) -> int:
        return self.bits_value(1)


def rip_get_int(bits: MsbBitReader) -> int:
    value = 1
    while bits.bit() > 0:
        value = (value << 1) | bits.bit()
    return value


def rip_get_signed(bits: MsbBitReader) -> int:
    negative = bits.bit() > 0
    value = rip_get_int(bits)
    return -value if negative else value


def rip_quant(q: int, value: int) -> int:
    """Apply the q=0 table used by the four audited PF/PM records.

    GARbro documents additional lossy quantization tables.  They are outside
    this deliberately narrow writer/decoder profile and are rejected instead
    of being loaded from a developer-machine source checkout at runtime.
    """

    if q != 0:
        raise ValueError(f"unsupported scoped CRip007 quant table {q}; expected 0")
    if not 0 <= value <= 0xFF:
        raise ValueError(f"CRip007 quant value out of range: {value}")
    return value & 0x7F


def pack_bgra(output: bytearray, pos: int, pixel: int) -> None:
    output[pos : pos + 4] = pixel.to_bytes(4, "little")


def decode_legacy_rip007_bgra(
    payload: bytes,
    width: int,
    height: int,
    q: int,
    b_bits: int,
    g_bits: int,
    r_bits: int,
    pred_flag: int,
) -> bytearray:
    """Return the native packed BGRA surface for one legacy RGB record."""

    if width <= 0 or height <= 0:
        raise ValueError(f"invalid legacy RIP007 dimensions: {width}x{height}")
    if not all(1 <= value <= 8 for value in (b_bits, g_bits, r_bits)):
        raise ValueError(
            f"invalid legacy RIP007 channel widths: {b_bits}/{g_bits}/{r_bits}"
        )

    bits = MsbBitReader(payload)
    output = bytearray(width * height * 4)
    stride = width * 4
    b_shift = 8 - b_bits
    g_shift = 16 - g_bits
    r_shift = 24 - r_bits
    is_bgr676 = b_bits == 6 and g_bits == 7 and r_bits == 6
    # Use uint32 arithmetic throughout.  The engine uses 0x80 as full native
    # opacity, while the colour predictor operates on the low 24 bits only.
    baseline_rgb = (
        (0xFF >> b_bits)
        | (((0xFF >> g_bits) | ((0xFF >> r_bits) << 8)) << 8)
    ) & 0xFFFFFFFF
    baseline_native = 0x80000000 | baseline_rgb

    for y in range(height):
        rgb = 0
        rgb_previous = 0
        destination = y * stride
        x = 0
        while x < width:
            count = rip_get_int(bits)
            x += count
            if x > width:
                raise ValueError(
                    f"legacy RIP007 literal run exceeds row at y={y}: {x}>{width}"
                )
            while count > 0:
                if bits.bit() > 0:
                    packed_above = (
                        0
                        if y == 0
                        else int.from_bytes(
                            output[destination - stride : destination - stride + 4],
                            "little",
                        )
                    )
                    # Exact AGES7 behaviour at PF 0x005EC8F7: ignore the
                    # BGR32 high byte before the zero test and baseline undo.
                    above_rgb = packed_above & 0x00FFFFFF
                    rgb = (
                        (above_rgb - baseline_rgb) & 0xFFFFFFFF
                        if above_rgb != 0
                        else 0
                    )
                    rgb_previous = rgb
                else:
                    green = rip_get_signed(bits) if bits.bit() > 0 else 0
                    blue_increment = 0
                    if bits.bit() > 0:
                        negative = bits.bit() > 0
                        blue_increment = rip_quant(q, rip_get_int(bits))
                        if negative:
                            blue_increment = -blue_increment
                    red_increment = 0
                    if bits.bit() > 0:
                        negative = bits.bit() > 0
                        red_increment = rip_quant(q, rip_get_int(bits))
                        if negative:
                            red_increment = -red_increment

                    green_predict = green >> 1 if is_bgr676 else green
                    if pred_flag:
                        base = -((rgb_previous >> b_shift) & (0xFF >> b_shift))
                        if green_predict >= base:
                            high = (0xFF >> b_shift) + base
                            base = high
                            if green_predict <= high:
                                base = green_predict
                        blue = base + blue_increment

                        base = -((rgb_previous >> r_shift) & (0xFF0000 >> r_shift))
                        if green_predict >= base:
                            high = (0xFF0000 >> r_shift) + base
                            base = high
                            if green_predict <= high:
                                base = green_predict
                        red = base + red_increment
                    else:
                        blue = green_predict + blue_increment
                        red = green_predict + red_increment

                    rgb_previous = (
                        rgb_previous
                        + (blue << b_shift)
                        + (red << r_shift)
                        + (green << g_shift)
                    ) & 0xFFFFFFFF
                    rgb = rgb_previous

                pixel = (
                    (rgb + baseline_native) & 0xFFFFFFFF
                    if rgb != 0
                    else 0x80000000
                )
                pack_bgra(output, destination, pixel)
                destination += 4
                count -= 1

            if x >= width:
                break

            count = rip_get_int(bits)
            x += count
            if x > width:
                raise ValueError(
                    f"legacy RIP007 repeat run exceeds row at y={y}: {x}>{width}"
                )
            while count > 0:
                pixel = (
                    (rgb + baseline_native) & 0xFFFFFFFF
                    if rgb != 0
                    else 0x80000000
                )
                pack_bgra(output, destination, pixel)
                destination += 4
                count -= 1

    if bits.index != len(payload) or bits.cached != 0:
        raise ValueError(
            "legacy RIP007 did not consume payload exactly: "
            f"bytes={bits.index}/{len(payload)}, cached_bits={bits.cached}"
        )
    return output


def legacy_bgra_to_rgba(
    bgra: bytes | bytearray, *, force_opaque: bool = True
) -> bytearray:
    """Convert native packed BGRA to PNG RGBA without heuristic keying.

    The kind-2 branch is exposed by the engine/GARbro as Bgr32: ``0x80`` in
    the high byte is native full opacity, not PNG alpha 128.  Canonical display
    output is therefore opaque.  ``force_opaque=False`` is retained for
    low-level state diagnostics only.
    """

    if len(bgra) % 4:
        raise ValueError("legacy BGRA buffer length is not divisible by four")
    rgba = bytearray(len(bgra))
    for index in range(0, len(bgra), 4):
        blue, green, red, alpha = bgra[index : index + 4]
        rgba[index : index + 4] = bytes(
            (red, green, blue, 0xFF if force_opaque else alpha)
        )
    return rgba
