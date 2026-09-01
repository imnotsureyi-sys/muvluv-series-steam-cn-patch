#!/usr/bin/env python3
"""Independent native-semantics Cr6Ti decoder used to audit encoder v2.

This file intentionally does not import the encoder, the v1 decoder, or the
v1 builder.  Its control flow follows the AFHook/alterdec decode state machine
directly so encoder regressions cannot validate themselves through shared
implementation helpers.
"""

from __future__ import annotations

from dataclasses import dataclass


HEADER_SIZE = 0x2C


class Cr6TiDecodeError(ValueError):
    pass


def _need(condition: bool, message: str) -> None:
    if not condition:
        raise Cr6TiDecodeError(message)


def _clip_byte(value: int) -> int:
    return 0 if value < 0 else 255 if value > 255 else value


def _clip_signed(value: int) -> int:
    return -128 if value < -128 else 127 if value > 127 else value


def _half_native(value: int) -> int:
    return value // 2 if value >= 0 else -((-value) // 2)


@dataclass(frozen=True)
class Header:
    width: int
    height: int
    left: int
    top: int
    rect_width: int
    rect_height: int
    kind: int
    payload_length: int


@dataclass(frozen=True)
class DecodeResult:
    header: Header
    rgba: bytes
    consumed_bits: int
    padding_bits: int


class Reader:
    __slots__ = ("source", "cursor")

    def __init__(self, source: bytes) -> None:
        self.source = source
        self.cursor = 0

    def one(self) -> int:
        _need(self.cursor < len(self.source) * 8, "Cr6Ti stream ended early")
        value = (self.source[self.cursor >> 3] >> (self.cursor & 7)) & 1
        self.cursor += 1
        return value

    def signed(self) -> int:
        if not self.one():
            return 0
        sign = -1 if self.one() else 1
        magnitude = 1
        for _ in range(6):
            if not self.one():
                return sign * magnitude
            magnitude = magnitude * 2 + self.one()
        return sign * magnitude

    def unsigned(self) -> int:
        if not self.one():
            return 0
        value = 1
        for _ in range(31):
            value = value * 2 + self.one()
            if not self.one():
                return value - 1
        raise Cr6TiDecodeError("unsigned code exceeds 31 continuation pairs")

    def finish(self) -> int:
        remaining = len(self.source) * 8 - self.cursor
        _need(remaining <= 15, f"excess Cr6Ti padding: {remaining} bits")
        while self.cursor < len(self.source) * 8:
            _need(self.one() == 0, "non-zero Cr6Ti padding bit")
        return remaining


def _header(record: bytes) -> Header:
    _need(len(record) >= HEADER_SIZE + 2, "record is truncated")
    _need(record[:3] == b"\x00\x04\x45", "magic mismatch")
    width = int.from_bytes(record[6:8], "little")
    height = int.from_bytes(record[8:10], "little")
    left = int.from_bytes(record[10:12], "little", signed=True)
    top = int.from_bytes(record[12:14], "little", signed=True)
    rect_width = int.from_bytes(record[14:16], "little") or width
    rect_height = int.from_bytes(record[16:18], "little") or height
    payload_length = int.from_bytes(record[32:36], "little")
    result = Header(
        width=width,
        height=height,
        left=left,
        top=top,
        rect_width=rect_width,
        rect_height=rect_height,
        kind=record[18],
        payload_length=payload_length,
    )
    _need(result.kind in (2, 3), f"unsupported kind {result.kind}")
    _need(width > 0 and height > 0, "invalid canvas")
    _need(
        left >= 0
        and top >= 0
        and left + rect_width <= width
        and top + rect_height <= height,
        "draw rectangle is out of bounds",
    )
    _need(len(record) == HEADER_SIZE + payload_length + 2, "extent mismatch")
    _need(record[-2:] == b"\0\0", "trailer mismatch")
    return result


def _store(
    rect: bytearray,
    width: int,
    x: int,
    y: int,
    native_r: int,
    native_g: int,
    native_b: int,
    alpha: int,
) -> None:
    at = (y * width + x) * 4
    rect[at : at + 4] = bytes((native_b, native_g, native_r, alpha))


def _kind2(bits: Reader, width: int, height: int) -> bytes:
    rect = bytearray(width * height * 4)
    above_r = [0] * width
    above_g = [0] * width
    above_b = [0] * width
    for y in range(height):
        current_r = current_g = current_b = derivative_g = 0
        x = 0
        while x < width:
            literals = bits.unsigned() + 1
            _need(literals <= width - x, "kind2 literal run crosses row")
            for _ in range(literals):
                if bits.one():
                    current_r = above_r[x]
                    current_g = above_g[x]
                    current_b = above_b[x]
                    derivative_g = 0
                else:
                    prediction = _clip_byte(current_g + derivative_g * 2) - current_g
                    derivative_g = _clip_signed(bits.signed() + _half_native(prediction))
                    current_r = _clip_byte(current_r + derivative_g * 2)
                    current_g = _clip_byte(current_g + derivative_g * 2)
                    current_b = _clip_byte(current_b + derivative_g * 2)
                    current_r = _clip_byte(current_r + bits.signed() * 2)
                    current_b = _clip_byte(current_b + bits.signed() * 2)
                above_r[x] = current_r
                above_g[x] = current_g
                above_b[x] = current_b
                _store(rect, width, x, y, current_r, current_g, current_b, 255)
                x += 1
            if x == width:
                continue
            repeats = bits.unsigned() + 1
            _need(repeats <= width - x, "kind2 repeat run crosses row")
            for _ in range(repeats):
                above_r[x] = current_r
                above_g[x] = current_g
                above_b[x] = current_b
                _store(rect, width, x, y, current_r, current_g, current_b, 255)
                x += 1
            derivative_g = 0
    return bytes(rect)


