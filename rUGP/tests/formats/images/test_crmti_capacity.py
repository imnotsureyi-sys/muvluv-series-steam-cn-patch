from __future__ import annotations

import unittest

from rUGP.formats.images.crmti_capacity import capacity_for_ranges
from rUGP.formats.images.crmti_decode import decode_crmt, parse_crmt
from rUGP.formats.images.crmti_encode import encode_crmt
from rUGP.tests.formats.images.test_crmti_codec import template


class CrmtiCapacityTests(unittest.TestCase):
    def test_sentinels_and_native_guard_are_not_rgba_size(self):
        capacity = capacity_for_ranges(4, 3, 3, [(0, 4)] * 3)
        # Five expanded rows: 6, 6, 6, 6, 8 pixels. Cursor: 4+5*8+32*4.
        self.assertEqual(capacity.expanded_pixel_bytes, 128)
        self.assertEqual(capacity.guard_cursor, 172)
        self.assertEqual(capacity.required_hint, 140)
        self.assertFalse(capacity.accepts(4*3*4))
        self.assertFalse(capacity.accepts(139))
        self.assertTrue(capacity.accepts(140))

    def test_sparse_neighbour_union_and_empty_tail(self):
        capacity = capacity_for_ranges(12, 7, 3, [(7, 9), (0, 0), (1, 4)] + [(0, 0)]*4)
        # y=-1..3: 4,4,10,5,7, including union across the empty centre row.
        self.assertEqual(capacity.expanded_pixel_bytes, 120)
        self.assertEqual(capacity.guard_cursor, 164)
        self.assertEqual(capacity.physical_storage_bytes, 196)
        self.assertEqual(capacity.required_hint, 116)
        self.assertTrue(capacity.accepts(116))

    def test_empty_image_and_preserved_larger_source(self):
        capacity = capacity_for_ranges(10, 5, 0, [(0, 0)]*5)
        self.assertEqual(capacity.required_hint, 0)
        self.assertEqual(capacity.replacement_hint(12345), 12345)
        self.assertTrue(capacity.accepts(0))

    def test_invalid_native_dimensions_ranges_and_overflow(self):
        for args in [(0, 1, 0, [(0, 0)]), (0x8000, 1, 0, [(0, 0)]),
                     (10, 1, 2, [(0, 1)]), (10, 1, 1, [(2, 11)]),
                     (10, 1, 0, [(1, 2)]), (10, 2, 1, [(1, 2)])]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                capacity_for_ranges(*args)
        capacity = capacity_for_ranges(1, 1, 1, [(0, 1)])
        with self.assertRaises(ValueError):
            capacity.replacement_hint(0x7FFFFFFF)
        with self.assertRaises(ValueError):
            capacity.replacement_hint(-1)

    def test_encoder_grows_metadata_and_readback_rejects_old_hint(self):
        source = template(4, 3, 0x0707070F)
        encoded, expected, stats = encode_crmt(source, [bytes((250, 250, 250, 255))*12])
        level = parse_crmt(encoded)[0][0]
        decoded, _ = decode_crmt(encoded)
        capacity = capacity_for_ranges(4, 3, level.active_row_count, decoded[0].active_ranges)
        self.assertEqual(decoded[0].rgba, expected[0])
        self.assertEqual(level.decoded_size_hint, 140)
        self.assertEqual(stats['levels'][0]['replacement_decoded_size_hint'], 140)
        damaged = bytearray(encoded)
        damaged[level.header_offset+12:level.header_offset+16] = (48).to_bytes(4, 'little')
        # Pixel-only readback STILL succeeds. The independent gate catches it.
        self.assertEqual(decode_crmt(bytes(damaged))[0][0].rgba, expected[0])
        self.assertFalse(capacity.accepts(parse_crmt(bytes(damaged))[0][0].decoded_size_hint))

    def test_capacity_independent_of_repeat_compression(self):
        source = template(11, 4, 0x0707070F)
        pixels = [bytes((250, 250, 250, 255))*44]
        first = encode_crmt(source, pixels, allow_repeat=True)[0]
        second = encode_crmt(source, pixels, allow_repeat=False)[0]
        self.assertNotEqual(len(first), len(second))
        self.assertEqual(parse_crmt(first)[0][0].decoded_size_hint,
                         parse_crmt(second)[0][0].decoded_size_hint)


if __name__ == '__main__':
    unittest.main()
