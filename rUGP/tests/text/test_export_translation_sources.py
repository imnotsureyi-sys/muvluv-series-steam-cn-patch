from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from rUGP.tools.text.export_translation_sources import PUBLIC_COLUMNS, ExportError, run


PRIVATE_COLUMNS = [
    "game",
    "stable_id",
    "rio_file",
    "block_offset",
    "payload_offset",
    "text_offset",
    "writer_mode",
    "delimiter",
    "field_sha256",
    "full_cstring_identity_sha256",
    "final_cn_text",
    "writer_replacement_text",
    "writer_inline_controls",
    "allow_control_change",
    "control_delta_reason",
    "production_runtime_binding",
    "production_native_capacity_units",
    "production_replacement_units",
    "production_padding_codepoint",
    "production_padding_units",
    "translation_source",
    "native_field_text",
]


def row(game: str, stable_id: str, *, desired: str, runtime: str) -> dict[str, str]:
    return {
        "game": game,
        "stable_id": stable_id,
        "rio_file": f"{game}.rio",
        "block_offset": "100",
        "payload_offset": "20",
        "text_offset": "8",
        "writer_mode": "whole_visible",
        "delimiter": "",
        "field_sha256": "A" * 64,
        "full_cstring_identity_sha256": "B" * 64,
        "final_cn_text": desired,
        "writer_replacement_text": runtime,
        "writer_inline_controls": "\\p",
        "allow_control_change": "False",
        "control_delta_reason": "",
        "production_runtime_binding": "direct_top_level",
        "production_native_capacity_units": "20",
        "production_replacement_units": "10",
        "production_padding_codepoint": "U+2060",
        "production_padding_units": "10",
        "translation_source": "reviewed_translation",
        "native_field_text": "公式原文を公開しない",
    }


class PortableTranslationExportTests(unittest.TestCase):
    def write_private(self, path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=PRIVATE_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_exports_only_portable_fields_and_preserves_runtime_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "private.csv"
            self.write_private(
                source,
                [
                    row("pf", "pf:1", desired="中文一\n第二行", runtime="中文一\n第二行"),
                    row("pm", "pm:1", desired="返回标题菜单", runtime="返回标题菜单\u2060"),
                ],
            )
            games = root / "games"
            manifest = root / "evidence" / "manifest.json"
            source_hash = hashlib.sha256(source.read_bytes()).hexdigest().upper()

            result = run(
                source,
                games,
                manifest,
                source_label="sealed-input-v1",
                expected_source_sha256=source_hash,
                check=False,
            )

            self.assertEqual(result["status"], "PASS")
            pm_path = games / "photonmelodies" / "translations" / "zh-Hans.csv"
            with pm_path.open("r", encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(tuple(rows[0]), PUBLIC_COLUMNS)
            self.assertEqual(rows[0]["translation_text"], "返回标题菜单")
            self.assertEqual(rows[0]["runtime_text"], "返回标题菜单\u2060")
            self.assertNotIn("native_field_text", rows[0])
            document = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertFalse(document["official_source_text_included"])
            self.assertEqual(document["games"]["photonflowers"]["rows"], 1)
            self.assertEqual(document["games"]["photonmelodies"]["rows"], 1)
            self.assertNotIn(str(root), manifest.read_text(encoding="utf-8"))

            checked = run(
                source,
                games,
                manifest,
                source_label="sealed-input-v1",
                expected_source_sha256=source_hash,
                check=True,
            )
            self.assertEqual(checked["mode"], "check")

    def test_rejects_duplicate_identity_and_source_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "private.csv"
            duplicate = row("pf", "duplicate", desired="甲", runtime="甲")
            self.write_private(source, [duplicate, duplicate, row("pm", "pm:1", desired="乙", runtime="乙")])
            with self.assertRaisesRegex(ExportError, "duplicate stable_id"):
                run(
                    source,
                    root / "games",
                    root / "manifest.json",
                    source_label="sealed-input-v1",
                    expected_source_sha256=None,
                    check=False,
                )

            self.write_private(source, [row("pf", "pf:1", desired="甲", runtime="甲"), row("pm", "pm:1", desired="乙", runtime="乙")])
            with self.assertRaisesRegex(ExportError, "hash mismatch"):
                run(
                    source,
                    root / "games",
                    root / "manifest.json",
                    source_label="sealed-input-v1",
                    expected_source_sha256="0" * 64,
                    check=False,
                )


if __name__ == "__main__":
    unittest.main()
