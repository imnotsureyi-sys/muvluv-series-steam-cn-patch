from __future__ import annotations

import unittest

from rugp.formats.images.cr6ti_encode import (
    encode_cr6ti,
    trunc_toward_zero,
)
from rugp.formats.images.cr6ti_reference import decode_record


def template(width: int, height: int, kind: int) -> bytes:
    header = bytearray(0x2C)
    header[:3] = b"\x00\x04\x45"
    header[6:8] = width.to_bytes(2, "little")
    header[8:10] = height.to_bytes(2, "little")
    header[14:16] = width.to_bytes(2, "little")
    header[16:18] = height.to_bytes(2, "little")
    header[18] = kind
    header[19] = 3
    header[22] = 7
    return bytes(header) + b"\0\0"


def test_native_division_is_toward_zero() -> None:
    assert trunc_toward_zero(-3) == -1
    assert trunc_toward_zero(-2) == -1
    assert trunc_toward_zero(3) == 1


def test_kind2_roundtrip_is_deterministic_under_independent_decoder() -> None:
    width, height = 7, 4
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            # Adjacent repeats plus an above-row copy exercise both legal
            # compression modes.  Odd input values exercise quantization.
            red = (x // 2 * 37 + y * 9) & 0xFF
            green = (x // 2 * 19 + y * 13) & 0xFF
            blue = (x // 2 * 11 + y * 17) & 0xFF
            pixels.extend((red, green, blue, 255))
    first, expected, first_stats = encode_cr6ti(template(width, height, 2), bytes(pixels))
    second, expected_again, second_stats = encode_cr6ti(
        template(width, height, 2), bytes(pixels)
    )
    assert first == second
    assert expected == expected_again
    assert first_stats == second_stats
    assert decode_record(first).rgba == expected
    assert first_stats["repeat_pixels"] > 0


def test_kind3_transparent_pixel_clears_previous_row_before_copy() -> None:
    width, height = 3, 3
    rgba = bytearray(width * height * 4)

    def put(x: int, y: int, value: tuple[int, int, int, int]) -> None:
        start = (y * width + x) * 4
        rgba[start : start + 4] = bytes(value)

    # Row zero seeds non-zero previous-row RGB.
    put(0, 0, (100, 60, 20, 255))
    put(1, 0, (80, 40, 10, 255))
    # Row one is fully transparent and therefore must clear all three RGB
    # columns in the previous-row state.
    # Row two's visible black pixel can then legally use an above-row copy.
    put(0, 2, (0, 0, 0, 255))

    record, expected, stats = encode_cr6ti(template(width, height, 3), bytes(rgba))
    decoded = decode_record(record).rgba
    assert decoded == expected
    assert decoded[(2 * width) * 4 : (2 * width) * 4 + 4] == b"\0\0\0\xff"
    assert stats["above_row_copy_pixels"] >= 1
    assert stats["transparent_pixels"] >= width


def test_kind3_repeat_and_partial_alpha_roundtrip() -> None:
    width, height = 12, 3
    rgba = bytearray(width * height * 4)
    for y in range(height):
        for x in range(width):
            alpha = 0 if x < 2 else (255 if x > 4 else 40 + x * 24)
            color = (240, 100, 30, alpha) if x < 9 else (20, 180, 220, alpha)
            start = (y * width + x) * 4
            rgba[start : start + 4] = bytes(color)
    record, expected, stats = encode_cr6ti(template(width, height, 3), bytes(rgba))
    assert decode_record(record).rgba == expected
    assert stats["repeat_pixels"] > 0
    assert stats["partial_alpha_declarations"] > 0


class Cr6TiEncodeTests(unittest.TestCase):
    """Expose the original assertion-based cases to stdlib discovery."""

    def test_native_division(self) -> None:
        test_native_division_is_toward_zero()

    def test_kind2_roundtrip(self) -> None:
        test_kind2_roundtrip_is_deterministic_under_independent_decoder()

    def test_kind3_transparent_copy(self) -> None:
        test_kind3_transparent_pixel_clears_previous_row_before_copy()

    def test_kind3_partial_alpha(self) -> None:
        test_kind3_repeat_and_partial_alpha_roundtrip()
