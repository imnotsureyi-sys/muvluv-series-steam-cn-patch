from __future__ import annotations

import unittest

from rUGP.formats.images.crip008_decode import (
    decode_crip008_kind2_native,
    decode_crip008_kind3_native,
    parse_crip008_header,
)
from rUGP.formats.images.crip008_kind2_encode import (
    decode_generated_payload as decode_kind2_subset,
    encode_native_pixels as encode_kind2,
)
from rUGP.formats.images.crip008_kind3_encode import (
    decode_generated_payload as decode_kind3_subset,
    encode_native_pixels as encode_kind3,
)


def header(
    *,
    kind: int,
    width: int,
    height: int,
    payload_length: int,
    x_offset: int = 0,
    y_offset: int = 0,
    draw_width: int | None = None,
    draw_height: int | None = None,
) -> bytes:
    data = bytearray(0x29)
    data[:3] = b"\x00\x04\x45"
    data[0x06:0x08] = width.to_bytes(2, "little")
    data[0x08:0x0A] = height.to_bytes(2, "little")
    data[0x0A:0x0C] = x_offset.to_bytes(2, "little", signed=True)
    data[0x0C:0x0E] = y_offset.to_bytes(2, "little", signed=True)
    data[0x0E:0x10] = (draw_width or width).to_bytes(2, "little")
    data[0x10:0x12] = (draw_height or height).to_bytes(2, "little")
    data[0x12] = kind
    data[0x13] = 3
    data[0x16] = 2  # red/blue prediction used by both scoped encoders
    data[0x17:0x1A] = b"\x08\x08\x08"
    data[0x1D:0x21] = payload_length.to_bytes(4, "little")
    return bytes(data)


class CRip008EncodeTests(unittest.TestCase):
    def test_kind2_roundtrips_through_independent_decoder(self) -> None:
        width, height = 5, 3
        native = bytearray()
        for y in range(height):
            for x in range(width):
                native.extend(
                    (
                        (x * 47 + y * 13) & 0xFF,
                        (x * 29 + y * 31) & 0xFF,
                        (x * 17 + y * 53) & 0xFF,
                        0x80,
                    )
                )
        payload, _ = encode_kind2(bytes(native), width, height)
        parsed = parse_crip008_header(
            header(
                kind=2,
                width=width,
                height=height,
                payload_length=len(payload),
            )
        )
        self.assertEqual(decode_kind2_subset(payload, width, height), native)
        self.assertEqual(decode_crip008_kind2_native(payload, parsed), native)

    def test_kind3_draw_rect_and_alpha_roundtrip_independently(self) -> None:
        width, height = 6, 4
        x_offset, y_offset, draw_width, draw_height = 1, 1, 4, 2
        native = bytearray(width * height * 4)
        pixels = (
            (10, 20, 30, 0),
            (40, 50, 60, 0x80),
            (70, 80, 90, 0x40),
            (100, 110, 120, 0x04),
            (130, 140, 150, 0x7C),
            (160, 170, 180, 0),
            (190, 200, 210, 0x80),
            (220, 230, 240, 0x20),
        )
        for index, pixel in enumerate(pixels):
            x = x_offset + index % draw_width
            y = y_offset + index // draw_width
            start = (y * width + x) * 4
            native[start : start + 4] = bytes(pixel)

        parameters = dict(
            width=width,
            height=height,
            x_offset=x_offset,
            y_offset=y_offset,
            draw_width=draw_width,
            draw_height=draw_height,
        )
        payload, _ = encode_kind3(bytes(native), **parameters)
        expected = bytearray(native)
        # Native transparent pixels carry no visible colour; the game decoder
        # canonicalizes their RGB bytes to zero.
        for pos in range(0, len(expected), 4):
            if expected[pos + 3] == 0:
                expected[pos : pos + 3] = b"\0\0\0"
        parsed = parse_crip008_header(
            header(kind=3, payload_length=len(payload), **parameters)
        )
        self.assertEqual(decode_kind3_subset(payload, **parameters), expected)
        self.assertEqual(decode_crip008_kind3_native(payload, parsed), expected)


if __name__ == "__main__":
    unittest.main()
