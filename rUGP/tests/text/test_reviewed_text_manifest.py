from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unittest

from rUGP.tools.text.export_reviewed_translation import (
    PUBLIC_COLUMNS,
    public_csv_bytes,
)


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "rUGP/evidence/photon-reviewed-text-v1/manifest.json"
EXPECTED_SOURCE_FACTS = {
    "photonflowers-alternative": (
        2080459, "E8379CA3A3109AB71C1143FCE0660356AFDC13EA329D3621C0B6CF65B83354DB", 6033
    ),
    "photonflowers-extra": (
        1887968, "695DBC3FFBCFCDA089E216D797E922F36F985847BB5C17088DD29846B10C462C", 6931
    ),
    "photonmelodies-adoration-resurrection": (
        3124256, "3A148AEC9F86D1D1C88C183CDBAFDCF3EC88E4549C05AD3E0B79EAF47986A5EE", 8407
    ),
    "photonmelodies-shard-of-spacetime": (
        11374564, "B3628BBE3238A1736C1D146B675881333DD3A1F958ECB722D20452572CA62736", 36176
    ),
}
SHA256_RE = re.compile(r"[0-9A-F]{64}\Z")
PUBLIC_REVIEW_FILE_WARNING_BYTES = 9 * 1024 * 1024


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def materialize_public(public: dict[str, object]) -> tuple[bytes, list[str]]:
    if "path" in public:
        relative = str(public["path"])
        return (ROOT / relative).read_bytes(), [relative]
    if public.get("layout") != "rio-file-shards/v1":
        raise AssertionError(f"unsupported reviewed-text public layout: {public!r}")
    rows: list[dict[str, str]] = []
    paths: list[str] = []
    for shard in public.get("shards", []):
        assert isinstance(shard, dict)
        relative = str(shard["path"])
        paths.append(relative)
        payload = (ROOT / relative).read_bytes()
        if len(payload) != shard["bytes"] or digest(payload) != shard["sha256"]:
            raise AssertionError(f"reviewed-text shard identity mismatch: {relative}")
        reader = csv.DictReader(
            io.StringIO(payload.decode("utf-8", errors="strict"), newline="")
        )
        if tuple(reader.fieldnames or ()) != PUBLIC_COLUMNS:
            raise AssertionError(f"reviewed-text shard header mismatch: {relative}")
        members = list(reader)
        if len(members) != shard["rows"]:
            raise AssertionError(f"reviewed-text shard row count mismatch: {relative}")
        if {row["rio_file"] for row in members} != {shard["rio_file"]}:
            raise AssertionError(f"reviewed-text shard RIO mismatch: {relative}")
        if int(members[0]["call_order"]) != shard["call_order_first"]:
            raise AssertionError(f"reviewed-text shard first order mismatch: {relative}")
        if int(members[-1]["call_order"]) != shard["call_order_last"]:
            raise AssertionError(f"reviewed-text shard last order mismatch: {relative}")
        rows.extend(members)
    return public_csv_bytes(rows), paths


class PhotonReviewedTextManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_and_public_tables_are_complete_and_self_consistent(self) -> None:
        manifest = self.manifest
        self.assertEqual(manifest["schema"], "muvluv-photon-reviewed-text/v1")
        self.assertEqual(manifest["status"], "reviewed_translation_source_not_runtime_binding")
        self.assertEqual(manifest["locale"], "zh-Hans")
        self.assertFalse(manifest["official_source_text_included"])
        self.assertEqual(tuple(manifest["public_columns"]), PUBLIC_COLUMNS)
        self.assertEqual(manifest["omitted_source_fields"], ["speaker_jp", "jp_text"])
        self.assertEqual(set(manifest["datasets"]), set(EXPECTED_SOURCE_FACTS))

        total = 0
        public_paths: set[str] = set()
        global_ids: set[str] = set()
        for dataset_id, dataset in manifest["datasets"].items():
            with self.subTest(dataset=dataset_id):
                source = dataset["source"]
                public = dataset["public"]
                self.assertEqual(
                    (source["bytes"], source["sha256"], source["rows"]),
                    EXPECTED_SOURCE_FACTS[dataset_id],
                )
                self.assertEqual(
                    source["availability"], "private-sealed-input-not-in-public-git"
                )
                self.assertFalse(source["public_git_locator_included"])
                self.assertTrue({"commit", "path", "blob_sha1"}.isdisjoint(source))
                self.assertRegex(source["sha256"], SHA256_RE)
                self.assertRegex(public["sha256"], SHA256_RE)
                self.assertGreater(source["bytes"], 0)
                self.assertEqual(source["rows"], public["rows"])

                payload, relatives = materialize_public(public)
                for relative in relatives:
                    self.assertNotIn(relative, public_paths)
                    public_paths.add(relative)
                    target = (ROOT / relative).resolve(strict=True)
                    target.relative_to(ROOT.resolve())
                    self.assertLess(
                        target.stat().st_size,
                        PUBLIC_REVIEW_FILE_WARNING_BYTES,
                        f"review table needs deterministic secondary sharding: {relative}",
                    )
                    self.assertIn(
                        "/translations/reviewed/", relative.replace("\\", "/")
                    )
                self.assertEqual(len(payload), public["bytes"])
                self.assertEqual(digest(payload), public["sha256"])
                self.assertNotIn(b"\r", payload)
                reader = csv.DictReader(
                    io.StringIO(payload.decode("utf-8", errors="strict"), newline="")
                )
                self.assertEqual(tuple(reader.fieldnames or ()), PUBLIC_COLUMNS)

                rows = list(reader)
                self.assertEqual(len(rows), public["rows"])
                for order, row in enumerate(rows, start=1):
                    self.assertEqual(row["call_order"], str(order))
                    self.assertNotEqual(row["translated_text"], "")
                    self.assertNotIn("\x00", row["translated_text"])
                    self.assertRegex(row["source_text_sha256"], SHA256_RE)

                    stable_id = row["stable_id"]
                    self.assertNotIn(stable_id, global_ids)
                    global_ids.add(stable_id)
                    game, kind, rio_file, block, text_offset = stable_id.split(":")
                    self.assertEqual(kind, "static")
                    self.assertEqual(game, "pf" if dataset["game"] == "photonflowers" else "pm")
                    self.assertEqual(rio_file, row["rio_file"])
                    self.assertTrue(block.isascii() and block.isdecimal())
                    self.assertTrue(text_offset.isascii() and text_offset.isdecimal())
                    self.assertEqual(row["scene"], f"crsa:{rio_file}@{int(block)}")

                total += len(rows)

        self.assertEqual(total, 57547)
        self.assertEqual(total, manifest["records"])

    def test_manifest_does_not_publish_private_source_git_locators(self) -> None:
        serialized = MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn('"commit"', serialized)
        self.assertNotIn('"blob_sha1"', serialized)
        self.assertNotIn('"patch-sources/', serialized)


if __name__ == "__main__":
    unittest.main()
