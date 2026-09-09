from __future__ import annotations

from contextlib import redirect_stdout
import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from rUGP.formats.images.crmti_decode import CRMT_CHILD_WRAPPER, decode_crmt
from rUGP.tools.images.replace_crmt import build_replacement, main


def template(width: int, height: int, meta: int = 0x0707070F) -> bytes:
    parent = bytearray(0x41)
    parent[:4] = bytes.fromhex("80 04 02 05")
    parent[0x40] = 1
    header = bytearray(18)
    header[0:2] = width.to_bytes(2, "little")
    header[2:4] = height.to_bytes(2, "little")
    header[4:8] = meta.to_bytes(4, "little")
    header[8:12] = (2).to_bytes(4, "little")
    header[12:16] = (width * height * 4).to_bytes(4, "little")
    return bytes(parent) + CRMT_CHILD_WRAPPER + bytes(header) + b"\0\0TRAILER"


class ReplaceCrmtTests(unittest.TestCase):
    def test_builds_all_mips_and_leaves_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            record = template(8, 4)
            source_bytes = b"PREFIX" + record + b"SUFFIX"
            source = root / "volume.rio"
            source.write_bytes(source_bytes)
            top = Image.new("RGBA", (8, 4), (0, 0, 0, 0))
            for x in range(2, 7):
                top.putpixel((x, 2), (230, 80, 20, 255))
            top_path = root / "localized.png"
            top.save(top_path)

            replacement, report = build_replacement(
                source=source,
                offset=6,
                extent=len(record),
                top_png=top_path,
                output_name="replacement.crmt",
            )
            decoded, trailer = decode_crmt(replacement)
            self.assertEqual((decoded[0].level.width, decoded[0].level.height), (8, 4))
            self.assertEqual(trailer, b"TRAILER")
            self.assertEqual(source.read_bytes(), source_bytes)
            self.assertTrue(report["all_levels_read_back_as_expected"])
            self.assertFalse(report["input_modified"])

    def test_cli_is_create_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            record = template(3, 2)
            source = root / "one.crmt"
            source.write_bytes(record)
            top_path = root / "top.png"
            Image.new("RGBA", (3, 2), (50, 100, 150, 255)).save(top_path)
            output = root / "replacement.crmt"
            arguments = [
                "--source",
                str(source),
                "--offset",
                "0",
                "--extent",
                str(len(record)),
                "--top-png",
                str(top_path),
                "--output",
                str(output),
            ]
            with redirect_stdout(io.StringIO()):
                first_status = main(arguments)
            self.assertEqual(first_status, 0)
            first = output.read_bytes()
            with redirect_stdout(io.StringIO()):
                second_status = main(arguments)
            self.assertEqual(second_status, 1)
            self.assertEqual(output.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
