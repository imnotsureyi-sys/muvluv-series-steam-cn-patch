from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.egpack.extract_egpack_manifest import MANIFEST_COLUMNS, main, manifest_rows

from .fixtures import build_egpack


class EgpackManifestTests(unittest.TestCase):
    def test_manifest_outputs_every_slot_including_empty_and_control_only(self) -> None:
        data = build_egpack(
            [
                {"id": "game_t00000", "jp": "「日本語」\\p", "en": "English"},
                {"id": "game_t00001", "jp": "\\f", "en": ""},
            ]
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "nested" / "scene.egpack"
            source.parent.mkdir()
            source.write_bytes(data)

            rows = list(manifest_rows(root))

        self.assertEqual(len(rows), 20)
        self.assertEqual({row["relative_path"] for row in rows}, {"nested/scene.egpack"})
        self.assertEqual({row["record_index"] for row in rows}, {0, 1})
        self.assertEqual(len([row for row in rows if row["id"] == "game_t00000"]), 10)
        self.assertEqual(len([row for row in rows if row["id"] == "game_t00001"]), 10)

        control = next(row for row in rows if row["id"] == "game_t00001" and row["slot"] == "jp")
        empty = next(row for row in rows if row["id"] == "game_t00001" and row["slot"] == "en")
        self.assertEqual(control["text"], "\\f")
        self.assertFalse(control["is_empty"])
        self.assertTrue(control["is_control_only"])
        self.assertEqual(control["control_codes"], "\\f")
        self.assertEqual(empty["text"], "")
        self.assertTrue(empty["is_empty"])
        self.assertFalse(empty["is_control_only"])

    def test_manifest_offsets_and_hash_match_original_value_bytes(self) -> None:
        data = build_egpack([{"id": "game_t00000", "jp": "日本語", "en": "English"}])
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "scene.egpack"
            source.write_bytes(data)

            row = next(
                row for row in manifest_rows(source)
                if row["id"] == "game_t00000" and row["slot"] == "jp"
            )

        start = int(row["value_offset"])
        length = int(row["value_length"])
        raw = data[start : start + length]
        self.assertEqual(raw, "日本語".encode("utf-8"))
        self.assertEqual(row["value_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(row["file_size"], len(data))
        self.assertEqual(row["declared_size"], len(data))

    def test_cli_writes_utf8_bom_csv_with_approved_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "scene.egpack"
            output = root / "manifest.csv"
            source.write_bytes(build_egpack([{"id": "game_t00000", "jp": "日本語"}]))

            result = main([str(source), "--output", str(output)])

            self.assertEqual(result, 0)
            self.assertTrue(output.read_bytes().startswith(b"\xef\xbb\xbf"))
            with output.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0].keys(), dict.fromkeys(MANIFEST_COLUMNS).keys())
            self.assertEqual(len(rows), 10)


if __name__ == "__main__":
    unittest.main()
