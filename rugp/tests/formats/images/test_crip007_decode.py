from __future__ import annotations

import unittest

from rugp.formats.images.crip007_decode import (
    decode_legacy_rip007_bgra,
    legacy_bgra_to_rgba,
)


class LegacyRip007DecodeTests(unittest.TestCase):
    def test_opaque_black_does_not_pollute_vertical_rgb_prediction(self) -> None:
        # Five one-pixel rows.  Rows 1, 3 and 4 copy from above; rows 0 and 2
        # explicitly decode zero.  The MSB bitstream is exactly two bytes.
        decoded = decode_legacy_rip007_bgra(
            bytes((0x02, 0x05)), 1, 5, 0, 6, 6, 6, 1
        )
        self.assertEqual(decoded, bytes((0, 0, 0, 0x80)) * 5)

    def test_nonzero_and_black_pixels_both_keep_native_bgr32_opacity(self) -> None:
        # Row 0 creates a +1 neutral colour delta, row 1 copies it; row 2 is
        # exact zero and row 3 copies that zero.  Correct packed BGRA values
        # are therefore native BGR32 (7,7,7,0x80) twice followed by opaque
        # black (0,0,0,0x80) twice.
        bgra = decode_legacy_rip007_bgra(
            bytes((0x20, 0x81)), 1, 4, 0, 6, 6, 6, 1
        )
        self.assertEqual(
            bgra,
            bytes((7, 7, 7, 0x80, 7, 7, 7, 0x80, 0, 0, 0, 0x80, 0, 0, 0, 0x80)),
        )
        self.assertEqual(
            legacy_bgra_to_rgba(bgra),
            bytes(
                (
                    7, 7, 7, 255,
                    7, 7, 7, 255,
                    0, 0, 0, 255,
                    0, 0, 0, 255,
                )
            ),
        )
        self.assertEqual(legacy_bgra_to_rgba(bgra, force_opaque=False), bgra)


if __name__ == "__main__":
    unittest.main()
