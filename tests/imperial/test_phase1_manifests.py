import csv
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
PHASE = ROOT / "chapters" / "imperial-capital-burns" / "phase1"


def read_tsv(name: str):
    with (PHASE / name).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def read_csv(name: str):
    with (PHASE / name).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class PhaseOneManifestTests(unittest.TestCase):
    def test_choice_whitelist_contains_only_the_18_branch_item_slots(self):
        manifest = PHASE / "choice_ja_zh.csv"
        self.assertTrue(manifest.is_file(), "choice whitelist is missing")
        if not manifest.is_file():
            return

        rows = read_csv(manifest.name)
        keys = {(row["relative_path"], row["id"], row["slot"]) for row in rows}
        self.assertEqual(len(rows), 18)
        self.assertEqual(len(keys), 18)
        self.assertEqual({row["slot"] for row in rows}, {"jp"})
        self.assertEqual(len({row["relative_path"] for row in rows}), 7)
        for row in rows:
            self.assertTrue(row["relative_path"].endswith(".egpack"))
            self.assertTrue(row["id"].startswith("game_t"))
            self.assertTrue(row["expected_text"])
            self.assertTrue(row["replacement_text"])
            self.assertNotEqual(row["expected_text"], row["replacement_text"])

    def test_remaining_option_ui_is_explicitly_localized(self):
        strings = read_tsv("uistring_ja_zh.tsv")
        by_id = {row["id"]: row for row in strings}

        self.assertIn("50025", by_id)
        self.assertEqual(by_id["50025"]["jp"], "音量")
        self.assertEqual(by_id["50025"]["zh_cn"], "音声")

    def test_character_name_cards_are_generated_from_japanese_evidence(self):
        manifest = PHASE / "character_name_cards_ja_zh.tsv"
        self.assertTrue(manifest.is_file(), "character-card manifest is missing")
        if not manifest.is_file():
            return

        rows = read_tsv(manifest.name)
        expected_targets = {
            *(f"option/11_name{index:02d}_ja.webp" for index in range(36)),
            "option/11_name_non_ja.webp",
        }
        self.assertEqual(len(rows), 37)
        self.assertEqual({row["target_ja"] for row in rows}, expected_targets)
        for row in rows:
            self.assertTrue(row["jp"])
            self.assertTrue(row["zh_cn"])
            self.assertNotEqual(row["jp"], row.get("source_en", ""))

        copied = read_tsv("image_ui_copy_data_spec.tsv")
        copied_targets = {row["target_ja"] for row in copied}
        self.assertTrue(expected_targets.isdisjoint(copied_targets))

    def test_only_script_referenced_telops_are_listed_with_jp_evidence(self):
        expected = {
            *(f"{n:02d}" for n in range(1, 9)),
            *(f"{n:02d}" for n in range(10, 24)),
            "24a",
            "24b",
            *(f"{n:02d}" for n in range(25, 42)),
            *(f"{n:02d}" for n in range(59, 76)),
            *(f"{n:02d}" for n in range(79, 83)),
            *(f"{n:02d}" for n in range(85, 90)),
            *(f"{n:02d}" for n in range(91, 98)),
        }
        rows = read_tsv("telop_ja_zh.tsv")

        self.assertEqual(len(rows), 74)
        self.assertEqual({row["asset_id"] for row in rows}, expected)
        for row in rows:
            self.assertTrue(row["resource_file"].endswith(f"add_telop_{row['asset_id']}.webp"))
            self.assertTrue(row["scene"])
            self.assertTrue(row["speaker_jp"])
            self.assertTrue(row["jp_voice"])
            self.assertTrue(row["jp_text"])
            self.assertTrue(row["zh_cn"])

    def test_location_and_date_cards_are_an_explicit_jp_only_whitelist(self):
        rows = read_tsv("location_date_cards_ja_zh.tsv")
        by_source = {row["source_relative"]: row for row in rows}

        self.assertEqual(len(rows), 61)
        self.assertEqual(len(by_source), 61)
        self.assertEqual(sum(row["kind"] == "location" for row in rows), 54)
        self.assertEqual(sum(row["kind"] == "date" for row in rows), 7)
        for row in rows:
            self.assertIn(row["kind"], {"location", "date"})
            self.assertTrue(row["source_relative"].endswith(".avif"))
            self.assertEqual(row["jp_text"].count("|"), row["zh_cn"].count("|"))
            self.assertTrue(row["jp_text"])
            self.assertTrue(row["zh_cn"])
            self.assertIsNone(re.search(r"[ぁ-ゖァ-ヺ]", row["zh_cn"]))

        defense = by_source["010_場所指定/EVテロップ_第一防衛線　丹波戦区.avif"]
        self.assertEqual(defense["zh_cn"], "第一防卫线 丹波战区")
        school = by_source[
            "010_場所指定/EVテロップ_山百合女子衛士訓練学校　愛宕山実機演習区域.avif"
        ]
        self.assertIn("帝国斯卫军附属·山百合女子卫士训练学校", school["zh_cn"])

    def test_image_and_uistring_whitelists_have_fixed_sizes_and_unique_ids(self):
        images = read_tsv("image_ui_copy.tsv")
        boot_notices = read_tsv("boot_notice_tda.tsv")
        data_spec_images = read_tsv("image_ui_copy_data_spec.tsv")
        strings = read_tsv("uistring_ja_zh.tsv")

        self.assertEqual(len(images), 42)
        self.assertEqual(len({row["target_ja"] for row in images}), 42)
        self.assertEqual(len(boot_notices), 2)
        self.assertEqual(
            {row["target_ja"] for row in boot_notices},
            {"boot/00_note000_ja.webp", "boot/00_v_note000_ja.webp"},
        )
        self.assertTrue(
            {row["target_ja"] for row in boot_notices}.isdisjoint(
                {row["target_ja"] for row in images}
            )
        )
        self.assertEqual(len(data_spec_images), 86)
        self.assertEqual(len({row["target_ja"] for row in data_spec_images}), 86)
        allowed_dirs = {
            "Jukebox",
            "backlog",
            "chapter",
            "clearlist",
            "common",
            "control",
            "gallery",
            "load",
            "main",
            "manual",
            "option",
            "save",
            "theater",
            "title",
        }
        for row in data_spec_images:
            self.assertTrue(row["source_en"].endswith("_en.webp"))
            self.assertTrue(row["target_ja"].endswith("_ja.webp"))
            self.assertEqual(row["source_en"].split("/", 1)[0], row["target_ja"].split("/", 1)[0])
            self.assertIn(row["source_en"].split("/", 1)[0], allowed_dirs)
        self.assertEqual(len(strings), 76)
        self.assertEqual(len({row["id"] for row in strings}), 76)


if __name__ == "__main__":
    unittest.main()
