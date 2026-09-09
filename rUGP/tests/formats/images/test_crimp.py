from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest

from rUGP.formats.images.crimp import (
    CrimpDecodeError, CrimpProperty, CrimpRecord, CrimpValue, decode_value, parse_crimp,
)
from rUGP.tools.images.inspect_crimp import inspect_record, main
from rUGP.tools.provenance.export_crmt_structure_trigger_evidence import compact_crimp, compact_crimp_section


def example_record() -> CrimpRecord:
    return CrimpRecord((
        CrimpProperty("標準視点", CrimpValue("tagged_integer", integer=7667982), 0, 0, 0),
        CrimpProperty("原点", CrimpValue("inline_struct", struct_name="_CPoint32",
                                      components_i32=(17694976, 7721444)), 0, 0, 0),
    ), bytes.fromhex("00 00 05 00 00"))


class CrimpCodecTests(unittest.TestCase):
    def test_four_bytes_are_tagged_integer_not_fixed16(self):
        value, end = decode_value(bytes.fromhex("3a 04 d4 01"))
        self.assertEqual(end, 4)
        self.assertEqual((value.kind, value.integer), ("tagged_integer", 7667982))
        self.assertEqual(value.to_bytes(), bytes.fromhex("3a 04 d4 01"))
        self.assertEqual(value.as_dict()["semantic_units"], "not_established")

    def test_signed_integer_boundaries(self):
        for number in (-(1 << 29), -1, 0, 1, (1 << 29) - 1):
            original = CrimpValue("tagged_integer", integer=number)
            value, end = decode_value(original.to_bytes())
            self.assertEqual((value, end), (original, 4))
        for number in (-(1 << 29) - 1, 1 << 29, True):
            with self.assertRaises(CrimpDecodeError):
                CrimpValue("tagged_integer", integer=number).to_bytes()

    def test_record_exact_byte_roundtrip_and_offsets(self):
        data = example_record().to_bytes()
        record = parse_crimp(data)
        self.assertEqual(len(data), 64)
        self.assertEqual(record.to_bytes(), data)
        self.assertEqual([(p.name_offset, p.value_offset, p.end_offset) for p in record.properties],
                         [(4, 16, 20), (20, 28, 55)])

    def test_struct_components_are_preserved_without_unit_claim(self):
        value = CrimpValue("inline_struct", struct_name="_CVector32", components_i32=(-1, 65536, -(1 << 31)))
        decoded, end = decode_value(value.to_bytes())
        self.assertEqual(decoded, value)
        self.assertEqual(end, 32)
        self.assertEqual(decoded.as_dict()["component_units"], "not_established")

    def test_marker_inside_struct_data_is_not_a_property_boundary(self):
        source = example_record()
        point = CrimpValue("inline_struct", struct_name="_CPoint32", components_i32=(0x00FFFEFF, 7))
        source = replace(source, properties=(source.properties[0], replace(source.properties[1], value=point)))
        raw = source.to_bytes()
        self.assertEqual(raw.count(b"\xff\xfe\xff"), 4)
        self.assertEqual(len(parse_crimp(raw).properties), 2)

    def test_unknown_tags_fail_instead_of_scalar_fallback(self):
        for tag in (0, 1, 3, 8):
            with self.assertRaisesRegex(CrimpDecodeError, "unsupported.*tag"):
                decode_value(struct.pack("<I", tag))

    def test_changed_inline_descriptor_or_type_fails(self):
        raw = bytearray(example_record().properties[1].value.to_bytes())
        raw[4] ^= 1
        with self.assertRaisesRegex(CrimpDecodeError, "descriptor"):
            decode_value(bytes(raw))
        raw = example_record().properties[1].value.to_bytes().replace(b"_CPoint32", b"_Unknown3")
        with self.assertRaisesRegex(CrimpDecodeError, "struct type"):
            decode_value(raw)

    def test_truncation_and_trailing_bytes_fail(self):
        raw = example_record().to_bytes()
        for end in range(len(raw)):
            with self.assertRaises(CrimpDecodeError):
                parse_crimp(raw[:end])
        with self.assertRaises(CrimpDecodeError):
            parse_crimp(raw + b"\0")

    def test_header_count_and_terminal_fail_closed(self):
        source = example_record().to_bytes()
        for offset, value in ((1, 3), (2, 3), (len(source) - 1, 1)):
            raw = bytearray(source)
            raw[offset] = value
            with self.assertRaises(CrimpDecodeError):
                parse_crimp(bytes(raw))

    def test_duplicate_names_are_outside_bounded_profile(self):
        source = example_record()
        invalid = replace(source, properties=(source.properties[0], source.properties[0]))
        with self.assertRaisesRegex(CrimpDecodeError, "duplicate"):
            invalid.to_bytes()

    def test_cli_reads_exact_extent_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "sample.rio"
            data = b"BEFORE" + example_record().to_bytes() + b"AFTER"
            source.write_bytes(data)
            output = io.StringIO()
            with redirect_stdout(output):
                status = main(["--source", str(source), "--offset", "6", "--extent", "64"])
            self.assertEqual(status, 0)
            report = json.loads(output.getvalue())
            self.assertFalse(report["is_raster_image"])
            self.assertEqual(report["files_written"], 0)
            self.assertEqual(source.read_bytes(), data)
            self.assertEqual(list(root.iterdir()), [source])

    def test_cli_rejects_bad_extent(self):
        with tempfile.TemporaryDirectory() as raw:
            source = Path(raw) / "sample.rio"
            source.write_bytes(example_record().to_bytes())
            with redirect_stdout(io.StringIO()):
                status = main(["--source", str(source), "--offset", "0", "--extent", "65"])
            self.assertEqual(status, 1)

    def test_exporter_redecodes_wire_bytes_not_legacy_numeric_projection(self):
        record = {"game": "PF", "volume": "sample.rio", "offset_hex": "0x0", "extent": 64,
                  "sha256": "A" * 64, "declared_occurrence_count": 1, "catalog_node_count": 0,
                  "property_envelope": {"properties": [
                      {"name": "標準視点", "value_kind": "fixed16_scalar", "decoded_value": {"value": 9999},
                       "value_hex": "3a 04 d4 01"}]}}
        compact = compact_crimp(record)
        self.assertEqual(compact["property_value_decoder"], "native_tagged_values_v1")
        self.assertEqual(compact["properties"][0]["decoded_value"]["value"], 7667982)
        record["property_envelope"]["properties"][0]["value_hex"] += " 00"
        with self.assertRaisesRegex(ValueError, "trailing"):
            compact_crimp(record)

    def test_export_summary_does_not_republish_old_numeric_claims(self):
        summary = {"all_unique_physical_records": 0, "decoded_value_kind_distribution": {"fixed16_scalar": 8},
                   "unit_vector_norm_range": {"all_within_0.001_of_one": True}}
        projected = compact_crimp_section({"summary": summary, "records": []})["summary"]
        self.assertNotIn("unit_vector_norm_range", projected)
        self.assertEqual(projected["decoded_value_kind_distribution"], {})
        self.assertFalse(projected["scene_coordinate_units_established"])
        self.assertIn("unit_vector_norm_range", summary)


if __name__ == "__main__":
    unittest.main()
