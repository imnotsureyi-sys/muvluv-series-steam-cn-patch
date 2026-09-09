from __future__ import annotations

import unittest

from rUGP.formats.images.crmti_decode import decode_crmt, parse_crmt
from rUGP.formats.images.crmti_encode import encode_crmt


LAYOUTS = (
    (bytes.fromhex("80 04 02 05"), 0x2D, bytes.fromhex("0a 80 40 c0"), 0x0505050F),
    (bytes.fromhex("80 04 02 05"), 0x40, bytes.fromhex("0c 80 40 c0"), 0x0606060F),
    (bytes.fromhex("80 04 02 05"), 0x53, bytes.fromhex("0e 80 40 c0"), 0x07070707),
    (bytes.fromhex("80 04 02 06"), 0x40, bytes.fromhex("0d 80 40 c0"), 0x0707070F),
    (bytes.fromhex("80 04 02 06"), 0x53, bytes.fromhex("0f 80 40 c0"), 0x0505050F),
)


def template(prefix: bytes, count_offset: int, wrapper: bytes, meta: int) -> bytes:
    parent = bytearray(count_offset + 1)
    parent[:4] = prefix
    # Non-zero audited-parent bytes make accidental hard-coded 0x41 slicing
    # visible without assigning semantics to the parent payload.
    for index in range(4, count_offset):
        parent[index] = (index * 37 + count_offset) & 0xFF
    parent[count_offset] = 1
    width, height = 7, 5
    child = bytearray(18)
    child[0:2] = width.to_bytes(2, "little")
    child[2:4] = height.to_bytes(2, "little")
    child[4:8] = meta.to_bytes(4, "little")
    child[8:12] = (2).to_bytes(4, "little")
    child[12:16] = (width * height * 4).to_bytes(4, "little")
    return bytes(parent) + wrapper + bytes(child) + b"\0\0AUDITED-TRAILER"


class CrmtiParentLayoutTests(unittest.TestCase):
    def test_all_five_census_layouts_roundtrip_and_preserve_framing(self) -> None:
        for prefix, count_offset, wrapper, meta in LAYOUTS:
            with self.subTest(prefix=prefix.hex(), count_offset=count_offset):
                original = template(prefix, count_offset, wrapper, meta)
                width, height = 7, 5
                rgba = bytes((0, 0, 0, 255)) * (width * height)

                encoded, expected, stats = encode_crmt(original, [rgba])
                parsed, trailer = parse_crmt(encoded)
                decoded, decoded_trailer = decode_crmt(encoded)

                self.assertEqual(encoded[: count_offset + 1], original[: count_offset + 1])
                self.assertEqual(
                    encoded[parsed[0].wrapper_offset : parsed[0].header_offset], wrapper
                )
                self.assertEqual(trailer, b"AUDITED-TRAILER")
                self.assertEqual(decoded_trailer, trailer)
                self.assertEqual(decoded[0].rgba, expected[0])
                self.assertEqual(stats["child_table_offset"], count_offset + 1)
                self.assertEqual(stats["child_wrapper_hex"], wrapper.hex(" "))

    def test_unobserved_wrapper_is_rejected(self) -> None:
        original = bytearray(template(*LAYOUTS[0]))
        original[0x2E] = 0x7F
        with self.assertRaisesRegex(ValueError, "no audited child-table layout"):
            parse_crmt(bytes(original))

    def test_unobserved_prefix_is_rejected(self) -> None:
        original = bytearray(template(*LAYOUTS[0]))
        original[3] = 0x07
        with self.assertRaisesRegex(ValueError, "prefix mismatch"):
            parse_crmt(bytes(original))


if __name__ == "__main__":
    unittest.main()
