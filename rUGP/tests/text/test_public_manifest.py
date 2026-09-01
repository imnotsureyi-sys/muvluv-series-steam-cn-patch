from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "rUGP/evidence/photon-text-v1/manifest.json"


class PhotonPublicTextManifestTests(unittest.TestCase):
    def test_tables_match_public_manifest_byte_for_byte(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema"], "muvluv-photon-portable-text-sources/v1")
        self.assertEqual(manifest["locale"], "zh-Hans")
        self.assertFalse(manifest["official_source_text_included"])
        expected_columns = manifest["columns"]

        for game, expected in manifest["games"].items():
            with self.subTest(game=game):
                path = ROOT / expected["path"]
                payload = path.read_bytes()
                self.assertEqual(len(payload), expected["bytes"])
                self.assertEqual(
                    hashlib.sha256(payload).hexdigest().upper(), expected["sha256"]
                )
                with path.open("r", encoding="utf-8-sig", newline="") as stream:
                    reader = csv.DictReader(stream)
                    self.assertEqual(reader.fieldnames, expected_columns)
                    rows = list(reader)
                self.assertEqual(len(rows), expected["rows"])
                identities = [row["stable_id"] for row in rows]
                self.assertEqual(len(identities), len(set(identities)))
                self.assertFalse(any("\x00" in row["runtime_text"] for row in rows))
                self.assertLessEqual(
                    {row["padding_codepoint"] for row in rows}, {"", "U+2060"}
                )
                for row in rows:
                    capacity = int(row["native_capacity_units"])
                    replacement = int(row["replacement_units"])
                    padding = int(row["padding_units"])
                    runtime_text = row["runtime_text"]
                    self.assertGreater(capacity, 0)
                    self.assertEqual(
                        replacement,
                        len(runtime_text.encode("utf-16le", errors="strict")) // 2,
                    )
                    self.assertEqual(padding, runtime_text.count("\u2060"))

                    binding = row["runtime_binding"]
                    self.assertIn(
                        binding, {"direct_top_level", "nested_requires_linking"}
                    )
                    if binding == "nested_requires_linking":
                        # Nested strings are scattered into an existing native
                        # range and may not grow.  One audited PM row omits a
                        # native terminal newline from runtime_text because the
                        # writer restores that boundary control from the source.
                        self.assertLessEqual(replacement, capacity)
                        self.assertIn(capacity - replacement, {0, 1})
                    elif replacement > capacity:
                        # A directly referenced top-level RUO record can grow,
                        # but every such layout/control change must be explicit.
                        self.assertEqual(row["allow_control_change"], "yes")
                        self.assertNotIn(row["control_delta_reason"], {"", "none"})

                    if padding:
                        self.assertEqual(binding, "nested_requires_linking")
                        self.assertEqual(row["padding_codepoint"], "U+2060")
                    else:
                        self.assertEqual(row["padding_codepoint"], "")


if __name__ == "__main__":
    unittest.main()
