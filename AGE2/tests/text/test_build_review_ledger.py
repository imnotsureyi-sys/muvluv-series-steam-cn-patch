from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from AGE2.tools.text.build_review_ledger import (
    CHAPTER_RE,
    OUTPUT_COLUMNS,
    SHA256_RE,
    LedgerError,
    build_ledger,
    write_new_outputs,
)


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class ReviewLedgerTests(unittest.TestCase):
    def make_inputs(self, root: Path) -> tuple[Path, Path]:
        source = "source line"
        target = "reviewed line"
        translations = root / "translations.csv"
        write_csv(
            translations,
            ("call_order", "id", "egpack", "scene", "speaker_jp", "source_text_sha256", "cn_text"),
            [{
                "call_order": "1", "id": "x", "egpack": "a.egpack", "scene": "s",
                "speaker_jp": "", "source_text_sha256": hashlib.sha256(source.encode()).hexdigest().upper(),
                "cn_text": target,
            }],
        )
        audit = root / "audit.csv"
        write_csv(
            audit,
            ("chapter", "call_order", "id", "egpack", "scene", "issue_type", "jp_text", "cn_text"),
            [{
                "chapter": "TDA00", "call_order": "1", "id": "x", "egpack": "a.egpack",
                "scene": "s", "issue_type": "symbol_count_mismatch", "jp_text": source,
                "cn_text": target,
            }],
        )
        return translations, audit

    def test_exports_only_bound_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            translations, audit = self.make_inputs(Path(temporary))
            payload, report = build_ledger({"TDA00": translations}, {"symbol": audit})
        decoded = payload.decode("utf-8-sig")
        row = next(csv.DictReader(decoded.splitlines()))
        self.assertNotIn("source line", decoded)
        self.assertNotIn("reviewed line", decoded)
        self.assertEqual(row["audit_categories"], "symbol:symbol_count_mismatch")
        self.assertEqual(row["review_status"], "pending_manual_review")
        self.assertFalse(report["contains_source_or_translation_text"])

    def test_private_source_or_target_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, audit = self.make_inputs(root)
            rows = list(csv.DictReader(audit.read_text(encoding="utf-8").splitlines()))
            rows[0]["jp_text"] = "different"
            write_csv(audit, tuple(rows[0]), rows)
            with self.assertRaisesRegex(LedgerError, "source hash drift"):
                build_ledger({"TDA00": translations}, {"symbol": audit})

            translations, audit = self.make_inputs(root)
            rows = list(csv.DictReader(audit.read_text(encoding="utf-8").splitlines()))
            rows[0]["cn_text"] = "different"
            write_csv(audit, tuple(rows[0]), rows)
            with self.assertRaisesRegex(LedgerError, "translation drift"):
                build_ledger({"TDA00": translations}, {"symbol": audit})

    def test_skipped_finding_is_still_bound_before_exclusion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, audit = self.make_inputs(root)
            rows = list(csv.DictReader(audit.read_text(encoding="utf-8").splitlines()))
            rows[0]["issue_type"] = "inner_double_corner_quote_preserved"
            rows[0]["jp_text"] = "drift hidden behind skipped category"
            write_csv(audit, tuple(rows[0]), rows)
            with self.assertRaisesRegex(LedgerError, "source hash drift"):
                build_ledger({"TDA00": translations}, {"symbol": audit})

    def test_duplicate_headers_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, audit = self.make_inputs(root)
            audit.write_text(
                "chapter,call_order,id,egpack,scene,issue_type,issue_type,jp_text,cn_text\n"
                "TDA00,1,x,a.egpack,s,symbol_count_mismatch,hidden,source line,reviewed line\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(LedgerError, "duplicate header"):
                build_ledger({"TDA00": translations}, {"symbol": audit})

    def test_outputs_are_create_only_and_cannot_alias_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, audit = self.make_inputs(root)
            payload, report = build_ledger({"TDA00": translations}, {"symbol": audit})
            output = root / "ledger.csv"
            report_path = root / "report.json"
            write_new_outputs(output, payload, report_path, report, inputs=(translations, audit))
            self.assertEqual(output.read_bytes(), payload)
            with self.assertRaisesRegex(LedgerError, "overwrite"):
                write_new_outputs(output, payload, report_path, report, inputs=(translations, audit))
            with self.assertRaisesRegex(LedgerError, "alias"):
                write_new_outputs(translations, payload, root / "other.json", report, inputs=(translations, audit))
            hardlink = root / "translation-hardlink.csv"
            os.link(translations, hardlink)
            with self.assertRaisesRegex(LedgerError, "alias"):
                write_new_outputs(hardlink, payload, root / "third.json", report, inputs=(translations, audit))

    def test_published_ledger_is_text_free_and_matches_manifest(self) -> None:
        root = Path(__file__).resolve().parents[3]
        evidence = root / "AGE2" / "evidence" / "text-review-ledger-v1"
        payload = (evidence / "pending.csv").read_bytes()
        manifest = json.loads((evidence / "manifest.json").read_text(encoding="utf-8"))
        rows = list(csv.DictReader(payload.decode("utf-8-sig").splitlines()))
        reader = csv.DictReader(payload.decode("utf-8-sig").splitlines())
        self.assertEqual(tuple(reader.fieldnames or ()), OUTPUT_COLUMNS)
        self.assertEqual(len(rows), 246)
        self.assertEqual(manifest["rows"], len(rows))
        self.assertEqual(manifest["output_bytes"], len(payload))
        self.assertEqual(manifest["output_sha256"], hashlib.sha256(payload).hexdigest().upper())
        self.assertFalse(manifest["contains_source_or_translation_text"])
        self.assertNotIn("jp_text", rows[0])
        self.assertNotIn("cn_text", rows[0])
        self.assertTrue(all(row["review_status"] == "pending_manual_review" for row in rows))
        identities = [(row["game"], row["egpack"], row["id"]) for row in rows]
        self.assertEqual(len(identities), len(set(identities)))
        self.assertTrue(
            all(SHA256_RE.fullmatch(row["source_text_sha256"]) for row in rows)
        )
        self.assertTrue(
            all(
                all(
                    CHAPTER_RE.fullmatch(part)
                    for category in row["audit_categories"].split(";")
                    for part in category.split(":", 1)
                )
                for row in rows
            )
        )
        self.assertEqual(
            rows,
            sorted(rows, key=lambda row: (row["game"].casefold(), int(row["call_order"]))),
        )

        translation_paths = {
            "TDA00": root / "AGE2" / "games" / "tda00" / "translations" / "ja-zh-Hans.csv",
            "TDA01": root / "AGE2" / "games" / "tda01" / "translations" / "ja-zh-Hans.csv",
            "TDA02": root / "AGE2" / "games" / "tda02" / "translations" / "ja-zh-Hans.csv",
            "TDA03": root / "AGE2" / "games" / "tda03" / "translations" / "ja-zh-Hans.csv",
        }
        self.assertEqual(set(manifest["translation_inputs"]), set(translation_paths))
        for game, path in translation_paths.items():
            table = path.read_bytes()
            table_rows = list(csv.DictReader(table.decode("utf-8-sig").splitlines()))
            sealed = manifest["translation_inputs"][game]
            self.assertEqual(sealed["bytes"], len(table))
            self.assertEqual(sealed["rows"], len(table_rows))
            self.assertEqual(
                sealed["sha256"], hashlib.sha256(table).hexdigest().upper()
            )


if __name__ == "__main__":
    unittest.main()
