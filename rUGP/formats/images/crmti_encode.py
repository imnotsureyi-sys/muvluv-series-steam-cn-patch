#!/usr/bin/env python3
"""Deterministic encoder for AGES CRmti mip blobs and CRmt parents.

The encoder covers the same observed profiles as :mod:`crmti_decode`.  It
emits legal alternating literal/repeat frames, uses explicit predictor deltas
for each new colour, never relies on above-row copies, and preserves all CRmt
parent/child wrapper bytes except child blob lengths, active-row counts and
the capacity fields that must grow when the replacement expands row spans.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from functools import lru_cache
import hashlib
from typing import Sequence

from .crmti_capacity import capacity_for_ranges

from .crmti_decode import (
    CRMT_CHILD_WRAPPER,
    PrecisionProfile,
    parse_crmt,
    profile_for,
)


class CrmtiEncodeError(ValueError):
    """Raised when a template or candidate cannot be represented safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CrmtiEncodeError(message)


def _clamp8(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else value


def _clamp_signed(value: int) -> int:
    return -128 if value < -128 else 127 if value > 127 else value


class CrmtiBitWriter:
    """Logical-bit writer with the byte bit order selected by codec flags."""

    __slots__ = ("lsb_first", "_bytes", "_cache", "_used", "bit_count")

    def __init__(self, *, lsb_first: bool) -> None:
        self.lsb_first = lsb_first
        self._bytes = bytearray()
        self._cache = 0
        self._used = 0
        self.bit_count = 0

    def bit(self, value: bool | int) -> None:
        self._write_code(int(bool(value)), 1)

    def _write_code(self, code: int, count: int) -> None:
        _require(count >= 0 and code >= 0 and code >> count == 0, "invalid bit code")
        if self.lsb_first:
            self._cache |= code << self._used
            self._used += count
            self.bit_count += count
            while self._used >= 8:
                self._bytes.append(self._cache & 0xFF)
                self._cache >>= 8
                self._used -= 8
            return
        for logical_index in range(count):
            self._write_msb_bit((code >> logical_index) & 1)

    def _write_msb_bit(self, value: int) -> None:
        byte_index, bit_index = divmod(self.bit_count, 8)
        if byte_index == len(self._bytes):
            self._bytes.append(0)
        if value:
            self._bytes[byte_index] |= 1 << (7 - bit_index)
        self.bit_count += 1

    def signed(self, value: int) -> None:
        code, count = _short_signed_code(value, lsb_first=self.lsb_first)
        self._write_code(code, count)

    def signed_wide(self, value: int) -> None:
        code, count = _wide_signed_code(value)
        self._write_code(code, count)

    def unsigned(self, value: int) -> None:
        code, count = _unsigned_code(value)
        self._write_code(code, count)

    def finish(self) -> bytes:
        """Return zero-padded, 16-bit-aligned bytes."""

        if self.lsb_first and self._used:
            self._bytes.append(self._cache & 0xFF)
            self._cache = 0
            self._used = 0
        if len(self._bytes) & 1:
            self._bytes.append(0)
        return bytes(self._bytes)


@lru_cache(maxsize=512)
def _short_signed_code(value: int, *, lsb_first: bool) -> tuple[int, int]:
    _require(-127 <= value <= 127, f"short signed value out of range: {value}")
    if value == 0:
        return 0, 1
    magnitude = abs(value)
    bits = [1, int(value < 0)]
    for digit in bin(magnitude)[3:]:
        bits.extend((1, int(digit == "1")))
    # The LSB reader returns magnitude 127 at its six-pair ceiling without a
    # terminator; the MSB reader requires the normal zero terminator.
    if not lsb_first or magnitude.bit_length() < 7:
        bits.append(0)
    return sum(bit << index for index, bit in enumerate(bits)), len(bits)


@lru_cache(maxsize=4096)
def _wide_signed_code(value: int) -> tuple[int, int]:
    _require(
        -(2**31 - 1) <= value <= 2**31 - 1,
        f"wide signed value out of range: {value}",
    )
    if value == 0:
        return 0, 1
    magnitude = abs(value)
    bits = [1, int(value < 0)]
    for digit in bin(magnitude)[3:]:
        bits.extend((1, int(digit == "1")))
    bits.append(0)
    return sum(bit << index for index, bit in enumerate(bits)), len(bits)


@lru_cache(maxsize=65_536)
def _unsigned_code(value: int) -> tuple[int, int]:
    _require(0 <= value <= 2**31 - 2, f"unsigned value out of range: {value}")
    if value == 0:
        return 0, 1
    bits = [1]
    tail = bin(value + 1)[3:]
    for index, digit in enumerate(tail):
        bits.extend((int(digit == "1"), int(index != len(tail) - 1)))
    return sum(bit << index for index, bit in enumerate(bits)), len(bits)


def _short_signed_length(value: int, *, lsb_first: bool) -> int:
    return _short_signed_code(value, lsb_first=lsb_first)[1]


def _alpha_code(alpha: int) -> int:
    _require(0 <= alpha <= 255, "alpha channel is outside byte range")
    return max(0, min(32, (alpha * 32 + 127) // 255))


def _alpha_value(code: int) -> int:
    _require(0 <= code <= 32, "alpha code is outside 0..32")
    return 255 if code == 32 else code * 8


def _closest_to_zero(low: int, high: int) -> int:
    _require(low <= high, f"empty integer interval {low}..{high}")
    if low <= 0 <= high:
        return 0
    return low if low > 0 else high


def _raw_green_delta(
    *,
    step: int,
    mask: int,
    current: int,
    previous_dg: int,
    target: int,
) -> tuple[int, int]:
    prediction = _clamp8(current + previous_dg * step) - current
    if prediction < -128:
        prediction += 256
    if prediction > 127:
        prediction -= 256
    predicted_dg = prediction // step
    if target == 0:
        maximum_dg = -(current // step)
        low, high = -127, min(127, maximum_dg - predicted_dg)
        _require(low <= high, "green zero plateau is unreachable")
        raw = _closest_to_zero(low, high)
    elif target == mask:
        minimum_dg = (mask - current) // step
        low, high = max(-127, minimum_dg - predicted_dg), 127
        _require(low <= high, "green maximum plateau is unreachable")
        raw = _closest_to_zero(low, high)
    else:
        raw = (target - current) // step - predicted_dg
        _require(-127 <= raw <= 127, f"green target requires raw delta {raw}")
    dg = _clamp_signed(predicted_dg + raw)
    decoded = _clamp8(current + dg * step) & mask
    _require(decoded == target, f"green solver produced {decoded}, expected {target}")
    return raw, dg


def _raw_residual(*, step: int, mask: int, base: int, target: int) -> int:
    _require(0 <= base <= 255, "residual base is outside byte range")
    if base == 255:
        raw = 0 if target == mask else (target - mask) // step
    elif target == 0:
        raw = -(base // step)
    elif target == mask:
        raw = (mask - base) // step
    else:
        raw = (target - base) // step
    _require(-127 <= raw <= 127, f"residual code out of range: {raw}")
    decoded = _clamp8(base + raw * step) & mask
    _require(decoded == target, f"residual solver produced {decoded}, expected {target}")
    return raw


def solve_delta(
    *,
    profile: PrecisionProfile,
    current_r: int,
    current_g: int,
    current_b: int,
    previous_dg: int,
    target_r: int,
    target_g: int,
    target_b: int,
) -> tuple[int, int, int, int]:
    """Return exact native-order green/red/blue codes and the new shared delta."""

    step, mask = profile.color_step, profile.color_mask
    raw_g, dg = _raw_green_delta(
        step=step,
        mask=mask,
        current=current_g,
        previous_dg=previous_dg,
        target=target_g,
    )
    raw_r = _raw_residual(
        step=step,
        mask=mask,
        base=_clamp8(current_r + dg * step),
        target=target_r,
    )
    raw_b = _raw_residual(
        step=step,
        mask=mask,
        base=_clamp8(current_b + dg * step),
        target=target_b,
    )
    return raw_g, raw_r, raw_b, dg


def _candidate_rows(
    *, width: int, height: int, profile: PrecisionProfile, rgba: bytes
) -> tuple[bytes, list[list[tuple[int, int, int, int]]]]:
    _require(
        len(rgba) == width * height * 4,
        f"candidate RGBA has {len(rgba)} bytes, expected {width*height*4}",
    )
    expected = bytearray(len(rgba))
    rows: list[list[tuple[int, int, int, int]]] = []
    mask = profile.color_mask
    for y in range(height):
        row: list[tuple[int, int, int, int]] = []
        for x in range(width):
            offset = (y * width + x) * 4
            red, green, blue, alpha = rgba[offset : offset + 4]
            alpha = _alpha_value(_alpha_code(alpha))
            if alpha == 0:
                native_r = native_g = native_b = 0
                expected[offset : offset + 4] = b"\0\0\0\0"
            else:
                native_r, native_g, native_b = blue & mask, green & mask, red & mask
                expected[offset : offset + 4] = bytes(
                    (native_b, native_g, native_r, alpha)
                )
            row.append((native_r, native_g, native_b, alpha))
        rows.append(row)
    return bytes(expected), rows


def _decoded_candidate_segments(
    *, width: int, height: int, profile: PrecisionProfile, rgba: bytes
) -> tuple[
    bytes,
    list[list[tuple[int, int, int, int]] | None],
    list[tuple[int, int]],
    int,
]:
    """Validate already-decoded bytes without quantizing the transparent canvas."""

    _require(
        len(rgba) == width * height * 4,
        f"decoded RGBA has {len(rgba)} bytes, expected {width*height*4}",
    )
    alpha_plane = rgba[3::4]
    ranges: list[tuple[int, int]] = []
    segments: list[list[tuple[int, int, int, int]] | None] = []
    last_nonempty = -1
    mask = profile.color_mask
    representable_alpha = set(range(0, 249, 8)) | {255}
    for y in range(height):
        alpha_row = alpha_plane[y * width : (y + 1) * width]
        left_trimmed = alpha_row.lstrip(b"\0")
        if not left_trimmed:
            ranges.append((0, 0))
            segments.append(None)
            continue
        start = width - len(left_trimmed)
        end = len(alpha_row.rstrip(b"\0"))
        ranges.append((start, end))
        last_nonempty = y
        segment: list[tuple[int, int, int, int]] = []
        for x in range(start, end):
            offset = (y * width + x) * 4
            red, green, blue, alpha = rgba[offset : offset + 4]
            _require(alpha in representable_alpha, f"unrepresentable alpha at {x},{y}")
            if alpha == 0:
                _require(red == green == blue == 0, f"transparent RGB at {x},{y}")
                native_r = native_g = native_b = 0
            else:
                _require(
                    not ((red | green | blue) & ~mask),
                    f"RGB outside 0x{mask:02X} mask at {x},{y}",
                )
                native_r, native_g, native_b = blue, green, red
            segment.append((native_r, native_g, native_b, alpha))
        segments.append(segment)
    return rgba, segments, ranges, last_nonempty + 1


def _active_ranges(
    rows: Sequence[Sequence[tuple[int, int, int, int]]],
) -> tuple[list[tuple[int, int]], int]:
    ranges: list[tuple[int, int]] = []
    last_nonempty = -1
    for y, row in enumerate(rows):
        visible = [x for x, pixel in enumerate(row) if pixel[3] != 0]
        if visible:
            ranges.append((visible[0], visible[-1] + 1))
            last_nonempty = y
        else:
            ranges.append((0, 0))
    return ranges, last_nonempty + 1


def _literal_repeat_segments(
    values: Sequence[tuple[int, int, int]], *, allow_repeat: bool
) -> list[tuple[str, int, int]]:
    if not values:
        return []
    if not allow_repeat:
        return [("literal", 0, len(values))]
    result: list[tuple[str, int, int]] = []
    literal_start = 0
    second = 1
    while second < len(values):
        if values[second] != values[second - 1]:
            second += 1
            continue
        if literal_start < second:
            result.append(("literal", literal_start, second))
        end = second + 1
        while end < len(values) and values[end] == values[second - 1]:
            end += 1
        result.append(("repeat", second, end))
        literal_start = end
        second = end + 1
    if literal_start < len(values):
        result.append(("literal", literal_start, len(values)))
    _require(result[0][0] == "literal", "CRmti frame plan must begin literal")
    for index, segment in enumerate(result):
        expected = "literal" if index % 2 == 0 else "repeat"
        _require(segment[0] == expected and segment[1] < segment[2], "bad frame plan")
    return result


def encode_level(
    *,
    width: int,
    height: int,
    meta: int,
    rgba: bytes,
    assume_decoded_rgba: bool = False,
    allow_repeat: bool = True,
) -> tuple[bytes, int, bytes, dict[str, object]]:
    """Encode one CRmti blob and return blob, active rows, readback and stats."""

    _require(0 < width <= 0xFFFF and 0 < height <= 0xFFFF, "invalid CRmti size")
    profile = profile_for(meta)
    if assume_decoded_rgba:
        expected, rows, ranges, active_row_count = _decoded_candidate_segments(
            width=width, height=height, profile=profile, rgba=rgba
        )
    else:
        expected, full_rows = _candidate_rows(
            width=width, height=height, profile=profile, rgba=rgba
        )
        ranges, active_row_count = _active_ranges(full_rows)
        rows = list(full_rows)
    writer = CrmtiBitWriter(lsb_first=profile.bit_order == "lsb_first")
    counts: Counter[str] = Counter()

    previous_span = 0
    previous_start = 0
    for start, end in ranges[:active_row_count]:
        span = end - start
        writer.signed_wide(span - previous_span)
        previous_span = span
        counts["active_range_rows"] += 1
        if span == 0:
            previous_start = 0
            counts["zero_span_start_resets"] += 1
        else:
            writer.signed_wide(start - previous_start)
            previous_start = start
            counts["nonempty_active_rows"] += 1

    range_table_bits = writer.bit_count
    for y, (start, end) in enumerate(ranges[:active_row_count]):
        if start == end:
            continue
        row = rows[y]
        _require(row is not None, "non-empty active range has no row")
        row_offset = start if assume_decoded_rgba else 0
        visible_values = [
            tuple(row[x - row_offset][:3])
            for x in range(start, end)
            if row[x - row_offset][3] != 0
        ]
        visible_count = len(visible_values)
        _require(visible_count > 0, "non-empty active range has no visible pixels")
        segments = _literal_repeat_segments(visible_values, allow_repeat=allow_repeat)

        alpha_state = 0
        segment_index = 0
        frame_mode = "literal"
        frame_remaining = 0
        visible_index = 0
        current_r = current_g = current_b = 0
        previous_dg = 0
        x = start
        while x < end:
            alpha = row[x - row_offset][3]
            code = 32 if alpha == 255 else alpha // profile.alpha_step
            run = 1
            if code in (0, profile.alpha_max_code):
                while x + run < end:
                    next_alpha = row[x + run - row_offset][3]
                    next_code = 32 if next_alpha == 255 else next_alpha // profile.alpha_step
                    if next_code != code:
                        break
                    run += 1
            writer.signed(code - alpha_state)
            alpha_state = code
            if code in (0, profile.alpha_max_code):
                writer.unsigned(run - 1)
                key = "transparent_alpha_runs" if code == 0 else "opaque_alpha_runs"
                counts[key] += 1
            else:
                counts["partial_alpha_pixels"] += 1
            if code == 0:
                counts["transparent_pixels_inside_ranges"] += run
                x += run
                continue

            for _ in range(run):
                if frame_remaining == 0:
                    _require(segment_index < len(segments), "frame plan underflow")
                    frame_mode, frame_start, frame_end = segments[segment_index]
                    _require(frame_start == visible_index, "frame/visible position mismatch")
                    frame_remaining = frame_end - frame_start
                    writer.unsigned(frame_remaining - 1)
                    previous_dg = 0
                    counts[f"{frame_mode}_frame_declarations"] += 1
                    segment_index += 1
                native_r, native_g, native_b, _ = row[x - row_offset]
                if frame_mode == "repeat":
                    _require(
                        (native_r, native_g, native_b)
                        == (current_r, current_g, current_b),
                        "repeat target differs from current RGB",
                    )
                    counts["repeat_pixels"] += 1
                else:
                    raw_g, raw_r, raw_b, previous_dg = solve_delta(
                        profile=profile,
                        current_r=current_r,
                        current_g=current_g,
                        current_b=current_b,
                        previous_dg=previous_dg,
                        target_r=native_r,
                        target_g=native_g,
                        target_b=native_b,
                    )
                    writer.bit(0)  # explicit delta, never above-row copy
                    writer.signed(raw_g)
                    writer.signed(raw_r)
                    writer.signed(raw_b)
                    current_r, current_g, current_b = native_r, native_g, native_b
                    counts["delta_pixels"] += 1
                    counts["short_signed_bits"] += sum(
                        _short_signed_length(value, lsb_first=writer.lsb_first)
                        for value in (raw_g, raw_r, raw_b)
                    )
                visible_index += 1
                frame_remaining -= 1
                x += 1
        _require(visible_index == visible_count, "visible frame plan did not close")
        _require(frame_remaining == 0, "final CRmti frame did not close")
        _require(segment_index == len(segments), "unused CRmti frame segments")

    encoded_bits = writer.bit_count
    blob = writer.finish()
    stats: dict[str, object] = {
        "codec": "CRmti",
        "capacity": asdict(capacity_for_ranges(width, height, active_row_count, ranges)),
        "strategy": "alternating literal/repeat frames; explicit deltas; no above-row copy",
        "width": width,
        "height": height,
        "meta_hex": f"0x{meta:08X}",
        "profile": asdict(profile),
        "active_row_count": active_row_count,
        "range_table_bits": range_table_bits,
        "encoded_bits": encoded_bits,
        "blob_bytes": len(blob),
        "zero_alignment_bits": len(blob) * 8 - encoded_bits,
        "blob_sha256": hashlib.sha256(blob).hexdigest().upper(),
        "expected_rgba_sha256": hashlib.sha256(expected).hexdigest().upper(),
        "deterministic": True,
        "input_mode": (
            "trusted_decoded_rgba_verified_inside_active_ranges"
            if assume_decoded_rgba
            else "arbitrary_rgba_quantized_by_encoder"
        ),
        "uses_above_row_copy": False,
        "uses_repeat_frames": allow_repeat,
        **dict(counts),
    }
    return blob, active_row_count, expected, stats


def encode_crmt(
    template: bytes,
    rgba_levels: Sequence[bytes],
    *,
    assume_decoded_rgba: bool = False,
    allow_repeat: bool = True,
) -> tuple[bytes, list[bytes], dict[str, object]]:
    """Encode every CRmti child and preserve the CRmt parent framing."""

    levels, trailer = parse_crmt(template)
    _require(
        len(rgba_levels) == len(levels),
        f"received {len(rgba_levels)} RGBA levels for {len(levels)} children",
    )
    # The first wrapper offset is also the exact end of the variable-size CRmt
    # parent preamble (0x2e, 0x41, or 0x54 in the audited PF/PM layouts).
    parent_preamble_end = levels[0].wrapper_offset
    output = bytearray(template[:parent_preamble_end])
    expected_levels: list[bytes] = []
    level_stats: list[dict[str, object]] = []
    for level, rgba in zip(levels, rgba_levels, strict=True):
        blob, active_rows, expected, stats = encode_level(
            width=level.width,
            height=level.height,
            meta=level.meta,
            rgba=rgba,
            assume_decoded_rgba=assume_decoded_rgba,
            allow_repeat=allow_repeat,
        )
        child_header = bytearray(template[level.header_offset : level.blob_offset])
        child_header[8:12] = len(blob).to_bytes(4, "little")
        new_hint = max(level.decoded_size_hint, int(stats["capacity"]["required_hint"]))
        _require(new_hint <= 0x7FFFFFFF - 12*level.height - 16, "native capacity overflow")
        child_header[12:16] = new_hint.to_bytes(4, "little")
        child_header[16:18] = active_rows.to_bytes(2, "little")
        child_wrapper = template[level.wrapper_offset : level.header_offset]
        _require(
            len(child_wrapper) == len(CRMT_CHILD_WRAPPER),
            f"CRmti child {level.index} wrapper length changed",
        )
        output.extend(child_wrapper)
        output.extend(child_header)
        output.extend(blob)
        expected_levels.append(expected)
        level_stats.append(
            {
                "index": level.index,
                "source_blob_bytes": level.blob_length,
                "source_decoded_size_hint": level.decoded_size_hint,
                "replacement_decoded_size_hint": new_hint,
                "encoded_blob_bytes": len(blob),
                "blob_byte_delta": len(blob) - level.blob_length,
                **stats,
            }
        )
    output.extend(trailer)
    encoded = bytes(output)
    stats: dict[str, object] = {
        "codec": "CRmt/CRmti",
        "levels": level_stats,
        "level_count": len(levels),
        "source_record_bytes": len(template),
        "encoded_record_bytes": len(encoded),
        "record_byte_delta": len(encoded) - len(template),
        "parent_prefix_hex": template[:4].hex(" "),
        "child_table_offset": parent_preamble_end,
        "child_wrapper_hex": template[
            levels[0].wrapper_offset : levels[0].header_offset
        ].hex(" "),
        "trailer_bytes_preserved": len(trailer),
        "source_record_sha256": hashlib.sha256(template).hexdigest().upper(),
        "encoded_record_sha256": hashlib.sha256(encoded).hexdigest().upper(),
        "deterministic": True,
    }
    return encoded, expected_levels, stats


__all__ = [
    "CrmtiBitWriter",
    "CrmtiEncodeError",
    "encode_crmt",
    "encode_level",
    "solve_delta",
]
