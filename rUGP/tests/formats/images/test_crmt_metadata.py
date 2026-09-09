from __future__ import annotations

from dataclasses import replace
import json
import struct
import unittest

from rUGP.formats.images.crimp import CrimpProperty, CrimpRecord, CrimpValue
from rUGP.formats.images.crmt_metadata import CrmtMetadataError, crmt_origin, parse_crmt_metadata
from rUGP.formats.rio.crypto import encode_extent_offset, encode_extent_size


def header(*, image_mp=True, auxiliary=False, ancestors=5, width=541, height=236,
           scale=(65536, 65536), base=(0, 0), count=4):
    """Synthetic metadata, not a game image or an installed resource."""
    parts = [bytes((0x80, 4, 2, ancestors))]
    slots = 4 + ancestors
    image_index = 0
    for enabled, name, schema, offset, extent in (
        (image_mp, bytes.fromhex("3c a1 e5"), 4, 0x1000, 64),
        (auxiliary, bytes.fromhex("3c 35 e4"), 1, 0x2000, 256),
    ):
        if enabled:
            parts.append(struct.pack("<HHB", 0xFFFF, schema, len(name)) + name)
            parts.append(struct.pack("<HIIHB", 0xC108, encode_extent_offset(offset, 4),
                                     encode_extent_size(extent), 4, 0))
            slots += 2
            if schema == 4:
                image_index = slots - 1
        else:
            parts.append(b"\0\0")
    slots += 1  # Generic loader maps its +D4 archive object after dependencies.
    mip_class = slots
    parts.append(struct.pack("<HHHHHHiiiiBHIHB", 1, 4, 4, 10, width, height,
                             *scale, *base, 0, 85, 0xFFFFFFFF, image_index, count))
    parts.append(struct.pack("<HH", 0x8000 | mip_class, 0xC040))
    return b"".join(parts)


def properties(**values):
    return CrimpRecord(tuple(CrimpProperty(name, value, 0, 0, 0) for name, value in values.items()), b"\0" * 5)


class CrmtMetadataTests(unittest.TestCase):
    def test_all_five_layouts(self):
        for imp, aux, n, offset, cls in (
            (False, False, 5, 0x2D, 10), (True, False, 5, 0x40, 12),
            (True, True, 5, 0x53, 14), (True, False, 6, 0x40, 13), (True, True, 6, 0x53, 15),
        ):
            with self.subTest(imp=imp, aux=aux, ancestors=n):
                data = header(image_mp=imp, auxiliary=aux, ancestors=n)
                parsed = parse_crmt_metadata(data)
                self.assertEqual((parsed.count_offset, parsed.first_mip_class_index), (offset, cls))
                self.assertEqual(parsed.preamble, data[:-4])
                self.assertEqual(parsed.ancestor_count, n)
                self.assertEqual(parsed.image_mp.kind, "object_alias" if imp else "null")
                if imp:
                    ref = parsed.image_mp.resource
                    self.assertEqual((ref.class_name, ref.schema, ref.global_offset, ref.extent), ("CRimp", 4, 0x1000, 64))
                    self.assertEqual(ref.object_cache_index, 5 + n)
                    self.assertIs(ref, parsed.dependencies[0].resource)

    def test_post_dependency_slot_is_not_skipped(self):
        parsed = parse_crmt_metadata(header())
        self.assertEqual(parsed.post_dependency_cache_index, 11)
        self.assertEqual(parsed.registered_classes, (("CRmti", 1, 12), ("CRimp", 4, 13), ("Cr6Ti", 4, 14)))
        wrong = bytearray(header())
        wrong[-4:-2] = struct.pack("<H", 0x800B)
        with self.assertRaises(CrmtMetadataError):
            parse_crmt_metadata(bytes(wrong))

    def test_every_truncated_prefix_is_rejected(self):
        for args in ({}, {"auxiliary": True}, {"image_mp": False}, {"ancestors": 6}):
            data = header(**args)
            for length in range(len(data)):
                with self.subTest(args=args, length=length), self.assertRaises(CrmtMetadataError):
                    parse_crmt_metadata(data[:length])

    def test_unknown_compact_prefixes(self):
        for position, value in ((0, 0), (1, 3), (2, 1), (3, 4), (3, 255)):
            data = bytearray(header())
            data[position] = value
            with self.subTest(position=position, value=value), self.assertRaises(CrmtMetadataError):
                parse_crmt_metadata(bytes(data))

    def test_unknown_class_schema_flags_and_tail(self):
        for position, payload in ((6, b"\x03\0"), (8, b"\xff"), (9, b"x"),
                                  (12, b"\x40\xc0"), (22, b"\xff\xff"), (24, b"\x01")):
            data = bytearray(header())
            data[position:position + len(payload)] = payload
            with self.subTest(position=position), self.assertRaises(CrmtMetadataError):
                parse_crmt_metadata(bytes(data))

    def test_invalid_object_aliases(self):
        original = header()
        parsed = parse_crmt_metadata(original)
        for alias in (9, 12, 4, 127, 0x7FFF):
            data = bytearray(original)
            data[parsed.image_mp.start:parsed.image_mp.end] = struct.pack("<H", alias)
            with self.subTest(alias=alias), self.assertRaises(CrmtMetadataError):
                parse_crmt_metadata(bytes(data))

    def test_non_crimp_resource_cannot_be_imagemp(self):
        original = header(auxiliary=True)
        parsed = parse_crmt_metadata(original)
        data = bytearray(original)
        data[parsed.image_mp.start:parsed.image_mp.end] = struct.pack("<H", parsed.dependencies[1].cache_index)
        with self.assertRaisesRegex(CrmtMetadataError, "ImageMP"):
            parse_crmt_metadata(bytes(data))

    def test_registered_schema_and_version_fail_closed(self):
        for position in (27, 29, 31, 33):
            data = bytearray(header())
            data[position] ^= 1
            with self.subTest(position=position), self.assertRaises(CrmtMetadataError):
                parse_crmt_metadata(bytes(data))

    def test_invalid_mip_counts_and_sizes(self):
        for args in ({"count": 0}, {"count": 7}, {"width": 0}, {"height": 0}):
            with self.subTest(args=args), self.assertRaises(CrmtMetadataError):
                parse_crmt_metadata(header(**args))

    def test_scale_and_opaque_fields_are_preserved(self):
        metadata = parse_crmt_metadata(header(scale=(65535, 0), base=(-65536, 32768)))
        self.assertEqual(metadata.scale_i32, (65535, 0))
        self.assertEqual(metadata.as_dict()["effective_scale_i32"], [65535, 65535])
        self.assertEqual(metadata.base_offset_i32, (-65536, 32768))
        self.assertEqual((metadata.field_33_u8, metadata.field_34_u16, metadata.field_40_u32), (0, 85, 0xFFFFFFFF))
        self.assertEqual(json.loads(json.dumps(metadata.as_dict())), metadata.as_dict())

    def test_does_not_parse_or_change_pixel_payload(self):
        data = header() + b"not a decoded pixel payload"
        before = bytes(data)
        self.assertEqual(parse_crmt_metadata(data), parse_crmt_metadata(header()))
        self.assertEqual(data, before)


