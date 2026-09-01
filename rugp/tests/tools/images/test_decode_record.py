from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest

from rugp.formats.images.crip008_kind3_encode import encode_native_pixels
from rugp.tools.images.decode_record import (
    ImageExtractError,
    build_outputs,
    decode_record,
    write_new_outputs,
)


def crip008_header(
    width: int,
    height: int,
    payload_length: int,
    *,
    kind: int = 3,
    depth: int = 3,
    flags: int = 2,
    header_version: int = 0,
) -> bytes:
    data = bytearray(0x29)
    data[:3] = b"\x00\x04\x45"
    data[0x06:0x08] = width.to_bytes(2, "little")
    data[0x08:0x0A] = height.to_bytes(2, "little")
    data[0x0E:0x10] = width.to_bytes(2, "little")
    data[0x10:0x12] = height.to_bytes(2, "little")
    data[0x12] = kind
    data[0x13] = depth
    data[0x14:0x16] = header_version.to_bytes(2, "little")
    data[0x16] = flags
    data[0x17:0x1A] = b"\x08\x08\x08"
    data[0x1D:0x21] = payload_length.to_bytes(4, "little")
    return bytes(data)


class DecodeImageRecordTests(unittest.TestCase):
    def make_source(self, root: Path) -> Path:
        width, height = 2, 1
        native = bytes((20, 30, 10, 0x80, 50, 60, 40, 0x80))
        payload, _ = encode_native_pixels(
            native,
            width=width,
            height=height,
            x_offset=0,
            y_offset=0,
            draw_width=width,
            draw_height=height,
        )
        record = crip008_header(width, height, len(payload)) + payload
        source = root / "sample.rio"
        source.write_bytes(b"prefix" + record + b"tail")
        return source

    def test_exact_extent_decodes_to_portable_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source(root)
            extent = source.stat().st_size - len(b"prefix") - len(b"tail")
            png, report = build_outputs(source, len(b"prefix"), extent, "crip008", "review.png")
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(report["source_file"], "sample.rio")
        self.assertNotIn(str(root), json.dumps(report))
        self.assertFalse(report["input_modified"])

    def test_declared_length_mismatch_and_out_of_range_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source(root)
            extent = source.stat().st_size - len(b"prefix") - len(b"tail")
            with self.assertRaisesRegex(ImageExtractError, "declared record length"):
                build_outputs(source, len(b"prefix"), extent + len(b"tail"), "crip008", "x.png")
            with self.assertRaisesRegex(ImageExtractError, "outside"):
                build_outputs(source, source.stat().st_size, 1, "crip008", "x.png")

    def test_zero_and_truncated_payloads_fail_instead_of_zero_filling(self) -> None:
        for kind, depth in ((2, 6), (3, 3)):
            with self.subTest(kind=kind):
                empty = crip008_header(2, 2, 0, kind=kind, depth=depth)
                with self.assertRaisesRegex(ValueError, "payload length must be positive"):
                    decode_record(empty, "crip008")

        valid_header = crip008_header(4, 1, 1, kind=2, depth=6)
        with self.assertRaisesRegex(ValueError, "payload ended while decoding"):
            decode_record(valid_header + b"\x00", "crip008")

    def test_profile_and_pixel_safety_gates_run_before_allocation(self) -> None:
        oversized = crip008_header(65535, 65535, 1, kind=2, depth=6) + b"\x00"
        with self.assertRaisesRegex(ValueError, "safety limit"):
            decode_record(oversized, "crip008")

        unknown_flags = crip008_header(2, 1, 1, flags=0x80) + b"\x00"
        with self.assertRaisesRegex(ValueError, "compression flags"):
            decode_record(unknown_flags, "crip008")

        unknown_version = (
            crip008_header(2, 1, 1, header_version=2) + b"\x00"
        )
        with self.assertRaisesRegex(ValueError, "header version"):
            decode_record(unknown_version, "crip008")

    def test_trailing_payload_and_nonzero_padding_are_rejected(self) -> None:
        width, height = 2, 1
        native = bytes((20, 30, 10, 0x80, 50, 60, 40, 0x80))
        payload, bit_count = encode_native_pixels(
            native,
            width=width,
            height=height,
            x_offset=0,
            y_offset=0,
            draw_width=width,
            draw_height=height,
        )
        appended = crip008_header(width, height, len(payload) + 1) + payload + b"\x00"
        with self.assertRaisesRegex(ValueError, "excess .* padding"):
            decode_record(appended, "crip008")

        self.assertGreater(len(payload) * 8 - bit_count, 0)
        polluted = bytearray(payload)
        polluted[-1] |= 1
        record = crip008_header(width, height, len(polluted)) + bytes(polluted)
        with self.assertRaisesRegex(ValueError, "padding contains a set bit"):
            decode_record(record, "crip008")

    def test_publication_is_atomic_create_only_and_rejects_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.make_source(root)
            extent = source.stat().st_size - len(b"prefix") - len(b"tail")
            png, report = build_outputs(source, len(b"prefix"), extent, "crip008", "review.png")
            output = root / "review.png"
            report_path = root / "review.json"
            before = source.read_bytes()
            write_new_outputs(source, output, png, report_path, report)
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(output.is_file())
            self.assertTrue(report_path.is_file())
            with self.assertRaisesRegex(ImageExtractError, "overwrite"):
                write_new_outputs(source, output, png, report_path, report)
            alias = root / "source-hardlink.rio"
            os.link(source, alias)
            with self.assertRaisesRegex(ImageExtractError, "alias"):
                write_new_outputs(source, alias, png, root / "other.json", report)


if __name__ == "__main__":
    unittest.main()
