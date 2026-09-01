#!/usr/bin/env python3
"""Deterministic AGES/AFHook-compatible encoder for standard Cr6Ti records.

This module is intentionally independent from the v1 image-record builder.
It implements the byte/bit grammar documented by the AFHook C++ decoder,
AFEditor C# encoder/decoder, and alterdec C++ decoder, including the details
that matter for generated streams:

* transparent kind-3 pixels clear the previous-row RGB state;
* above-row copy is retained as a legal compression opcode;
* kind-3 shared and residual RGB deltas are added before one final clamp;
* kind-2 predictor division follows C/C# truncation toward zero;
* payloads and records are emitted deterministically.

The encoder preserves every template header byte except the four-byte payload
length at 0x20..0x23.  It never pads a record to an outer/container extent;
that is the responsibility of the native-scatter or parent-bundle writer.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

HEADER_SIZE = 0x2C
TRAILER = b"\0\0"


class Cr6TiEncodeError(ValueError):
    """Raised when a template or candidate cannot be represented safely."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise Cr6TiEncodeError(message)


def _clamp8(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else value


def _clamp_signed(value: int) -> int:
    return -128 if value < -128 else 127 if value > 127 else value


def trunc_toward_zero(value: int, divisor: int = 2) -> int:
    """Match signed integer division in C and C# (not Python ``//``)."""

    _require(divisor > 0, "divisor must be positive")
    return value // divisor if value >= 0 else -((-value) // divisor)


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

    @property
    def record_extent(self) -> int:
        return HEADER_SIZE + self.payload_length + len(TRAILER)


def parse_template(template: bytes) -> Cr6TiHeader:
    """Parse a complete record or a 0x2C-byte template header."""

    _require(len(template) >= HEADER_SIZE, "Cr6Ti template is truncated")
    _require(template[:3] == b"\x00\x04\x45", "Cr6Ti magic mismatch")
    width = int.from_bytes(template[0x06:0x08], "little")
    height = int.from_bytes(template[0x08:0x0A], "little")
    x_offset = int.from_bytes(template[0x0A:0x0C], "little", signed=True)
    y_offset = int.from_bytes(template[0x0C:0x0E], "little", signed=True)
    draw_width = int.from_bytes(template[0x0E:0x10], "little") or width
    draw_height = int.from_bytes(template[0x10:0x12], "little") or height
    header = Cr6TiHeader(
        width=width,
        height=height,
        x_offset=x_offset,
        y_offset=y_offset,
        draw_width=draw_width,
        draw_height=draw_height,
        kind=template[0x12],
        depth=template[0x13],
        flags=template[0x16],
        payload_length=int.from_bytes(template[0x20:0x24], "little"),
    )
    _require(width > 0 and height > 0, "invalid Cr6Ti canvas")
    _require(header.kind in (2, 3), f"unsupported Cr6Ti kind {header.kind}")
    _require(
        0 <= x_offset <= width - draw_width
        and 0 <= y_offset <= height - draw_height,
        "Cr6Ti draw rectangle is outside the canvas",
    )
    if len(template) > HEADER_SIZE:
        _require(
            len(template) == header.record_extent,
            "complete Cr6Ti template extent does not match its payload length",
        )
        _require(template[-2:] == TRAILER, "Cr6Ti template trailer is not 0000")
    return header


class LsbBitWriter:
    """LSB-first writer for the R6Ti signed and unsigned universal codes."""

    __slots__ = ("_bytes", "_cache", "_used", "bit_count")

    def __init__(self) -> None:
        self._bytes = bytearray()
        self._cache = 0
        self._used = 0
        self.bit_count = 0

    def write_bits(self, value: int, count: int) -> None:
        _require(count >= 0, "negative bit count")
        _require(value >= 0 and value >> count == 0, "bit field does not fit")
        self._cache |= value << self._used
        self._used += count
        self.bit_count += count
        while self._used >= 8:
            self._bytes.append(self._cache & 0xFF)
            self._cache >>= 8
            self._used -= 8

    def bit(self, value: bool | int) -> None:
        self.write_bits(int(bool(value)), 1)

    def signed(self, value: int) -> None:
        code, count = signed_code(value)
        self.write_bits(code, count)

    def unsigned(self, value: int) -> None:
        code, count = unsigned_code(value)
        self.write_bits(code, count)

    def finish(self) -> bytes:
        if self._used:
            self._bytes.append(self._cache & 0xFF)
            self._cache = 0
            self._used = 0
        # Official standard Cr6Ti payloads are word aligned.  The extra byte is
        # zero and therefore also valid bitstream padding.
        if len(self._bytes) & 1:
            self._bytes.append(0)
        return bytes(self._bytes)


def signed_code(value: int) -> tuple[int, int]:
    _require(-127 <= value <= 127, f"signed R6Ti value out of range: {value}")
    if value == 0:
        return 0, 1
    magnitude = abs(value)
    bits: list[int] = [1, int(value < 0)]
    for digit in bin(magnitude)[3:]:
        bits.extend((1, int(digit == "1")))
    if magnitude.bit_length() < 7:
        bits.append(0)
    return sum(bit << index for index, bit in enumerate(bits)), len(bits)


def unsigned_code(value: int) -> tuple[int, int]:
    _require(value >= 0, "unsigned R6Ti value is negative")
    if value == 0:
        return 0, 1
    bits: list[int] = [1]
    tail = bin(value + 1)[3:]
    for index, digit in enumerate(tail):
        bits.extend((int(digit == "1"), int(index != len(tail) - 1)))
    return sum(bit << index for index, bit in enumerate(bits)), len(bits)


SIGNED_CODE_LENGTH = {value: signed_code(value)[1] for value in range(-127, 128)}


def alpha_code(alpha: int) -> int:
    """Quantize 0..255 to the decoder's 0..32 alpha code domain."""

    _require(0 <= alpha <= 255, "alpha outside byte range")
    return max(0, min(32, (alpha * 32 + 127) // 255))


def alpha_value(code: int) -> int:
    _require(0 <= code <= 32, "alpha code outside 0..32")
    return 255 if code == 32 else code * 8


def _candidate_values(desired: float, *extra: int) -> tuple[int, ...]:
    floor = int(desired // 1)
    values = {-127, 0, 127, floor, floor + 1, *extra}
    for seed in tuple(values):
        values.update(range(seed - 3, seed + 4))
    return tuple(sorted(value for value in values if -127 <= value <= 127))


@lru_cache(maxsize=524_288)
def _residual_solution(
    *, current: int, shared: int, target: int, kind: int
) -> tuple[int, int, int]:
    """Return residual code, decoded value, and absolute error."""

    if kind == 2:
        base = _clamp8(current + shared * 2)
    else:
        # AFHook/AGES kind-3 semantics: no intermediate channel clamp.
        base = current + shared * 2
    # Decoding is monotone in ``raw``.  Therefore the error minimum is at one
    # of floor/ceil(desired), while 0 and the two code endpoints cover the
    # shortest-code tie inside a clamp plateau.  This five-value set is exactly
    # equivalent to the older +/-3 neighbourhood enumeration over every legal
    # kind-2 base and every reachable even kind-3 base (exhaustively tested).
    floor = (target - base) // 2
    raw_values = {
        -127,
        0,
        127,
        max(-127, min(127, floor)),
        max(-127, min(127, floor + 1)),
    }
    candidates: list[tuple[int, int, int, int]] = []
    for raw in raw_values:
        decoded = _clamp8(base + raw * 2)
        if kind == 3:
            decoded &= 0xFE
        candidates.append(
            (abs(decoded - target), SIGNED_CODE_LENGTH[raw], abs(raw), raw)
        )
    error, _, _, raw = min(candidates)
    decoded = _clamp8(base + raw * 2)
    if kind == 3:
        decoded &= 0xFE
    return raw, decoded, error


@lru_cache(maxsize=262_144)
def solve_delta(
    kind: int,
    current_r: int,
    current_g: int,
    current_b: int,
    previous_dg: int,
    target_r: int,
    target_g: int,
    target_b: int,
) -> tuple[int, int, int, int, int, int, int]:
    """Find a compact native delta tuple for one *native-order* RGB pixel.

    ``r/g/b`` here are the decoder's native variables.  The visible RGBA byte
    order is ``native_b, native_g, native_r, alpha``.
    """

    _require(kind in (2, 3), "delta solver kind must be 2 or 3")
    prediction = _clamp8(current_g + previous_dg * 2) - current_g
    if kind == 3:
        if prediction < -128:
            prediction += 256
        if prediction > 127:
            prediction -= 256
    prediction_half = trunc_toward_zero(prediction)

    desired = (target_g - current_g) / 2.0 - prediction_half
    raw_candidates: Iterable[int] = _candidate_values(
        desired,
        -prediction_half,
        -128 - prediction_half,
        127 - prediction_half,
    )
    choices: list[
        tuple[
            int,
            int,
            int,
            int,
            int,
            int,
            int,
            int,
            int,
            int,
        ]
    ] = []
    for raw_g in raw_candidates:
        dg = _clamp_signed(raw_g + prediction_half)
        decoded_g = _clamp8(current_g + dg * 2)
        if kind == 3:
            decoded_g &= 0xFE
        raw_r, decoded_r, error_r = _residual_solution(
            current=current_r, shared=dg, target=target_r, kind=kind
        )
        raw_b, decoded_b, error_b = _residual_solution(
            current=current_b, shared=dg, target=target_b, kind=kind
        )
        choices.append(
            (
                abs(decoded_g - target_g) + error_r + error_b,
                SIGNED_CODE_LENGTH[raw_g]
                + SIGNED_CODE_LENGTH[raw_r]
                + SIGNED_CODE_LENGTH[raw_b],
                abs(raw_g) + abs(raw_r) + abs(raw_b),
                raw_g,
                raw_r,
                raw_b,
                decoded_r,
                decoded_g,
                decoded_b,
                dg,
            )
        )
    (
        _error,
        _bits,
        _magnitude,
        raw_g,
        raw_r,
        raw_b,
        decoded_r,
        decoded_g,
        decoded_b,
        dg,
    ) = min(choices)
    return raw_g, raw_r, raw_b, decoded_r, decoded_g, decoded_b, dg


def _quantized_native(red: int, green: int, blue: int, kind: int) -> tuple[int, int, int]:
    # Starting from zero and using doubled signed deltas, even channels are
    # exactly representable in both kinds.  Kind 3 mandates the even mask;
    # using the same deterministic quantizer for kind 2 bounds raw error by 1.
    del kind
    return blue & 0xFE, green & 0xFE, red & 0xFE


def _literal_repeat_segments(
    values: Sequence[tuple[int, int, int]],
) -> list[tuple[str, int, int]]:
    """Plan alternating literal/repeat runs over visible RGB values.

    A repeat run consumes the tail of a maximal equal-RGB run; its first pixel
    remains in the preceding literal run and seeds the decoder's current RGB.
    This is the AFEditor/official grammar, with transparent positions omitted
    because the decoder does not decrement its frame counter for them.
    """

    if not values:
        return []
    result: list[tuple[str, int, int]] = []
    literal_start = 0
    second = 1
    size = len(values)
    while second < size:
        if values[second] != values[second - 1]:
            second += 1
            continue
        if literal_start < second:
            result.append(("literal", literal_start, second))
        end = second + 1
        while end < size and values[end] == values[second - 1]:
            end += 1
        result.append(("repeat", second, end))
        literal_start = end
        second = end + 1
    if literal_start < size:
        result.append(("literal", literal_start, size))
    _require(result and result[0][0] == "literal", "frame plan must start literal")
    for index, segment in enumerate(result):
        _require(segment[1] < segment[2], "empty Cr6Ti frame segment")
        _require(
            segment[0] == ("literal" if index % 2 == 0 else "repeat"),
            "Cr6Ti frame modes do not alternate",
        )
    return result


def _emit_literal_operation(writer: LsbBitWriter, operation: tuple[Any, ...]) -> None:
    if operation[0] == "copy":
        writer.bit(True)
        return
    _require(operation[0] == "delta", "unknown literal operation")
    _tag, raw_g, raw_r, raw_b = operation
    writer.bit(False)
    writer.signed(raw_g)
    writer.signed(raw_r)
    writer.signed(raw_b)


def _plan_frame_row(
    *,
    kind: int,
    desired: Sequence[tuple[int, int, int]],
    positions: Sequence[int],
    above: Sequence[tuple[int, int, int]],
    allow_above_copy: bool,
    allow_repeat: bool,
) -> tuple[list[dict[str, Any]], list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    """Plan one row while tracking the encoder's actually reachable RGB.

    A native shared delta can make an abrupt multi-channel target impossible
    to reproduce exactly even after even-channel quantization.  Planning from
    the *decoded* state prevents an impossible desired pixel from poisoning a
    later repeat declaration.  The independent readback audit remains the
    authority for the resulting bytes.
    """

    _require(len(desired) == len(positions), "visible values/positions differ")
    new_prior = [(0, 0, 0)] * len(above)
    decoded: list[tuple[int, int, int]] = []
    segments: list[dict[str, Any]] = []
    current = (0, 0, 0)
    derivative_g = 0
    index = 0
    while index < len(desired):
        literal_start = index
        operations: list[tuple[Any, ...]] = []
        literal_values: list[tuple[int, int, int]] = []
        while index < len(desired):
            x = positions[index]
            target = desired[index]
            if allow_above_copy and above[x] == target:
                operation: tuple[Any, ...] = ("copy",)
                current = target
                derivative_g = 0
            else:
                fields = solve_delta(kind, *current, derivative_g, *target)
                raw_g, raw_r, raw_b, decoded_r, decoded_g, decoded_b, derivative_g = fields
                operation = ("delta", raw_g, raw_r, raw_b)
                current = (decoded_r, decoded_g, decoded_b)
            operations.append(operation)
            literal_values.append(current)
            decoded.append(current)
            new_prior[x] = current
            index += 1

            # The decoder can repeat only its *actual* current RGB.  Consume
            # the maximal following run that already requests that value.
            if allow_repeat and index < len(desired) and desired[index] == current:
                break

        segments.append(
            {
                "mode": "literal",
                "start": literal_start,
                "end": index,
                "operations": operations,
                "decoded": literal_values,
            }
        )
        if index >= len(desired):
            break
        repeat_start = index
        repeat_values: list[tuple[int, int, int]] = []
        while index < len(desired) and desired[index] == current:
            x = positions[index]
            repeat_values.append(current)
            decoded.append(current)
            new_prior[x] = current
            index += 1
        segments.append(
            {
                "mode": "repeat",
                "start": repeat_start,
                "end": index,
                "operations": [],
                "decoded": repeat_values,
            }
        )
        derivative_g = 0

    for number, segment in enumerate(segments):
        _require(segment["start"] < segment["end"], "empty frame segment")
        _require(
            segment["mode"] == ("literal" if number % 2 == 0 else "repeat"),
            "frame segments do not alternate",
        )
    _require(len(decoded) == len(desired), "frame plan did not decode every value")
    return segments, new_prior, decoded


def _candidate_rows(
    header: Cr6TiHeader, rgba: bytes
) -> tuple[bytes, list[list[tuple[int, int, int, int]]]]:
    _require(
        len(rgba) == header.width * header.height * 4,
        "candidate RGBA length does not match template canvas",
    )
    canvas = bytearray(header.width * header.height * 4)
    rows: list[list[tuple[int, int, int, int]]] = []
    for local_y in range(header.draw_height):
        y = header.y_offset + local_y
        row: list[tuple[int, int, int, int]] = []
        for local_x in range(header.draw_width):
            x = header.x_offset + local_x
            position = (y * header.width + x) * 4
            red, green, blue, alpha = rgba[position : position + 4]
            native_r, native_g, native_b = _quantized_native(
                red, green, blue, header.kind
            )
            if header.kind == 2:
                _require(alpha == 255, f"kind2 candidate alpha is {alpha} at {x},{y}")
                decoded_alpha = 255
            else:
                decoded_alpha = alpha_value(alpha_code(alpha))
                if decoded_alpha == 0:
                    native_r = native_g = native_b = 0
            canvas[position : position + 4] = bytes(
                (native_b, native_g, native_r, decoded_alpha)
            )
            row.append((native_r, native_g, native_b, decoded_alpha))
        rows.append(row)
    return bytes(canvas), rows


def _canvas_from_rows(
    header: Cr6TiHeader,
    rows: Sequence[Sequence[tuple[int, int, int, int]]],
) -> bytes:
    _require(len(rows) == header.draw_height, "decoded row count mismatch")
    canvas = bytearray(header.width * header.height * 4)
    for local_y, row in enumerate(rows):
        _require(len(row) == header.draw_width, "decoded row width mismatch")
        y = header.y_offset + local_y
        for local_x, (native_r, native_g, native_b, alpha) in enumerate(row):
            x = header.x_offset + local_x
            at = (y * header.width + x) * 4
            canvas[at : at + 4] = bytes((native_b, native_g, native_r, alpha))
    return bytes(canvas)


def _encode_kind2(
    header: Cr6TiHeader,
    rows: Sequence[Sequence[tuple[int, int, int, int]]],
    *,
    allow_above_copy: bool,
    allow_repeat: bool,
) -> tuple[bytes, dict[str, Any], list[list[tuple[int, int, int, int]]]]:
    writer = LsbBitWriter()
    prior = [(0, 0, 0)] * header.draw_width
    counts: Counter[str] = Counter()
    decoded_rows: list[list[tuple[int, int, int, int]]] = []
    for row in rows:
        values = [(r, g, b) for r, g, b, _a in row]
        positions = list(range(header.draw_width))
        segments, prior, decoded = _plan_frame_row(
            kind=2,
            desired=values,
            positions=positions,
            above=prior,
            allow_above_copy=allow_above_copy,
            allow_repeat=allow_repeat,
        )
        for segment in segments:
            mode = segment["mode"]
            writer.unsigned(segment["end"] - segment["start"] - 1)
            counts[f"{mode}_run_declarations"] += 1
            if mode == "repeat":
                counts["repeat_pixels"] += segment["end"] - segment["start"]
                continue
            for operation in segment["operations"]:
                _emit_literal_operation(writer, operation)
                counts[
                    "above_row_copy_pixels" if operation[0] == "copy" else "delta_pixels"
                ] += 1
        decoded_rows.append([(r, g, b, 255) for r, g, b in decoded])
    return writer.finish(), {
        "strategy": "alternating literal/repeat frames plus legal above-row copy",
        "encoded_bits": writer.bit_count,
        **dict(counts),
    }, decoded_rows


def _encode_kind3(
    header: Cr6TiHeader,
    rows: Sequence[Sequence[tuple[int, int, int, int]]],
    *,
    allow_above_copy: bool,
    allow_repeat: bool,
) -> tuple[bytes, dict[str, Any], list[list[tuple[int, int, int, int]]]]:
    writer = LsbBitWriter()
    prior = [(0, 0, 0)] * header.draw_width
    counts: Counter[str] = Counter()
    decoded_rows: list[list[tuple[int, int, int, int]]] = []
    for row in rows:
        visible_positions = [index for index, pixel in enumerate(row) if pixel[3] != 0]
        visible_values = [tuple(row[index][:3]) for index in visible_positions]
        segments, prior, decoded_visible = _plan_frame_row(
            kind=3,
            desired=visible_values,
            positions=visible_positions,
            above=prior,
            allow_above_copy=allow_above_copy,
            allow_repeat=allow_repeat,
        )
        segment_by_visible = {segment["start"]: segment for segment in segments}
        operation_by_visible: dict[int, tuple[Any, ...]] = {}
        for segment in segments:
            if segment["mode"] == "literal":
                for offset, operation in enumerate(segment["operations"]):
                    operation_by_visible[segment["start"] + offset] = operation

        decoded_row = [(0, 0, 0, pixel[3]) for pixel in row]
        for index, local_x in enumerate(visible_positions):
            r, g, b = decoded_visible[index]
            decoded_row[local_x] = (r, g, b, row[local_x][3])
        decoded_rows.append(decoded_row)

        alpha_state = 0
        local_x = 0
        visible_index = 0
        active_mode = "literal"
        active_remaining = 0
        while local_x < header.draw_width:
            code = 32 if row[local_x][3] == 255 else row[local_x][3] // 8
            if code in (0, 32):
                run = 1
                while run + local_x < header.draw_width:
                    next_alpha = row[local_x + run][3]
                    next_code = 32 if next_alpha == 255 else next_alpha // 8
                    if next_code != code:
                        break
                    run += 1
                writer.signed(code - alpha_state)
                writer.unsigned(run - 1)
                alpha_state = code
                counts["alpha_run_declarations"] += 1
            else:
                run = 1
                writer.signed(code - alpha_state)
                alpha_state = code
                counts["partial_alpha_declarations"] += 1

            if code == 0:
                for index in range(local_x, local_x + run):
                    # This is the state transition omitted by v1.  A later
                    # copy from above must observe black, not stale RGB.
                    prior[index] = (0, 0, 0)
                counts["transparent_pixels"] += run
                local_x += run
                continue

            for _ in range(run):
                if active_remaining == 0:
                    segment = segment_by_visible[visible_index]
                    active_mode = segment["mode"]
                    active_remaining = segment["end"] - segment["start"]
                    writer.unsigned(active_remaining - 1)
                    counts[f"{active_mode}_run_declarations"] += 1
                if active_mode == "repeat":
                    counts["repeat_pixels"] += 1
                else:
                    operation = operation_by_visible[visible_index]
                    _emit_literal_operation(writer, operation)
                    counts[
                        "above_row_copy_pixels"
                        if operation[0] == "copy"
                        else "delta_pixels"
                    ] += 1
                local_x += 1
                visible_index += 1
                active_remaining -= 1
        _require(visible_index == len(visible_positions), "visible frame plan underflow")
        _require(active_remaining == 0, "visible frame plan overflow")
    return writer.finish(), {
        "strategy": (
            "native alpha runs; alternating literal/repeat frames; legal above-row "
            "copy; transparent previous-row RGB clear; shared+residual single final clamp"
        ),
        "encoded_bits": writer.bit_count,
        **dict(counts),
    }, decoded_rows


def assemble_record(template: bytes, payload: bytes) -> bytes:
    parse_template(template)
    header = bytearray(template[:HEADER_SIZE])
    header[0x20:0x24] = len(payload).to_bytes(4, "little")
    return bytes(header) + payload + TRAILER


def encode_cr6ti(
    template: bytes,
    rgba: bytes,
    *,
    allow_above_copy: bool = True,
    allow_repeat: bool = True,
) -> tuple[bytes, bytes, dict[str, Any]]:
    """Encode one complete Cr6Ti record and return record, decoded RGBA, stats."""

    header = parse_template(template)
    _intended_rgba, rows = _candidate_rows(header, rgba)
    if header.kind == 2:
        payload, stats, decoded_rows = _encode_kind2(
            header,
            rows,
            allow_above_copy=allow_above_copy,
            allow_repeat=allow_repeat,
        )
    else:
        payload, stats, decoded_rows = _encode_kind3(
            header,
            rows,
            allow_above_copy=allow_above_copy,
            allow_repeat=allow_repeat,
        )
    expected_rgba = _canvas_from_rows(header, decoded_rows)
    record = assemble_record(template, payload)
    stats = {
        **stats,
        "codec": "Cr6Ti",
        "kind": header.kind,
        "header": asdict(header),
        "payload_bytes": len(payload),
        "record_bytes": len(record),
        "record_sha256": hashlib.sha256(record).hexdigest().upper(),
        "expected_rgba_sha256": hashlib.sha256(expected_rgba).hexdigest().upper(),
        "allow_above_copy": allow_above_copy,
        "allow_repeat": allow_repeat,
        "deterministic": True,
    }
    return record, expected_rgba, stats


def load_rgba(path: Path) -> tuple[int, int, bytes]:
    from PIL import Image

    with Image.open(path) as image:
        rgba = image.convert("RGBA")
        return rgba.width, rgba.height, rgba.tobytes()


def encode_png(
    template_path: Path,
    candidate_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    template = template_path.read_bytes()
    width, height, rgba = load_rgba(candidate_path)
    header = parse_template(template)
    _require((width, height) == (header.width, header.height), "PNG/template size mismatch")
    record, expected, stats = encode_cr6ti(template, rgba)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(record)
    return {
        **stats,
        "template": str(template_path.resolve()),
        "candidate": str(candidate_path.resolve()),
        "output": str(output_path.resolve()),
        "candidate_sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest().upper(),
        "expected_rgba_bytes": len(expected),
    }


__all__ = [
    "Cr6TiEncodeError",
    "Cr6TiHeader",
    "HEADER_SIZE",
    "TRAILER",
    "alpha_code",
    "alpha_value",
    "assemble_record",
    "encode_cr6ti",
    "encode_png",
    "load_rgba",
    "parse_template",
    "signed_code",
    "solve_delta",
    "trunc_toward_zero",
    "unsigned_code",
]
