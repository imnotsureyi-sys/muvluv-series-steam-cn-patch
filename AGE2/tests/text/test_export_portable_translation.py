from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from AGE2.tools.text.export_portable_translation import (
    ExportError,
    portable_bytes,
    write_new_export,
)


class PortableAge2TranslationTests(unittest.TestCase):
    def test_replaces_official_text_with_utf8_hash_and_preserves_other_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.csv"
            with source.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=(
                        "call_order",
                        "id",
                        "egpack",
                        "scene",
                        "speaker_jp",
                        "jp_text",
                        "cn_text",
                    ),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "call_order": "1",
                        "id": "game_t00001",
                        "egpack": "scene.egpack",
                        "scene": "scene-1",
                        "speaker_jp": "人物",
                        "jp_text": "公式原文\\p",
                        "cn_text": "公开译文\\p",
                    }
                )
            payload, report = portable_bytes(source)

        decoded = payload.decode("utf-8-sig")
        rows = list(csv.DictReader(decoded.splitlines()))
        self.assertNotIn("jp_text", rows[0])
        self.assertEqual(rows[0]["record_kind"], "text")
        self.assertEqual(
            rows[0]["source_text_sha256"],
            hashlib.sha256("公式原文\\p".encode("utf-8")).hexdigest().upper(),
        )
        self.assertEqual(rows[0]["cn_text"], "公开译文\\p")
        self.assertFalse(report["bulk_official_dialogue_included"])
        self.assertEqual(report["removed_source_columns"], ["jp_text"])
        self.assertEqual(report["retained_limited_source_context"], ["speaker_jp"])
        self.assertEqual(report["record_kinds"], {"text": 1, "structural_empty": 0})

    def test_explicitly_labels_a_fully_empty_structural_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.csv"
            source.write_text(
                "call_order,id,egpack,scene,speaker_jp,jp_text,cn_text\n"
                "1,x,a.egpack,s,,,\n",
                encoding="utf-8",
            )
            payload, report = portable_bytes(source)
        row = next(csv.DictReader(payload.decode("utf-8-sig").splitlines()))
        self.assertEqual(row["record_kind"], "structural_empty")
        self.assertEqual(
            row["source_text_sha256"], hashlib.sha256(b"").hexdigest().upper()
        )
        self.assertEqual(report["record_kinds"], {"text": 0, "structural_empty": 1})

    def test_rejects_ambiguous_empty_source_or_target(self) -> None:
        cases = (
            ("人物", "", "", "fully empty structural slot"),
            ("", "", "unexpected target", "fully empty structural slot"),
            ("", "source", "", "empty localized value"),
        )
        for speaker, source_text, target, message in cases:
            with self.subTest(speaker=speaker, source=source_text, target=target):
                with tempfile.TemporaryDirectory() as temporary:
                    source = Path(temporary) / "source.csv"
                    with source.open("w", encoding="utf-8", newline="") as stream:
                        writer = csv.writer(stream)
                        writer.writerow(
                            ("call_order", "id", "egpack", "scene", "speaker_jp", "jp_text", "cn_text")
                        )
                        writer.writerow(("1", "x", "a.egpack", "s", speaker, source_text, target))
                    with self.assertRaisesRegex(ExportError, message):
                        portable_bytes(source)

    def test_duplicate_resource_identity_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.csv"
            source.write_text(
                "call_order,id,egpack,scene,speaker_jp,jp_text,cn_text\n"
                "1,x,a.egpack,s,人物,一,甲\n"
                "2,x,a.egpack,s,人物,二,乙\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ExportError, "duplicate identity"):
                portable_bytes(source)

    def test_rejects_unknown_columns_instead_of_leaking_another_source_field(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "source.csv"
            source.write_text(
                "call_order,id,egpack,scene,speaker_jp,jp_text,cn_text,source_text\n"
                "1,x,a.egpack,a,人物,原文,译文,不应公开的另一列\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ExportError, "reviewed AGE2 schema"):
                portable_bytes(source)

    def test_refuses_input_alias_duplicate_outputs_and_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.csv"
            source.write_text(
                "call_order,id,egpack,scene,speaker_jp,jp_text,cn_text\n"
                "1,x,a.egpack,s,人物,原文,译文\n",
                encoding="utf-8",
            )
            payload, report = portable_bytes(source)
            with self.assertRaisesRegex(ExportError, "must not alias"):
                write_new_export(source, source, payload, None, report)
            same = root / "same.out"
            with self.assertRaisesRegex(ExportError, "different files"):
                write_new_export(source, same, payload, same, report)
            occupied = root / "portable.csv"
            occupied.write_text("reviewed", encoding="utf-8")
            with self.assertRaisesRegex(ExportError, "refusing to overwrite"):
                write_new_export(source, occupied, payload, None, report)
            self.assertEqual(occupied.read_text(encoding="utf-8"), "reviewed")

    def test_publishes_complete_table_and_report_without_temporary_residue(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.csv"
            source.write_text(
                "call_order,id,egpack,scene,speaker_jp,jp_text,cn_text\n"
                "1,x,a.egpack,s,人物,source,target\n",
                encoding="utf-8",
            )
            payload, report = portable_bytes(source)
            output = root / "portable.csv"
            report_path = root / "portable.json"
            write_new_export(source, output, payload, report_path, report)
            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual(
                json.loads(report_path.read_text(encoding="utf-8")), report
            )
            self.assertFalse(any(path.suffix == ".tmp" for path in root.iterdir()))


if __name__ == "__main__":
    unittest.main()
