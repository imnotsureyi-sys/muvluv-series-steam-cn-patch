from __future__ import annotations

import unittest

from rUGP.formats.images.cr6ti_decode import (
    HEADER_SIZE,
    decode_standard_cr6ti_record,
    is_exact_standard_cr6ti_record,
    parse_standard_cr6ti_record,
)


class LsbWriter:
    def __init__(self) -> None:
        self.bits: list[int] = []

    def bit(self, value: int) -> None:
        self.bits.append(1 if value else 0)

    def unsigned(self, value: int) -> None:
        if value == 0:
            self.bit(0)
            return
        self.bit(1)
        digits = bin(value + 1)[3:]
        for index, digit in enumerate(digits):
            self.bit(int(digit))
            self.bit(index != len(digits) - 1)

    def signed(self, value: int) -> None:
        if value == 0:
            self.bit(0)
            return
        self.bit(1)
        self.bit(value < 0)
        digits = bin(abs(value))[3:]
        for digit in digits:
            self.bit(1)
            self.bit(int(digit))
        self.bit(0)

    def finish_word_aligned(self) -> bytes:
        output = bytearray((len(self.bits) + 7) // 8)
        for index, value in enumerate(self.bits):
            output[index >> 3] |= value << (index & 7)
        if len(output) & 1:
            output.append(0)
        return bytes(output)


def make_kind2_record() -> bytes:
    # One literal pixel followed by one repeated pixel.  The predictor emits
    # conventional PNG RGBA (30, 20, 10, 255) for both pixels.
    writer = LsbWriter()
    writer.unsigned(0)
    writer.bit(0)
    writer.signed(10)
    writer.signed(-5)
    writer.signed(5)
    writer.unsigned(0)
    payload = writer.finish_word_aligned()

    header = bytearray(HEADER_SIZE)
    header[:3] = b"\x00\x04\x45"
    header[0x06:0x08] = (2).to_bytes(2, "little")
    header[0x08:0x0A] = (1).to_bytes(2, "little")
    header[0x0E:0x10] = (2).to_bytes(2, "little")
    header[0x10:0x12] = (1).to_bytes(2, "little")
    header[0x12] = 2
    header[0x13] = 6
    header[0x14:0x1D] = b"\x81\x00\x07\x07\x07\x07\x00\x08\x00"
    header[0x20:0x24] = len(payload).to_bytes(4, "little")
    return bytes(header) + payload + b"\x00\x00"


class Cr6TiNativeDecodeTests(unittest.TestCase):
    def test_exact_standard_record_and_pixels(self) -> None:
        record = make_kind2_record()
        self.assertTrue(is_exact_standard_cr6ti_record(record))
        header = parse_standard_cr6ti_record(record)
        self.assertEqual(header.exact_extent, len(record))
        result = decode_standard_cr6ti_record(record)
        self.assertEqual(result.rgba, bytes((30, 20, 10, 255)) * 2)
        self.assertEqual(result.stats.decoded_pixels, 2)
        self.assertEqual(result.stats.repeated_pixels, 1)
        self.assertLessEqual(result.stats.zero_padding_bits, 15)

    def test_crip008_length_field_cannot_masquerade_as_cr6ti(self) -> None:
        # A CRip008-style object uses payload length at 0x1d and has no Cr6Ti
        # payload at 0x20.  Shared magic alone must not select this decoder.
        # Keep the fake object long enough to pass the Cr6Ti minimum-size
        # guard, so this specifically exercises the competing length field.
        record = bytearray(HEADER_SIZE + 2)
        record[:3] = b"\x00\x04\x45"
        record[0x06:0x08] = (1).to_bytes(2, "little")
        record[0x08:0x0A] = (1).to_bytes(2, "little")
        record[0x0E:0x10] = (1).to_bytes(2, "little")
        record[0x10:0x12] = (1).to_bytes(2, "little")
        record[0x12] = 2
        record[0x1D:0x21] = (3).to_bytes(4, "little")
        with self.assertRaisesRegex(ValueError, "payload length at 0x20 is zero"):
            parse_standard_cr6ti_record(bytes(record))

    def test_extent_and_trailer_are_strict(self) -> None:
        record = make_kind2_record()
        with self.assertRaisesRegex(ValueError, "record extent"):
            parse_standard_cr6ti_record(record + b"\x00")
        corrupt = bytearray(record)
        corrupt[-1] = 1
        with self.assertRaisesRegex(ValueError, "trailer"):
            parse_standard_cr6ti_record(bytes(corrupt))

    def test_nonzero_bit_padding_is_rejected(self) -> None:
        record = bytearray(make_kind2_record())
        clean = decode_standard_cr6ti_record(bytes(record))
        # Flip the first bit after the decoder's actual stopping position,
        # rather than assuming which byte contains only alignment bits.
        padding_bit = clean.stats.consumed_bits
        self.assertLess(padding_bit, clean.stats.payload_bits)
        record[HEADER_SIZE + padding_bit // 8] |= 1 << (padding_bit & 7)
        with self.assertRaisesRegex(ValueError, "padding contains a set bit"):
            decode_standard_cr6ti_record(bytes(record))


if __name__ == "__main__":
    unittest.main()
