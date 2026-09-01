from __future__ import annotations

import csv
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from rugp.tools.text.export_reviewed_translation import (
    PUBLIC_COLUMNS,
    SOURCE_COLUMNS,
    ExportError,
    read_git_blob,
    run,
)


def source_row(
    order: int,
    *,
    stable_id: str | None = None,
    rio_file: str = "photonflowers11.rio",
    scene: str = "crsa:photonflowers11.rio@1234",
    speaker: str = "武",
    source: str = "【武】「テスト」<01>",
    translation: str = "【武】「测试」<01>",
) -> dict[str, str]:
    return {
        "call_order": str(order),
        "id": stable_id or f"pf:static:{rio_file}:0000001234:{order:08d}",
        "rio_file": rio_file,
        "scene": scene,
        "speaker_jp": speaker,
        "jp_text": source,
        "cn_text": translation,
    }


class ReviewedTranslationExportTests(unittest.TestCase):
    def test_git_blob_reader_is_binary_safe_and_never_uses_a_shell(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            payload = b"\xef\xbb\xbfraw\r\nbytes\x00"
            completed = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=payload, stderr=b""
            )
            with mock.patch(
                "rugp.tools.text.export_reviewed_translation.subprocess.run",
                return_value=completed,
            ) as invoked:
                self.assertEqual(read_git_blob("git:" + "a" * 40, repository), payload)
            args, kwargs = invoked.call_args
            self.assertEqual(args[0], ["git", "cat-file", "blob", "a" * 40])
            self.assertEqual(kwargs["cwd"], repository.resolve())
            self.assertNotIn("shell", kwargs)

            with self.assertRaisesRegex(ExportError, "40-hex"):
                read_git_blob("git:not-an-object", repository)

    def write_source(
        self,
        path: Path,
        rows: list[dict[str, str]],
        *,
        columns: tuple[str, ...] = SOURCE_COLUMNS,
    ) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def test_redacts_source_fields_and_hashes_exact_parsed_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "full.csv"
            output = root / "public.csv"
            japanese = "【武】「一行目\r\n二行目」<01>"
            rows = [
                source_row(1, source=japanese, translation="【武】「第一行\r\n第二行」<01>"),
                source_row(
                    2,
                    speaker="",
                    source="地の文<03>です。<01>",
                    translation="这是旁白。<01>",
                ),
            ]
            self.write_source(source, rows)
            source_digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()

            report = run(
                source,
                output,
                expected_source_sha256=source_digest,
                expected_id_prefix="pf",
                expected_rows=2,
            )

            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["records"], 2)
            with output.open("r", encoding="utf-8", newline="") as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(tuple(reader.fieldnames or ()), PUBLIC_COLUMNS)
                public = list(reader)
            self.assertEqual(public[0]["stable_id"], rows[0]["id"])
            self.assertEqual(public[0]["translated_text"], rows[0]["cn_text"])
            self.assertEqual(
                public[0]["source_text_sha256"],
                hashlib.sha256(japanese.encode("utf-8")).hexdigest().upper(),
            )
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("speaker_jp", serialized)
            self.assertNotIn("jp_text", serialized)
            self.assertNotIn(japanese, serialized)

            checked = run(
                source,
                output,
                expected_source_sha256=source_digest.lower(),
                expected_id_prefix="pf",
                expected_rows=2,
                check=True,
            )
            self.assertEqual(checked["mode"], "check")
            output.write_bytes(output.read_bytes() + b"\n")
            with self.assertRaisesRegex(ExportError, "missing or stale"):
                run(source, output, expected_id_prefix="pf", check=True)

    def test_rejects_header_identity_order_and_content_drift(self) -> None:
        mutations = {
            "wrong header": (
                list(reversed(SOURCE_COLUMNS)),
                [source_row(1)],
                "header must be exactly",
            ),
            "gapped call order": (
                list(SOURCE_COLUMNS),
                [source_row(2)],
                "call_order must be contiguous",
            ),
            "duplicate identity": (
                list(SOURCE_COLUMNS),
                [source_row(1), source_row(2, stable_id=source_row(1)["id"])],
                "duplicate stable identity",
            ),
            "rio mismatch": (
                list(SOURCE_COLUMNS),
                [
                    source_row(
                        1,
                        stable_id="pf:static:photonflowers11.rio:0000001234:00000001",
                        rio_file="photonflowers11.rio.002",
                        scene="crsa:photonflowers11.rio.002@1234",
                    )
                ],
                "does not match rio_file",
            ),
            "scene mismatch": (
                list(SOURCE_COLUMNS),
                [source_row(1, scene="crsa:photonflowers11.rio@999")],
                "does not match identity",
            ),
            "empty translation": (
                list(SOURCE_COLUMNS),
                [source_row(1, translation="")],
                "empty required field cn_text",
            ),
            "embedded nul": (
                list(SOURCE_COLUMNS),
                [source_row(1, speaker="武\x00")],
                r"embedded U\+0000",
            ),
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name, (columns, rows, message) in mutations.items():
                with self.subTest(name=name):
                    source = root / f"{name}.csv"
                    output = root / f"{name}.public.csv"
                    self.write_source(source, rows, columns=tuple(columns))
                    with self.assertRaisesRegex(ExportError, message):
                        run(source, output, expected_id_prefix="pf")

    def test_rejects_source_hash_prefix_and_record_count_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "full.csv"
            output = root / "public.csv"
            self.write_source(source, [source_row(1)])
            with self.assertRaisesRegex(ExportError, "SHA-256 mismatch"):
                run(source, output, expected_source_sha256="0" * 64)
            with self.assertRaisesRegex(ExportError, "prefix"):
                run(source, output, expected_id_prefix="pm")
            with self.assertRaisesRegex(ExportError, "record count mismatch"):
                run(source, output, expected_rows=2)

    def test_existing_output_requires_explicit_atomic_force(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "full.csv"
            output = root / "public.csv"
            self.write_source(source, [source_row(1)])
            output.write_bytes(b"reviewed-old-output")
            with self.assertRaisesRegex(ExportError, "refusing to overwrite"):
                run(source, output, expected_id_prefix="pf")
            self.assertEqual(output.read_bytes(), b"reviewed-old-output")
            report = run(
                source,
                output,
                expected_id_prefix="pf",
                force=True,
            )
            self.assertEqual(report["status"], "PASS")
            self.assertNotEqual(output.read_bytes(), b"reviewed-old-output")
            with self.assertRaisesRegex(ExportError, "mutually exclusive"):
                run(source, output, expected_id_prefix="pf", check=True, force=True)


if __name__ == "__main__":
    unittest.main()
