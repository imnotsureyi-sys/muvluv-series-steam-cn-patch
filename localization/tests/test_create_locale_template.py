from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from localization.tools.create_locale_template import TemplateError, run


SOURCE_COLUMNS = (
    "call_order",
    "stable_id",
    "rio_file",
    "scene",
    "source_text_sha256",
    "translated_text",
)


def row(order: int, *, identity: str | None = None, source_hash: str | None = None) -> dict[str, str]:
    return {
        "call_order": str(order),
        "stable_id": identity or f"pf:static:test.rio:100:{order:08d}",
        "rio_file": "test.rio",
        "scene": "crsa:test.rio@100",
        "source_text_sha256": source_hash if source_hash is not None else f"{order:X}" * 64,
        "translated_text": f"第{order}行中文<01>",
    }


class LocaleTemplateTests(unittest.TestCase):
    def write_table(
        self,
        path: Path,
        rows: list[dict[str, str]],
        *,
        columns: tuple[str, ...] = SOURCE_COLUMNS,
        delimiter: str = ",",
    ) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(
                stream,
                fieldnames=columns,
                delimiter=delimiter,
                lineterminator="\n",
            )
            writer.writeheader()
            writer.writerows(rows)

    def test_csv_output_is_blank_redacted_manifest_bound_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            results: list[tuple[bytes, bytes]] = []
            for folder in (root / "one", root / "two"):
                folder.mkdir()
                source = folder / "reviewed.csv"
                output = folder / "ru-template.csv"
                self.write_table(source, [row(1), row(2)])
                report = run(
                    source,
                    output,
                    target_locale="RU",
                    identity_column="stable_id",
                    source_hash_column="source_text_sha256",
                    text_column="translated_text",
                    keep_columns=("call_order", "rio_file", "scene"),
                )
                manifest_path = folder / "ru-template.csv.manifest.json"
                results.append((output.read_bytes(), manifest_path.read_bytes()))

                self.assertEqual(report["status"], "PASS")
                self.assertEqual(report["target_locale"], "ru")
                with output.open("r", encoding="utf-8", newline="") as stream:
                    reader = csv.DictReader(stream)
                    self.assertEqual(
                        reader.fieldnames,
                        [
                            "call_order",
                            "stable_id",
                            "rio_file",
                            "scene",
                            "source_text_sha256",
                            "target_locale",
                            "target_text",
                        ],
                    )
                    output_rows = list(reader)
                self.assertEqual([item["target_locale"] for item in output_rows], ["ru", "ru"])
                self.assertEqual([item["target_text"] for item in output_rows], ["", ""])
                serialized = output.read_text(encoding="utf-8")
                self.assertNotIn("translated_text", serialized)
                self.assertNotIn("中文", serialized)

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "working_template_not_writer_input")
                self.assertFalse(manifest["safeguards"]["existing_translation_included"])
                self.assertFalse(manifest["safeguards"]["official_source_text_included"])
                self.assertEqual(manifest["output"]["sha256"], hashlib.sha256(output.read_bytes()).hexdigest().upper())
                self.assertNotIn(str(folder), manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(results[0], results[1])

    def test_tsv_input_and_output_use_explicit_schema_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.tsv"
            output = root / "ko.tsv"
            columns = ("record", "context", "field_hash", "cn_text")
            rows = [
                {
                    "record": "asset:1",
                    "context": "menu/start",
                    "field_hash": "A" * 64,
                    "cn_text": "开始",
                }
            ]
            self.write_table(source, rows, columns=columns, delimiter="\t")
            run(
                source,
                output,
                target_locale="ko",
                identity_column="record",
                source_hash_column="field_hash",
                text_column="cn_text",
                keep_columns=("context",),
            )
            with output.open("r", encoding="utf-8", newline="") as stream:
                public = list(csv.DictReader(stream, delimiter="\t"))
            self.assertEqual(
                list(public[0]),
                ["record", "context", "field_hash", "target_locale", "target_text"],
            )
            self.assertEqual(public[0]["target_locale"], "ko")
            self.assertEqual(public[0]["target_text"], "")

    def test_fail_closed_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def attempt(
                name: str,
                rows: list[dict[str, str]],
                *,
                locale: str = "ru",
                source_hash_column: str = "source_text_sha256",
                keep_columns: tuple[str, ...] = ("scene",),
                columns: tuple[str, ...] = SOURCE_COLUMNS,
            ) -> None:
                source = root / f"{name}.csv"
                output = root / f"{name}-out.csv"
                self.write_table(source, rows, columns=columns)
                run(
                    source,
                    output,
                    target_locale=locale,
                    identity_column="stable_id",
                    source_hash_column=source_hash_column,
                    text_column="translated_text",
                    keep_columns=keep_columns,
                )

            cases = (
                ("duplicate identity", [row(1), row(2, identity=row(1)["stable_id"])], {}, "duplicate stable identity"),
                ("empty source hash", [row(1, source_hash="")], {}, "invalid SHA-256"),
                ("missing hash column", [row(1)], {"source_hash_column": "not_present"}, "missing explicitly requested"),
                ("existing locale", [row(1)], {"locale": "zh-Hans"}, "existing zh-Hans"),
                ("ambiguous existing locale", [row(1)], {"locale": "zh"}, "existing zh-Hans"),
                ("existing locale alias", [row(1)], {"locale": "zh-CN"}, "existing zh-Hans"),
                ("unsafe kept text", [row(1)], {"keep_columns": ("translated_text",)}, "refusing text-like"),
            )
            for name, rows, options, message in cases:
                with self.subTest(name=name):
                    with self.assertRaisesRegex(TemplateError, message):
                        attempt(name, rows, **options)

            source = root / "exists.csv"
            output = root / "exists-out.csv"
            self.write_table(source, [row(1)])
            output.write_text("do not replace", encoding="utf-8")
            with self.assertRaisesRegex(TemplateError, "refusing to overwrite"):
                run(
                    source,
                    output,
                    target_locale="ru",
                    identity_column="stable_id",
                    source_hash_column="source_text_sha256",
                    text_column="translated_text",
                )
            self.assertEqual(output.read_text(encoding="utf-8"), "do not replace")

            output = root / "manifest-exists-out.csv"
            manifest = root / "manifest-exists-out.csv.manifest.json"
            manifest.write_text("do not replace", encoding="utf-8")
            with self.assertRaisesRegex(TemplateError, "refusing to overwrite"):
                run(
                    source,
                    output,
                    target_locale="ko",
                    identity_column="stable_id",
                    source_hash_column="source_text_sha256",
                    text_column="translated_text",
                )
            self.assertFalse(output.exists())
            self.assertEqual(manifest.read_text(encoding="utf-8"), "do not replace")


if __name__ == "__main__":
    unittest.main()
