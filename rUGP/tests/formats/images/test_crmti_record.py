from __future__ import annotations

from dataclasses import replace
import struct
import unittest
from unittest.mock import patch

from rUGP.formats.images.crmti_encode import encode_level
from rUGP.formats.images.crmti_record import (
    StandaloneCrmtiError, decode_standalone_crmti, parse_standalone_crmti,
    parse_standalone_header,
)


def fixture(width=5, height=3, *, transparent=False):
    rgba = b"\0\0\0\0" * (width * height) if transparent else (
        bytes((42, 100, 198, 255)) * width +
        bytes((10, 22, 34, 128)) * width +
        b"\0\0\0\0" * width
    )
    if not transparent and height != 3:
        rgba = bytes((42, 100, 198, 255)) * (width * height)
    blob, active, expected, _ = encode_level(width=width, height=height, meta=0x0707070F, rgba=rgba)
    # A zero-active-row bitstream needs explicit zero padding to satisfy the
    # observed standalone envelope's non-empty blob rule.
    blob = blob or b"\0\0"
    return b"\0\1" + struct.pack("<HHIIIH", width, height, 0x0707070F, len(blob), 12345, active) + blob, expected


class StandaloneCrmtiTests(unittest.TestCase):
    def test_exact_frame_roundtrip_and_pixel_decode(self):
        raw, expected = fixture()
        frame = parse_standalone_crmti(raw)
        self.assertEqual(frame.to_bytes(), raw)
        self.assertEqual(decode_standalone_crmti(raw).rgba, expected)

    def test_no_inline_wrapper_and_real_offsets(self):
        raw, _ = fixture()
        level = parse_standalone_crmti(raw).as_level()
        self.assertEqual((level.wrapper_offset, level.header_offset, level.blob_offset, level.blob_end),
                         (-1, 2, 20, len(raw)))

    def test_decoded_hint_is_not_an_rgba_size_assertion(self):
        raw, _ = fixture()
        self.assertEqual(parse_standalone_crmti(raw).header.decoded_size_hint, 12345)
        self.assertEqual(len(decode_standalone_crmti(raw).rgba), 60)

    def test_empty_active_canvas_is_preserved(self):
        raw, expected = fixture(2, 2, transparent=True)
        result = decode_standalone_crmti(raw)
        self.assertEqual(result.rgba, expected)
        self.assertEqual(result.level.active_row_count, 0)

    def test_every_truncation_and_external_trailing_byte_rejected(self):
        raw, _ = fixture()
        for n in range(len(raw)):
            with self.subTest(n=n), self.assertRaises(StandaloneCrmtiError):
                parse_standalone_crmti(raw[:n])
        with self.assertRaises(StandaloneCrmtiError):
            parse_standalone_crmti(raw + b"\0")

    def test_compact_schema_and_inline_wrapper_rejected(self):
        raw, _ = fixture()
        for prefix in (b"\0\4", b"\x80\1", b"\x0c\x80\x40\xc0"):
            with self.subTest(prefix=prefix), self.assertRaises(StandaloneCrmtiError):
                parse_standalone_crmti(prefix + raw[2:])

    def test_other_embedded_profiles_not_promoted_to_standalone_support(self):
        raw, _ = fixture()
        for meta in (0x07070707, 0x0505050F, 0x0606060F, 0x0808080F):
            bad = raw[:6] + struct.pack("<I", meta) + raw[10:]
            with self.subTest(meta=meta), self.assertRaisesRegex(StandaloneCrmtiError, "profile"):
                decode_standalone_crmti(bad)

    def test_zero_dimensions_and_oversized_canvas_rejected_before_codec(self):
        raw, _ = fixture()
        for width, height in ((0, 2), (2, 0), (65535, 65535)):
            bad = raw[:2] + struct.pack("<HH", width, height) + raw[6:]
            with patch("rUGP.formats.images.crmti_record.decode_level") as codec:
                with self.assertRaises(StandaloneCrmtiError):
                    decode_standalone_crmti(bad)
                codec.assert_not_called()

    def test_active_rows_overflow_rejected(self):
        raw, _ = fixture()
        with self.assertRaisesRegex(StandaloneCrmtiError, "active row"):
            parse_standalone_crmti(raw[:18] + struct.pack("<H", 4) + raw[20:])

    def test_zero_blob_and_bad_declared_length_rejected(self):
        raw, _ = fixture()
        for length in (0, 1, len(raw), 0xFFFFFFFF):
            with self.subTest(length=length), self.assertRaises(StandaloneCrmtiError):
                parse_standalone_crmti(raw[:10] + struct.pack("<I", length) + raw[14:])

    def test_framing_does_not_claim_valid_pixels(self):
        raw = b"\0\1" + struct.pack("<HHIIIH", 1, 1, 0x0707070F, 1, 0, 1) + b"\xff"
        self.assertEqual(parse_standalone_crmti(raw).to_bytes(), raw)
        with self.assertRaises(ValueError):
            decode_standalone_crmti(raw)

    def test_nonzero_tail_rejected_by_pixel_codec(self):
        raw, _ = fixture(1, 1, transparent=True)
        bad = raw[:-1] + b"\x80"
        with self.assertRaisesRegex(ValueError, "padding"):
            decode_standalone_crmti(bad)

    def test_header_only_api_requires_exact_window_and_integer_extent(self):
        raw, _ = fixture()
        for header, extent in ((raw[:19], len(raw)), (raw[:21], len(raw)), (raw[:20], True),
                               (raw[:20], 2**40)):
            with self.subTest(extent=extent), self.assertRaises(StandaloneCrmtiError):
                parse_standalone_header(header, extent)

    def test_mutated_frame_cannot_bypass_extent_validation(self):
        raw, _ = fixture()
        frame = parse_standalone_crmti(raw)
        bad = replace(frame, blob=frame.blob + b"\0")
        with self.assertRaises(StandaloneCrmtiError):
            bad.to_bytes()
        with self.assertRaises(StandaloneCrmtiError):
            bad.as_level()


if __name__ == "__main__":
    unittest.main()
