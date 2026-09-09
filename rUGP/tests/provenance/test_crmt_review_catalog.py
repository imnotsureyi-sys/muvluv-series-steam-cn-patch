from collections import Counter
import json
from pathlib import Path
import unittest

from rUGP.tools.provenance.export_crmt_localization_evidence import assert_portable_document
from rUGP.tools.provenance.export_crmt_review_catalog import project


class ReviewCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((Path(__file__).resolve().parents[2] / "evidence/photon/crmt/review-catalog.json").read_text(encoding="utf-8"))

    def test_counts_close_and_no_images_or_private_paths(self):
        d = self.data
        assert_portable_document(d)
        self.assertEqual(len(d["items"]), 49)
        self.assertEqual(len(d["objects"]), 90)
        self.assertEqual(sum(len(o["levels"]) for o in d["objects"]), 476)
        self.assertEqual(sum(len(b["chinese"]["levels"]) for r in d["items"] for b in r["branches"]), 322)
        self.assertEqual(len({(b["game"], b["target_object"]) for r in d["items"] for b in r["branches"]}), 59)
        self.assertEqual(Counter(r["treatment"] for r in d["items"]), {"中文改图": 38, "复用官方日文": 3, "用户成图": 1, "保留官方日文": 7})
        self.assertNotIn('"path":', json.dumps(d))

    def test_locale_mapping_and_every_level(self):
        objects = {(o["game"], o["object_id"]): o for o in self.data["objects"]}
        self.assertEqual(sum(any(b["official_english"] for b in r["branches"]) for r in self.data["items"]), 23)
        for o in objects.values():
            self.assertEqual([p["level"] for p in o["levels"]], list(range(len(o["levels"]))))
            self.assertGreater(o["extent"], 0)
            self.assertRegex(o["record_sha256"], r"^[0-9A-F]{64}$")
        for r in self.data["items"]:
            for b in r["branches"]:
                self.assertIn((b["game"], b["official_japanese"]), objects)
                self.assertEqual(b["target_object"], b["official_english"] or b["official_japanese"])
                if b["official_english"]:
                    self.assertIn((b["game"], b["official_english"]), objects)
                else:
                    self.assertEqual(b["english_localization"], "none_uses_official_japanese")

    def test_no_runtime_or_release_promotion_from_offline_review(self):
        states = [b["evidence"] for r in self.data["items"] for b in r["branches"]]
        self.assertEqual(sum(s["controlled_display"] == "passed_diagnostic_original_key" for s in states), 18)
        self.assertTrue(all(s["original_story"] == "not_certified_by_this_snapshot" for s in states))

    def test_projection_rejects_mismatched_or_duplicate_ids(self):
        for review in ({"rows": [{"id": "U1"}]}, {"rows": [{"id": "U1"}, {"id": "U1"}]}):
            with self.assertRaisesRegex(ValueError, "logical IDs"):
                project(review, {"items": []}, {"objects": []}, [])

    def test_unrecognized_runtime_result_is_not_promoted(self):
        with self.assertRaisesRegex(ValueError, "runtime report"):
            project({"rows": []}, {"items": []}, {"objects": []}, [], [{"status": "PNG_LOOKS_GOOD"}])
