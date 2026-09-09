from contextlib import redirect_stdout
from io import StringIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rUGP.tests.formats.images.test_crmti_codec import template
from rUGP.formats.images.crmti_encode import encode_crmt
from rUGP.tools.images.export_crmt_layers import export_layers, main


class ExportLayersTests(unittest.TestCase):
    def test_exact_pixels_and_create_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "sample.rio"
            first = template(5, 3, 0x0707070F)
            second = template(3, 2, 0x0707070F)
            parent = bytearray(first[:0x41]); parent[0x40] = 2
            two_layers = bytes(parent) + first[0x41:-6] + second[0x41:]
            raw, expected, _ = encode_crmt(two_layers, [bytes((10, 50, 80, 255)) * 15, bytes((20, 40, 60, 255)) * 6])
            source.write_bytes(b"prefix" + raw + b"tail")
            digest = hashlib.sha256(raw).hexdigest().upper()
            result = export_layers(source, 6, len(raw), digest, root / "layers")
            self.assertEqual([(p["width"], p["height"]) for p in result["levels"]], [(5, 3), (3, 2)])
            self.assertEqual(len(list((root / "layers").glob("*.png"))), 2)
            self.assertEqual(result["levels"][0]["rgba_sha256"], hashlib.sha256(expected[0]).hexdigest().upper())
            self.assertFalse(result["external_image_fetched"])
            self.assertEqual(source.read_bytes(), b"prefix" + raw + b"tail")
            self.assertNotIn(temp, json.dumps(result))
            with self.assertRaisesRegex(ValueError, "must be new"):
                export_layers(source, 6, len(raw), digest, root / "layers")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                export_layers(source, 6, len(raw), "0" * 64, root / "bad")
            self.assertFalse((root / "bad").exists())

    def test_cli_unknown_record_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / "sample.rio"; source.write_bytes(b"bad")
            with redirect_stdout(StringIO()):
                status = main(["--source", str(source), "--offset", "0", "--extent", "3",
                               "--sha256", hashlib.sha256(b"bad").hexdigest(), "--output-dir", str(root / "out")])
            self.assertEqual(status, 1)
            self.assertFalse((root / "out").exists())