def _kind3(bits: Reader, width: int, height: int) -> bytes:
    rect = bytearray(width * height * 4)
    above_r = [0] * width
    above_g = [0] * width
    above_b = [0] * width
    above_a = [0] * width
    for y in range(height):
        current_r = current_g = current_b = current_a = 0
        derivative_g = 0
        alpha_state = 0
        alpha_remaining = 0
        frame_remaining = 0
        repeat_mode = True
        x = 0
        while x < width:
            alpha_remaining -= 1
            if alpha_remaining < 0:
                alpha_state += bits.signed()
                _need(0 <= alpha_state <= 32, "alpha state outside 0..32")
                if alpha_state == 0:
                    count = bits.unsigned() + 1
                    _need(count <= width - x, "transparent run crosses row")
                    for _ in range(count):
                        # This is explicitly present in AFHook, AFEditor, and
                        # alterdec.  It is not optional hidden-RGB behavior.
                        above_r[x] = above_g[x] = above_b[x] = above_a[x] = 0
                        _store(rect, width, x, y, 0, 0, 0, 0)
                        x += 1
                    continue
                if alpha_state == 32:
                    alpha_remaining = bits.unsigned()
                current_a = 255 if alpha_state == 32 else alpha_state * 8

            frame_remaining -= 1
            if frame_remaining < 0:
                repeat_mode = not repeat_mode
                frame_remaining = bits.unsigned()
                derivative_g = 0

            if repeat_mode:
                if alpha_remaining < frame_remaining:
                    above_r[x] = current_r
                    above_g[x] = current_g
                    above_b[x] = current_b
                    above_a[x] = current_a
                    _store(
                        rect,
                        width,
                        x,
                        y,
                        current_r,
                        current_g,
                        current_b,
                        current_a,
                    )
                    x += 1
                else:
                    if frame_remaining > 0:
                        alpha_remaining -= frame_remaining
                    count = frame_remaining + 1
                    _need(count <= width - x, "repeat frame crosses row")
                    for _ in range(count):
                        above_r[x] = current_r
                        above_g[x] = current_g
                        above_b[x] = current_b
                        above_a[x] = current_a
                        _store(
                            rect,
                            width,
                            x,
                            y,
                            current_r,
                            current_g,
                            current_b,
                            current_a,
                        )
                        x += 1
                    frame_remaining = 0
                continue

            if bits.one():
                current_r = above_r[x]
                current_g = above_g[x]
                current_b = above_b[x]
                derivative_g = 0
            else:
                prediction = _clip_byte(current_g + derivative_g * 2) - current_g
                if prediction < -128:
                    prediction += 256
                if prediction > 127:
                    prediction -= 256
                derivative_g = _clip_signed(bits.signed() + _half_native(prediction))
                # AFHook semantics: shared and residual terms are summed before
                # the one final R/B clamp.
                current_r = _clip_byte(
                    current_r + derivative_g * 2 + bits.signed() * 2
                ) & 0xFE
                current_g = _clip_byte(current_g + derivative_g * 2) & 0xFE
                current_b = _clip_byte(
                    current_b + derivative_g * 2 + bits.signed() * 2
                ) & 0xFE
            above_r[x] = current_r
            above_g[x] = current_g
            above_b[x] = current_b
            above_a[x] = current_a
            _store(
                rect,
                width,
                x,
                y,
                current_r,
                current_g,
                current_b,
                current_a,
            )
            x += 1
    return bytes(rect)


def decode_record(record: bytes) -> DecodeResult:
    header = _header(record)
    bits = Reader(record[HEADER_SIZE : HEADER_SIZE + header.payload_length])
    if header.kind == 2:
        rect = _kind2(bits, header.rect_width, header.rect_height)
    else:
        rect = _kind3(bits, header.rect_width, header.rect_height)
    consumed = bits.cursor
    padding = bits.finish()
    canvas = bytearray(header.width * header.height * 4)
    row_bytes = header.rect_width * 4
    for local_y in range(header.rect_height):
        source = local_y * row_bytes
        target = (
            (header.top + local_y) * header.width + header.left
        ) * 4
        canvas[target : target + row_bytes] = rect[source : source + row_bytes]
    return DecodeResult(
        header=header,
        rgba=bytes(canvas),
        consumed_bits=consumed,
        padding_bits=padding,
    )


__all__ = ["Cr6TiDecodeError", "DecodeResult", "Header", "decode_record"]
