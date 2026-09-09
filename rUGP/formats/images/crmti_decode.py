#!/usr/bin/env python3
"""Strict decoder for AGES CRmt containers and their CRmti mip children.

The implementation covers every profile observed in the frozen
Photonflowers/Photonmelodies census: equal 5-, 6-, or 7-bit RGB precision,
five-bit alpha plus the opaque sentinel, and both flag-selected byte bit
orders (0x0f LSB-first and 0x07 MSB-first).

CRmt is a parent object.  Each child begins with a four-byte wrapper and an
18-byte CRmti header, followed by a compressed blob.  The parent bytes before
the table and after the final child are deliberately exposed so an encoder can
preserve them exactly.
"""

from __future__ import annotations

from dataclasses import dataclass


CRMT_PREFIX = bytes.fromhex("80 04 02 05")
CRMT_PREFIX_DERIVED = bytes.fromhex("80 04 02 06")
CRMT_CHILD_WRAPPER = bytes.fromhex("0c 80 40 c0")
# The PF/PM whole-volume census found exactly these five parent layouts.  Keep
# the table closed rather than guessing at an arbitrary byte that merely looks
# like a child count; a future layout must first be audited and added here.
CRMT_LAYOUTS = {
    CRMT_PREFIX: (
        (0x2D, bytes.fromhex("0a 80 40 c0")),
        (0x40, CRMT_CHILD_WRAPPER),
        (0x53, bytes.fromhex("0e 80 40 c0")),
    ),
    CRMT_PREFIX_DERIVED: (
        (0x40, bytes.fromhex("0d 80 40 c0")),
        (0x53, bytes.fromhex("0f 80 40 c0")),
    ),
}
CRMT_CHILD_HEADER_SIZE = 18
MAX_LEVELS = 16
MAX_PIXELS = 16_777_216


@dataclass(frozen=True)
class PrecisionProfile:
    red_bits: int
    green_bits: int
    blue_bits: int
    alpha_bits: int
    codec_flags: int
    bit_order: str
    color_step: int
    color_mask: int
    alpha_step: int
    alpha_max_code: int


@dataclass(frozen=True)
class CrmtiLevel:
    index: int
    width: int
    height: int
    meta: int
    blob_length: int
    decoded_size_hint: int
    active_row_count: int
    wrapper_offset: int
    header_offset: int
    blob_offset: int
    blob_end: int
    blob: bytes


@dataclass(frozen=True)
class DecodeStats:
    active_rows: int
    active_pixels: int
    transparent_pixels: int
    repeated_pixels: int
    copied_from_above: int
    delta_pixels: int
    consumed_bits: int
    payload_bits: int
    zero_padding_bits: int


@dataclass(frozen=True)
class DecodeResult:
    level: CrmtiLevel
    rgba: bytes
    active_ranges: tuple[tuple[int, int], ...]
    stats: DecodeStats


