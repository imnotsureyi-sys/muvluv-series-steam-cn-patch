from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
TABLES = {
    "age2/games/tda00/translations/ja-zh-Hans.csv": 3713,
    "age2/games/tda01/translations/ja-zh-Hans.csv": 8565,
    "age2/games/tda02/translations/ja-zh-Hans.csv": 6589,
    "age2/games/tda03/translations/ja-zh-Hans.csv": 6913,
    "age2/games/imperial-capital-burns/translations/main.ja-zh-Hans.csv": 5564,
}
REQUIRED_COLUMNS = {
    "call_order",
    "id",
    "egpack",
    "scene",
    "speaker_jp",
    "source_text_sha256",
    "record_kind",
    "cn_text",
}
EMPTY_TEXT_SHA256 = hashlib.sha256(b"").hexdigest().upper()


class PublishedAge2TranslationTests(unittest.TestCase):
    def test_row_identity_and_frozen_counts(self) -> None:
        for relative, expected_count in TABLES.items():
            with self.subTest(table=relative):
                with (ROOT / relative).open(
                    "r", encoding="utf-8-sig", newline=""
                ) as stream:
                    reader = csv.DictReader(stream)
                    self.assertTrue(REQUIRED_COLUMNS.issubset(reader.fieldnames or ()))
                    self.assertNotIn("jp_text", reader.fieldnames or ())
                    rows = list(reader)
                self.assertEqual(len(rows), expected_count)
                self.assertEqual(
                    [int(row["call_order"]) for row in rows],
                    list(range(1, expected_count + 1)),
                )
                identities = [(row["egpack"], row["id"]) for row in rows]
                self.assertEqual(len(identities), len(set(identities)))
                self.assertFalse(any("\x00" in value for row in rows for value in row.values()))
                self.assertTrue(
                    all(
                        len(row["source_text_sha256"]) == 64
                        and set(row["source_text_sha256"]) <= set("0123456789ABCDEF")
                        for row in rows
                    )
                )
                self.assertTrue(
                    all(row["record_kind"] in {"text", "structural_empty"} for row in rows)
                )
                for row in rows:
                    if row["record_kind"] == "structural_empty":
                        self.assertEqual(row["source_text_sha256"], EMPTY_TEXT_SHA256)
                        self.assertEqual(row["speaker_jp"], "")
                        self.assertEqual(row["cn_text"], "")
                    else:
                        self.assertNotEqual(row["source_text_sha256"], EMPTY_TEXT_SHA256)
                        self.assertNotEqual(row["cn_text"], "")

    def test_portable_tables_match_their_public_export_sidecars(self) -> None:
        for relative in TABLES:
            with self.subTest(table=relative):
                path = ROOT / relative
                name = (
                    "imperial-capital-burns"
                    if "imperial-capital-burns" in relative
                    else Path(relative).parts[2]
                )
                sidecar = json.loads(
                    (
                        ROOT
                        / "age2"
                        / "evidence"
                        / "translation-snapshots-v1"
                        / f"{name}.json"
                    ).read_text(encoding="utf-8")
                )
                payload = path.read_bytes()
                self.assertEqual(sidecar["output_bytes"], len(payload))
                self.assertEqual(
                    sidecar["output_sha256"],
                    hashlib.sha256(payload).hexdigest().upper(),
                )
                self.assertFalse(sidecar["bulk_official_dialogue_included"])
                self.assertEqual(sidecar["removed_source_columns"], ["jp_text"])
                self.assertEqual(
                    sidecar["retained_limited_source_context"], ["speaker_jp"]
                )
                kinds = {"text": 0, "structural_empty": 0}
                with path.open("r", encoding="utf-8-sig", newline="") as stream:
                    for row in csv.DictReader(stream):
                        kinds[row["record_kind"]] += 1
                self.assertEqual(sidecar["record_kinds"], kinds)
                header = next(csv.reader(payload.decode("utf-8-sig").splitlines()))
                self.assertEqual(sidecar["output_columns"], header)


if __name__ == "__main__":
    unittest.main()
