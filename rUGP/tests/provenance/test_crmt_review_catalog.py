from collections import Counter
import json
import os
from pathlib import Path
import unittest
import subprocess
import sys
import tempfile

from PIL import Image

from rUGP.examples.crmt_review_fixture import write_fixture, digest

from rUGP.tools.provenance.export_crmt_localization_evidence import assert_portable_document
from rUGP.tools.provenance.export_crmt_review_catalog import project


class SyntheticProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "fixture"
        self.review, self.expanded, self.catalog, self.volumes = write_fixture(self.directory)

    def run_projection(self):
        return project(self.review, self.expanded, self.catalog, self.volumes)

    @property
    def branch(self):
        return self.expanded["items"][0]["branches"][0]

    def test_valid_paired_shared_retained_and_unequal_locale_layer_counts(self):
        result = self.run_projection()
        self.assertEqual(result["summary"]["physical_targets"], 4)
        self.assertEqual(result["summary"]["chinese_or_retained_layers"], 8)
        self.assertEqual(len(self.branch["japanese"]["levels"]), 2)
        self.assertEqual(len(self.branch["english"]["levels"]), 1)
        for item in result["items"]:
            for branch in item["branches"]:
                for level in branch["chinese"]["levels"]:
                    self.assertRegex(level["rgba_sha256"], r"^[0-9A-F]{64}$")
                self.assertEqual(branch["evidence"]["controlled_display"], "not_imported_in_this_snapshot")

    def test_swapped_english_object_rejected(self):
        self.branch["english"] = self.expanded["items"][1]["branches"][0]["japanese"]
        with self.assertRaisesRegex(ValueError, "canonical language pairs"):
            self.run_projection()

    def test_cannot_hide_english_localization(self):
        self.branch["english"] = None
        with self.assertRaisesRegex(ValueError, "canonical language pairs"):
            self.run_projection()

    def test_shared_label_cannot_override_pair_census(self):
        self.review["rows"][0]["official_english"] = None
        self.review["rows"][0]["relationship"] = "无英文本地化"
        with self.assertRaisesRegex(ValueError, "shared image conflicts"):
            self.run_projection()

    def test_missing_physical_branch_rejected(self):
        self.expanded["items"][0]["branches"].pop()
        with self.assertRaisesRegex(ValueError, "canonical language pairs"):
            self.run_projection()

    def test_duplicate_physical_branch_rejected(self):
        self.expanded["items"][0]["branches"].append(self.branch)
        with self.assertRaisesRegex(ValueError, "canonical language pairs"):
            self.run_projection()

    def test_review_image_cannot_switch_under_same_logical_id(self):
        self.review["rows"][0]["official_english"]["image_id"] = "SYN002-ja"
        with self.assertRaisesRegex(ValueError, "review image identity"):
            self.run_projection()

    def test_chinese_target_must_match(self):
        self.branch["chinese"]["object_id"] = self.branch["japanese"]["object_id"]
        with self.assertRaisesRegex(ValueError, "Chinese target identity"):
            self.run_projection()

    def test_truncated_chinese_levels_rejected(self):
        self.branch["chinese"]["levels"].pop()
        with self.assertRaisesRegex(ValueError, "incomplete Chinese layer"):
            self.run_projection()

    def test_reordered_chinese_levels_rejected(self):
        self.branch["chinese"]["levels"].reverse()
        with self.assertRaisesRegex(ValueError, "Chinese layer order"):
            self.run_projection()

    def test_duplicate_chinese_levels_rejected(self):
        levels = self.branch["chinese"]["levels"]
        levels[1] = levels[0]
        with self.assertRaisesRegex(ValueError, "Chinese layer order"):
            self.run_projection()

    def alter_png(self, picture, size):
        path = self.directory / "tampered.png"
        Image.new("RGBA", size, (254, 2, 3, 255)).save(path)
        picture.update(path=str(path), sha256=digest(path.read_bytes()))

    def test_self_hashed_wrong_pixels_rejected(self):
        p = self.branch["chinese"]["levels"][0]
        self.alter_png(p, (p["width"], p["height"]))
        with self.assertRaisesRegex(ValueError, "Chinese layer pixels"):
            self.run_projection()

    def test_png_dimensions_not_trusted(self):
        self.alter_png(self.branch["chinese"]["levels"][0], (1, 1))
        with self.assertRaisesRegex(ValueError, "PNG dimensions"):
            self.run_projection()

    def test_record_bytes_are_independently_decoded(self):
        zh = self.branch["chinese"]
        raw = (self.directory / "ja.crmt").read_bytes()
        zh.update(record=str(self.directory / "ja.crmt"), record_sha256=digest(raw))
        with self.assertRaisesRegex(ValueError, "Chinese layer pixels"):
            self.run_projection()

    def test_retained_official_layers_cannot_be_changed(self):
        p = self.expanded["items"][2]["branches"][0]["chinese"]["levels"][0]
        self.alter_png(p, (p["width"], p["height"]))
        with self.assertRaisesRegex(ValueError, "Chinese layer pixels"):
            self.run_projection()

    def test_expanded_decision_must_match_review(self):
        self.expanded["items"][0]["treatment"] = "保留官方日文"
        with self.assertRaisesRegex(ValueError, "review decision"):
            self.run_projection()

    def test_duplicate_expanded_ids_rejected(self):
        self.expanded["items"].append(self.expanded["items"][0])
        with self.assertRaisesRegex(ValueError, "logical IDs"):
            self.run_projection()

    def test_cli_example_and_no_overwrite(self):
        root = Path(__file__).resolve().parents[3]
        fixture_dir = Path(self.temp.name) / "cli-fixture"
        subprocess.run([sys.executable, "-m", "rUGP.examples.crmt_review_fixture", "--output-dir", str(fixture_dir)],
                       cwd=root, check=True, capture_output=True)
        output = fixture_dir / "public.json"
        command = [sys.executable, "-m", "rUGP.tools.provenance.export_crmt_review_catalog"]
        for name in ("review", "expanded", "catalog", "volume-index"):
            command += ["--" + name, str(fixture_dir / (name + ".json"))]
        command += ["--output", str(output)]
        # Windows redirected stdout may use cp1252 even when the parent uses UTF-8.
        env = dict(os.environ, PYTHONIOENCODING="cp1252")
        completed = subprocess.run(command, cwd=root, env=env, capture_output=True)
        self.assertEqual(completed.returncode, 0, completed.stderr.decode("ascii", errors="replace"))
        result = json.loads(output.read_text(encoding="utf-8"))
        assert_portable_document(result)
        self.assertEqual(result["summary"]["logical_groups"], 3)
        original = output.read_bytes()
        self.assertNotEqual(subprocess.run(command, cwd=root, capture_output=True).returncode, 0)
        self.assertEqual(output.read_bytes(), original)
        with self.assertRaises(FileExistsError):
            write_fixture(fixture_dir)


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
