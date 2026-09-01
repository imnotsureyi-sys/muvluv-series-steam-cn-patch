from __future__ import annotations

import unittest

from rUGP.formats.images.crip007_encode import (
    HEADER_SIZE,
    decode_record_rgba,
    decode_scoped_reference_rgba,
    encode_extent_offset_unit4,
    encode_record_from_rgba,
    parse_legacy_record,
)


def source_header(width: int, height: int) -> bytes:
    header = bytearray.fromhex(
        "0004450000002003580200000000200358020206810003000001060606040000"
        "0000000000000000"
    )
    header[0x06:0x08] = width.to_bytes(2, "little")
    header[0x08:0x0A] = height.to_bytes(2, "little")
    header[0x0E:0x10] = width.to_bytes(2, "little")
    header[0x10:0x12] = height.to_bytes(2, "little")
    header[0x20:0x24] = (0).to_bytes(4, "little")
    return bytes(header)


class CRip007LiteralEncoderTests(unittest.TestCase):
    def test_all_8bit_grayscale_levels_roundtrip_exactly(self) -> None:
        width, height = 256, 12
        gray = (
            bytes(range(256))
            + bytes(reversed(range(256)))
            + bytes(range(256)) * 2
            + bytes(256) * 8
        )
        rgba = b"".join(bytes((value, value, value, 255)) for value in gray)
        record = encode_record_from_rgba(source_header(width, height), rgba, width, height)
        header, decoded = decode_record_rgba(record)
        self.assertEqual(decoded, rgba)
        self.assertEqual(decode_scoped_reference_rgba(record), rgba)
        self.assertEqual((header.b_bits, header.g_bits, header.r_bits), (8, 8, 8))
        self.assertEqual(len(record), HEADER_SIZE + header.payload_length)

    def test_native_high_byte_maps_to_opaque_png_alpha(self) -> None:
        width, height = 8, 4
        values = (0, 1, 255, 128, 128, 128, 7, 3) + (0,) * 24
        rgba = b"".join(bytes((value, value, value, 255)) for value in values)
        record = encode_record_from_rgba(source_header(width, height), rgba, width, height)
        _, decoded = decode_record_rgba(record)
        self.assertEqual(decoded, rgba)
        self.assertEqual(set(decoded[3::4]), {255})

    def test_source_key_is_exact_unit4_encoding(self) -> None:
        self.assertEqual(encode_extent_offset_unit4(0x1AD8246C), 0xA9B173EC)
        self.assertEqual(encode_extent_offset_unit4(0x1B158BB4), 0xA9C0CDBE)
        self.assertEqual(encode_extent_offset_unit4(0x65D765DC), 0xBC714448)
        self.assertEqual(encode_extent_offset_unit4(0x663F3BEC), 0xBC8B39CC)

    def test_rejects_nonopaque_or_nongrayscale_candidate(self) -> None:
        source = source_header(1, 1)
        with self.assertRaisesRegex(ValueError, "fully opaque"):
            encode_record_from_rgba(source, bytes((1, 1, 1, 128)), 1, 1)
        with self.assertRaisesRegex(ValueError, "grayscale"):
            encode_record_from_rgba(source, bytes((1, 2, 1, 255)), 1, 1)

    def test_no_trailer_and_payload_extent_are_strict(self) -> None:
        source = source_header(1, 1)
        with self.assertRaisesRegex(ValueError, r"0x28 \+ payload"):
            parse_legacy_record(source + b"\x00")


if __name__ == "__main__":
    unittest.main()
