from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from localization.tools.font_coverage import (
    CoverageError,
    audit,
    font_codepoints,
    main,
    read_table,
    visible_codepoints,
)


class FontCoverageTests(unittest.TestCase):
    def test_engine_controls_and_format_characters_are_not_visible_glyphs(self) -> None:
        self.assertEqual(
            visible_codepoints("中文<03>\\w\u2060A"),
            {ord("中"), ord("文"), ord("A")},
        )

    def test_table_requires_an_explicit_or_known_translation_column(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "source.csv"
            path.write_text("id,source\n1,日本語\n", encoding="utf-8")
            with self.assertRaisesRegex(CoverageError, "pass --column"):
                read_table(path, [])

    def test_audit_reports_missing_codepoints_without_rewriting_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            font = root / "test.ttf"
            font.write_bytes(b"synthetic-font")
            table = root / "translation.csv"
            with table.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=("id", "translated_text"))
                writer.writeheader()
                writer.writerow({"id": "1", "translated_text": "中文A<01>"})
            with mock.patch(
                "localization.tools.font_coverage.font_codepoints",
                return_value={ord("中"), ord("A")},
            ):
                report = audit(font, [table], [])

        self.assertEqual(report["status"], "FAIL")
        self.assertEqual(
            report["missing"],
            [{"codepoint": "U+6587", "character": "文", "name": "CJK UNIFIED IDEOGRAPH-6587"}],
        )
        self.assertEqual(report["tables"][0]["columns"], ["translated_text"])
        self.assertEqual(report["tables"][0]["file"], "translation.csv")

    def test_collection_never_unions_faces_implicitly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            collection_path = Path(temporary) / "collection.ttc"
            collection_path.write_bytes(b"synthetic")
            fake_collection = mock.Mock()
            fake_collection.fonts = [mock.Mock(), mock.Mock()]
            with mock.patch(
                "fontTools.ttLib.TTCollection", return_value=fake_collection
            ):
                with self.assertRaisesRegex(CoverageError, "explicit --face-index"):
                    font_codepoints(collection_path)
                with self.assertRaisesRegex(CoverageError, "outside 0..1"):
                    font_codepoints(collection_path, 2)
            self.assertEqual(fake_collection.close.call_count, 2)

    def test_cli_refuses_to_overwrite_a_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            font = root / "test.ttf"
            font.write_bytes(b"synthetic-font")
            table = root / "translation.csv"
            table.write_text("id,translated_text\n1,中文\n", encoding="utf-8")
            report_path = root / "report.json"
            report_path.write_text("reviewed", encoding="utf-8")
            with mock.patch(
                "localization.tools.font_coverage.font_codepoints",
                return_value={ord("中"), ord("文")},
            ):
                with self.assertRaisesRegex(FileExistsError, "already exists"):
                    main(
                        [
                            str(font),
                            str(table),
                            "--output",
                            str(report_path),
                        ]
                    )
            self.assertEqual(report_path.read_text(encoding="utf-8"), "reviewed")


if __name__ == "__main__":
    unittest.main()