class CrmtOriginTests(unittest.TestCase):
    def test_e10_point32(self):
        metadata = parse_crmt_metadata(header())
        crimp = properties(原点=CrimpValue("inline_struct", struct_name="_CPoint32", components_i32=(17694976, 7721444)))
        result = crmt_origin(metadata, crimp)
        self.assertEqual(result["components_i32"], [17694976, 7721444])
        self.assertEqual(result["pixel_projection"], [270.00390625, 117.81988525390625])
        self.assertFalse(result["runtime_observed"])
        self.assertFalse(result["scene_position_established"])

    def test_point32_subtracts_offset_with_i32_wrap(self):
        metadata = parse_crmt_metadata(header(base=(65536, -65536)))
        crimp = properties(原点=CrimpValue("inline_struct", struct_name="_CPoint32", components_i32=(-2147483648, 2147483647)))
        self.assertEqual(crmt_origin(metadata, crimp)["components_i32"], [2147418112, -2147418113])

    def test_integer_origin_is_shifted_tag_payload_not_wire_word(self):
        metadata = parse_crmt_metadata(header(base=(12345, 54321)))
        crimp = properties(原点=CrimpValue("tagged_integer", integer=(-13 << 16) | 0xFFF9))
        result = crmt_origin(metadata, crimp)
        self.assertEqual(result["branch"], "packed_integer_origin")
        self.assertEqual(result["pixel_projection"], [-7, -13])

    def test_baseline_adds_offset(self):
        metadata = parse_crmt_metadata(header(base=(32768, -65536)))
        crimp = properties(基準立ち位置Y=CrimpValue("tagged_integer", integer=(19 << 16) | 7))
        result = crmt_origin(metadata, crimp)
        self.assertEqual(result["branch"], "packed_baseline_plus_base_offset")
        self.assertEqual(result["pixel_projection"], [7.5, 18])

    def test_origin_takes_precedence(self):
        metadata = parse_crmt_metadata(header())
        crimp = properties(原点=CrimpValue("tagged_integer", integer=4),
                           基準立ち位置Y=CrimpValue("tagged_integer", integer=20))
        self.assertEqual(crmt_origin(metadata, crimp)["pixel_projection"], [4, 0])

    def test_missing_or_unsupported_property_defaults(self):
        metadata = parse_crmt_metadata(header())
        for crimp in (properties(), properties(標準視点=CrimpValue("tagged_integer", integer=123)),
                      properties(原点=CrimpValue("inline_struct", struct_name="_CVector32", components_i32=(1, 2, 3)))):
            self.assertEqual(crmt_origin(metadata, crimp)["pixel_projection"], [270.5, 236])

    def test_null_imagemp_defaults_and_signed_dimensions(self):
        metadata = parse_crmt_metadata(header(image_mp=False, width=32769, height=65535))
        self.assertEqual(crmt_origin(metadata, None)["pixel_projection"], [-16383.5, -1])

    def test_missing_or_extraneous_crimp_rejected(self):
        for metadata, crimp in ((parse_crmt_metadata(header()), None),
                                (parse_crmt_metadata(header(image_mp=False)), properties())):
            with self.assertRaises(CrmtMetadataError):
                crmt_origin(metadata, crimp)

    def test_scale_does_not_rescale_this_origin_query(self):
        metadata = parse_crmt_metadata(header())
        crimp = properties(原点=CrimpValue("tagged_integer", integer=(9 << 16) | 7))
        self.assertEqual(crmt_origin(metadata, crimp), crmt_origin(replace(metadata, scale_i32=(131072, 1)), crimp))


if __name__ == "__main__":
    unittest.main()
