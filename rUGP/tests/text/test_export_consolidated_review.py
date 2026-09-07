import hashlib
import json
import re
from pathlib import Path
import tempfile
import unittest

from rUGP.tools.text.export_consolidated_review import export, public_rows


def row(identity="pf:vm:test:1:2:3"):
    return dict(game="pf", kind="cvm", binding_id=identity, stable_id="old-alias",
                jp="原文\x03\n\x01", en="Source\n\x01",
                cn="【姓名】「正文\n续行。」\x01", input_file="PRIVATE_PATH",
                cn_before_layout="DO_NOT_PUBLISH", native_complete_field="PRIVATE_SOURCE")


class ConsolidatedExportTests(unittest.TestCase):
    def test_committed_snapshot_counts_hashes_and_boundaries(self):
        root = Path(__file__).resolve().parents[2]
        identities = set()
        for title, expected in [("photonflowers", 13025), ("photonmelodies", 44698)]:
            folder = root / "games" / title / "text-data/layout-baseline"
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            count = 0
            for shard in manifest["shards"]:
                raw = (folder / shard["file"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), shard["sha256"])
                rows = json.loads(raw)
                self.assertEqual(len(rows), shard["rows"])
                count += len(rows)
                for item in rows:
                    self.assertNotIn(item["binding_id"], identities)
                    identities.add(item["binding_id"])
                    self.assertFalse({"jp", "en", "input_file", "native_complete_field"} & item.keys())
                    if item["kind"] != "cstring":
                        self.assertNotIn("\x03", item["translated_text"])
                    for name in re.findall(r"【([^】]*)】", item["translated_text"]):
                        self.assertNotIn("\u2060", name)
            self.assertEqual(count, expected)
            self.assertEqual(count, manifest["rows"])

    def test_controls_and_sources(self):
        original = row()
        result = public_rows([original])[0]
        self.assertEqual(result["translated_text"], original["cn"])
        self.assertEqual(result["jp_utf8_sha256"], hashlib.sha256(original["jp"].encode()).hexdigest())
        self.assertFalse({"jp", "en", "input_file", "cn_before_layout", "native_complete_field"} & result.keys())

    def test_binding_not_historical_alias_is_unique(self):
        self.assertEqual(len(public_rows([row(), row("pf:vm:test:4:5:6")])), 2)
        with self.assertRaises(ValueError):
            public_rows([row(), row()])

    def test_no03_no_name_joiners(self):
        for text in ["正文\x03", "【姓\u2060名】正文"]:
            item = row()
            item["cn"] = text
            with self.assertRaises(ValueError):
                public_rows([item])

    def test_cstring_is_display_and_missing_en_is_null(self):
        item = row()
        item.update(kind="cstring", en=None)
        result = public_rows([item])[0]
        self.assertIsNone(result["en_utf8_sha256"])
        self.assertEqual(result["representation"], "reviewed_display_not_serialized_field")

    def test_deterministic_export_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "private.jsonl"
            source.write_text(json.dumps(row()), encoding="utf-8")
            self.assertEqual(export(source, root / "games"), {"pf": 1, "pm": 0})
            export(source, root / "games")
            manifest = next((root / "games").rglob("manifest.json"))
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            shard = manifest.parent / payload["shards"][0]["file"]
            before = shard.read_bytes()
            self.assertEqual(hashlib.sha256(before).hexdigest(), payload["shards"][0]["sha256"])
            source.write_text(json.dumps(dict(row(), cn="另一个版本")), encoding="utf-8")
            with self.assertRaises(ValueError):
                export(source, root / "games")
            self.assertEqual(shard.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