class CrmtiBitReader:
    """Bounds-checked RioX logical-bit reader."""

    __slots__ = ("data", "lsb_first", "bit_position")

    def __init__(self, data: bytes, *, lsb_first: bool) -> None:
        self.data = data
        self.lsb_first = lsb_first
        self.bit_position = 0

    @property
    def remaining_bits(self) -> int:
        return len(self.data) * 8 - self.bit_position

    def bit(self) -> int:
        if self.bit_position >= len(self.data) * 8:
            raise ValueError(
                f"CRmti bitstream ended at bit {self.bit_position} "
                f"of {len(self.data) * 8}"
            )
        byte_index, bit_index = divmod(self.bit_position, 8)
        self.bit_position += 1
        if not self.lsb_first:
            bit_index = 7 - bit_index
        return (self.data[byte_index] >> bit_index) & 1

    def signed(self) -> int:
        if self.bit() == 0:
            return 0
        negative = bool(self.bit())
        value = 1
        # RioX's LSB-first short flavor returns after six continuation pairs.
        continuation_limit = 6 if self.lsb_first else 31
        for _ in range(continuation_limit):
            if self.bit() == 0:
                return -value if negative else value
            value = (value << 1) | self.bit()
        if self.lsb_first:
            return -value if negative else value
        raise ValueError("CRmti MSB-first signed code exceeds 31 continuation pairs")

    def unsigned(self) -> int:
        if self.bit() == 0:
            return 0
        value = 1
        for _ in range(31):
            value = (value << 1) | self.bit()
            if self.bit() == 0:
                return value - 1
        raise ValueError("CRmti unsigned code exceeds 31 continuation pairs")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _clamp8(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else value


def _put_rgba(
    output: bytearray,
    width: int,
    x: int,
    y: int,
    native_r: int,
    native_g: int,
    native_b: int,
    alpha: int,
) -> None:
    offset = (y * width + x) * 4
    # RioX predictor variables reach the renderer in native B,G,R order.
    output[offset : offset + 4] = bytes((native_b, native_g, native_r, alpha))


def profile_for(meta: int) -> PrecisionProfile:
    """Interpret the observed little-endian flags,R,G,B packed field."""

    codec_flags = meta & 0xFF
    red = (meta >> 8) & 0xFF
    green = (meta >> 16) & 0xFF
    blue = (meta >> 24) & 0xFF
    _require(
        red == green == blue and red in {5, 6, 7},
        f"unsupported CRmti RGB precision profile 0x{meta:08X}",
    )
    _require(
        codec_flags in {0x07, 0x0F},
        f"unsupported CRmti codec flags in profile 0x{meta:08X}",
    )
    step = 1 << (8 - red)
    return PrecisionProfile(
        red_bits=red,
        green_bits=green,
        blue_bits=blue,
        alpha_bits=5,
        codec_flags=codec_flags,
        bit_order="lsb_first" if codec_flags & 8 else "msb_first",
        color_step=step,
        color_mask=0xFF & ~(step - 1),
        alpha_step=8,
        alpha_max_code=32,
    )


def parse_crmt(record: bytes) -> tuple[list[CrmtiLevel], bytes]:
    """Parse one exact CRmt extent and return children plus parent trailer."""

    layouts = CRMT_LAYOUTS.get(record[:4])
    _require(layouts is not None, "CRmt prefix mismatch")
    matches: list[tuple[int, bytes]] = []
    for count_offset, wrapper in layouts:
        wrapper_offset = count_offset + 1
        if wrapper_offset + len(wrapper) > len(record):
            continue
        count = record[count_offset]
        if 1 <= count <= MAX_LEVELS and record[
            wrapper_offset : wrapper_offset + len(wrapper)
        ] == wrapper:
            matches.append((count_offset, wrapper))
    _require(matches, "CRmt record has no audited child-table layout")
    _require(len(matches) == 1, "CRmt record has an ambiguous child-table layout")
    count_offset, child_wrapper = matches[0]
    count = record[count_offset]
    cursor = count_offset + 1
    levels: list[CrmtiLevel] = []
    for index in range(count):
        wrapper_offset = cursor
        _require(
            cursor + len(child_wrapper) <= len(record),
            f"CRmti child {index} wrapper is truncated",
        )
        _require(
            record[cursor : cursor + 4] == child_wrapper,
            f"CRmti child {index} wrapper mismatch at 0x{cursor:X}",
        )
        header_offset = cursor + 4
        _require(
            header_offset + CRMT_CHILD_HEADER_SIZE <= len(record),
            f"CRmti child {index} header is truncated",
        )
        width = int.from_bytes(record[header_offset : header_offset + 2], "little")
        height = int.from_bytes(record[header_offset + 2 : header_offset + 4], "little")
        meta = int.from_bytes(record[header_offset + 4 : header_offset + 8], "little")
        blob_length = int.from_bytes(record[header_offset + 8 : header_offset + 12], "little")
        decoded_size_hint = int.from_bytes(
            record[header_offset + 12 : header_offset + 16], "little"
        )
        active_row_count = int.from_bytes(
            record[header_offset + 16 : header_offset + 18], "little"
        )
        blob_offset = header_offset + CRMT_CHILD_HEADER_SIZE
        blob_end = blob_offset + blob_length
        _require(width > 0 and height > 0, f"invalid CRmti size {width}x{height}")
        _require(width * height <= MAX_PIXELS, f"CRmti canvas exceeds {MAX_PIXELS} pixels")
        _require(active_row_count <= height, "CRmti active row count exceeds height")
        _require(blob_length > 0, f"CRmti child {index} has an empty blob")
        _require(blob_end <= len(record), f"CRmti child {index} blob is truncated")
        profile_for(meta)
        levels.append(
            CrmtiLevel(
                index=index,
                width=width,
                height=height,
                meta=meta,
                blob_length=blob_length,
                decoded_size_hint=decoded_size_hint,
                active_row_count=active_row_count,
                wrapper_offset=wrapper_offset,
                header_offset=header_offset,
                blob_offset=blob_offset,
                blob_end=blob_end,
                blob=record[blob_offset:blob_end],
            )
        )
        cursor = blob_end
    return levels, record[cursor:]


def _read_signed_wide(bits: CrmtiBitReader) -> int:
    if bits.bit() == 0:
        return 0
    negative = bool(bits.bit())
    value = 1
    for _ in range(31):
        if bits.bit() == 0:
            return -value if negative else value
        value = (value << 1) | bits.bit()
    raise ValueError("CRmti wide signed code exceeds 31 continuation pairs")


def read_active_ranges(
    bits: CrmtiBitReader,
    width: int,
    height: int,
    active_row_count: int,
) -> tuple[tuple[int, int], ...]:
    """Decode delta-coded row spans, including the native zero-span reset."""

    _require(active_row_count <= height, "CRmti active row count exceeds height")
    ranges: list[tuple[int, int]] = []
    span = 0
    start = 0
    for y in range(active_row_count):
        span += _read_signed_wide(bits)
        if span == 0:
            # Both RioX readers reset the accumulated start on an empty row.
            start = 0
            row = (0, 0)
        else:
            start += _read_signed_wide(bits)
            row = (start, start + span)
        _require(
            0 <= row[0] <= row[1] <= width,
            f"CRmti active range {row} is outside width {width} at row {y}",
        )
        ranges.append(row)
    ranges.extend([(0, 0)] * (height - active_row_count))
    return tuple(ranges)


def _alpha_value(code: int, profile: PrecisionProfile) -> int:
    return 255 if code == profile.alpha_max_code else code * profile.alpha_step


def decode_level(level: CrmtiLevel) -> DecodeResult:
    """Decode one child, rejecting malformed runs and non-zero tail bits."""

    profile = profile_for(level.meta)
    bits = CrmtiBitReader(level.blob, lsb_first=profile.bit_order == "lsb_first")
    ranges = read_active_ranges(
        bits, level.width, level.height, level.active_row_count
    )
    output = bytearray(level.width * level.height * 4)
    previous_r = [0] * level.width
    previous_g = [0] * level.width
    previous_b = [0] * level.width
    active_pixels = transparent_pixels = repeated_pixels = 0
    copied_from_above = delta_pixels = 0
    step = profile.color_step
    mask = profile.color_mask

    for y, (start, end) in enumerate(ranges):
        native_r = native_g = native_b = 0
        alpha_code = 0
        previous_dg = 0
        alpha_remaining = 0
        frame_remaining = 0
        frame_mode_repeat = True
        x = start
        active_pixels += end - start
        while x < end:
            alpha_remaining -= 1
            if alpha_remaining < 0:
                alpha_code += bits.signed()
                _require(
                    0 <= alpha_code <= profile.alpha_max_code,
                    f"CRmti alpha code {alpha_code} outside 0..{profile.alpha_max_code} "
                    f"at mip={level.index}, y={y}, x={x}",
                )
                if alpha_code == 0:
                    count = bits.unsigned() + 1
                    _require(
                        count <= end - x,
                        f"CRmti transparent run {count} exceeds row remainder "
                        f"{end-x} at mip={level.index}, y={y}, x={x}",
                    )
                    x += count
                    transparent_pixels += count
                    continue
                if alpha_code == profile.alpha_max_code:
                    alpha_remaining = bits.unsigned()

            frame_remaining -= 1
            if frame_remaining < 0:
                frame_mode_repeat = not frame_mode_repeat
                frame_remaining = bits.unsigned()
                previous_dg = 0

            if frame_mode_repeat:
                if alpha_remaining < frame_remaining:
                    _put_rgba(
                        output,
                        level.width,
                        x,
                        y,
                        native_r,
                        native_g,
                        native_b,
                        _alpha_value(alpha_code, profile),
                    )
                    previous_r[x], previous_g[x], previous_b[x] = (
                        native_r,
                        native_g,
                        native_b,
                    )
                    x += 1
                    repeated_pixels += 1
                else:
                    if frame_remaining > 0:
                        alpha_remaining -= frame_remaining
                    count = frame_remaining + 1
                    _require(
                        count <= end - x,
                        f"CRmti repeat frame {count} exceeds row remainder "
                        f"{end-x} at mip={level.index}, y={y}, x={x}",
                    )
                    alpha = _alpha_value(alpha_code, profile)
                    for _ in range(count):
                        _put_rgba(
                            output,
                            level.width,
                            x,
                            y,
                            native_r,
                            native_g,
                            native_b,
                            alpha,
                        )
                        previous_r[x], previous_g[x], previous_b[x] = (
                            native_r,
                            native_g,
                            native_b,
                        )
                        x += 1
                    repeated_pixels += count
                    frame_remaining = 0
            elif bits.bit():
                native_r, native_g, native_b = (
                    previous_r[x],
                    previous_g[x],
                    previous_b[x],
                )
                _put_rgba(
                    output,
                    level.width,
                    x,
                    y,
                    native_r,
                    native_g,
                    native_b,
                    _alpha_value(alpha_code, profile),
                )
                previous_r[x], previous_g[x], previous_b[x] = (
                    native_r,
                    native_g,
                    native_b,
                )
                x += 1
                previous_dg = 0
                copied_from_above += 1
            else:
                prediction = _clamp8(native_g + previous_dg * step) - native_g
                if prediction < -128:
                    prediction += 256
                if prediction > 127:
                    prediction -= 256
                previous_dg = max(
                    -128, min(127, prediction // step + bits.signed())
                )
                native_r = _clamp8(native_r + previous_dg * step)
                native_g = _clamp8(native_g + previous_dg * step)
                native_b = _clamp8(native_b + previous_dg * step)
                native_r = _clamp8(native_r + bits.signed() * step) & mask
                native_b = _clamp8(native_b + bits.signed() * step) & mask
                native_g &= mask
                _put_rgba(
                    output,
                    level.width,
                    x,
                    y,
                    native_r,
                    native_g,
                    native_b,
                    _alpha_value(alpha_code, profile),
                )
                previous_r[x], previous_g[x], previous_b[x] = (
                    native_r,
                    native_g,
                    native_b,
                )
                x += 1
                delta_pixels += 1

    for position in range(bits.bit_position, len(level.blob) * 8):
        bit_index = position & 7
        if not bits.lsb_first:
            bit_index = 7 - bit_index
        if (level.blob[position >> 3] >> bit_index) & 1:
            raise ValueError(
                f"CRmti non-zero padding at mip {level.index}, payload bit {position}"
            )
    stats = DecodeStats(
        active_rows=sum(end > start for start, end in ranges),
        active_pixels=active_pixels,
        transparent_pixels=transparent_pixels,
        repeated_pixels=repeated_pixels,
        copied_from_above=copied_from_above,
        delta_pixels=delta_pixels,
        consumed_bits=bits.bit_position,
        payload_bits=len(level.blob) * 8,
        zero_padding_bits=bits.remaining_bits,
    )
    return DecodeResult(level=level, rgba=bytes(output), active_ranges=ranges, stats=stats)


def decode_crmt(record: bytes) -> tuple[list[DecodeResult], bytes]:
    """Parse and decode every child in one exact CRmt record."""

    levels, trailer = parse_crmt(record)
    return [decode_level(level) for level in levels], trailer


__all__ = [
    "CRMT_CHILD_HEADER_SIZE",
    "CRMT_CHILD_WRAPPER",
    "CRMT_LAYOUTS",
    "CRMT_PREFIX",
    "CRMT_PREFIX_DERIVED",
    "CrmtiBitReader",
    "CrmtiLevel",
    "DecodeResult",
    "DecodeStats",
    "PrecisionProfile",
    "decode_crmt",
    "decode_level",
    "parse_crmt",
    "profile_for",
    "read_active_ranges",
]
