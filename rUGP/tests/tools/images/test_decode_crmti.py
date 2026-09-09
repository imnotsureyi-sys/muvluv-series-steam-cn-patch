from contextlib import redirect_stdout
import hashlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from rUGP.tests.formats.images.test_crmti_record import fixture
from rUGP.tools.images.decode_crmti import build_outputs, main


class DecodeStandaloneToolTests(unittest.TestCase):
    def test_full_dimensions_alpha_and_portable_hash_report(self):
        raw, expected = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "test.rio"
            source.write_bytes(b"prefix" + raw + b"tail")
            png, report = build_outputs(source, 6, len(raw), "review.png")
            self.assertNotIn(temporary, json.dumps(report))
        with Image.open(BytesIO(png)) as image:
            self.assertEqual((image.mode, image.size), ("RGBA", (5, 3)))
            self.assertEqual(image.tobytes(), expected)
        self.assertEqual(report["record_sha256"], hashlib.sha256(raw).hexdigest().upper())
        self.assertEqual(report["rgba_sha256"], hashlib.sha256(expected).hexdigest().upper())
        self.assertTrue(report["standalone_not_inline_child"])
        self.assertFalse(report["runtime_acceptance"])
        self.assertFalse(report["language_pair_inferred"])
        self.assertFalse(report["input_modified"])

    def test_cli_create_only_and_source_unchanged(self):
        raw, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / "test.rio", root / "review.png"
            source.write_bytes(raw)
            args = ["--source", str(source), "--offset", "0", "--extent", str(len(raw)), "--output", str(output)]
            with redirect_stdout(StringIO()):
                self.assertEqual(main(args), 0)
            png_before = output.read_bytes()
            report_path = output.with_suffix(".png.json")
            report_before = report_path.read_bytes()
            with redirect_stdout(StringIO()):
                self.assertEqual(main(args), 1)
            self.assertEqual(output.read_bytes(), png_before)
            self.assertEqual(report_path.read_bytes(), report_before)
            self.assertEqual(source.read_bytes(), raw)

    def test_cli_input_alias_refused(self):
        raw, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "test.rio"
            source.write_bytes(raw)
            with redirect_stdout(StringIO()):
                code = main(["--source", str(source), "--offset", "0", "--extent", str(len(raw)), "--output", str(source)])
            self.assertEqual(code, 1)
            self.assertEqual(source.read_bytes(), raw)
            self.assertFalse(source.with_suffix(".rio.json").exists())

    def test_unsupported_frame_has_no_outputs(self):
        raw, _ = fixture()
        for data in (b"\0\4" + raw[2:], raw[:-1], raw + b"\0"):
            with tempfile.TemporaryDirectory() as temporary:
                source, output = Path(temporary) / "test.rio", Path(temporary) / "out.png"
                source.write_bytes(data)
                with redirect_stdout(StringIO()):
                    self.assertEqual(main(["--source", str(source), "--offset", "0", "--extent", str(len(data)), "--output", str(output)]), 1)
                self.assertFalse(output.exists())
                self.assertFalse(output.with_suffix(".png.json").exists())

    def test_outside_extent_refused(self):
        raw, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "test.rio"
            source.write_bytes(raw)
            for offset, extent in ((-1, len(raw)), (0, 0), (1, len(raw))):
                with self.subTest(offset=offset, extent=extent), self.assertRaises(RuntimeError):
                    build_outputs(source, offset, extent, "x.png")


if __name__ == "__main__":
    unittest.main()
