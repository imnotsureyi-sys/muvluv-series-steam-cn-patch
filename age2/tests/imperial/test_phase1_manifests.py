import csv
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[3]
GAME = ROOT / "age2" / "games" / "imperial-capital-burns"
TRANSLATIONS = GAME / "translations"
IMAGE_COPY = GAME / "images" / "copy"


def read_tsv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter="\t"))


def read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


class PhaseOneManifestTests(unittest.TestCase):
    def test_choice_whitelist_contains_only_the_18_branch_item_slots(self):
        manifest = TRANSLATIONS / "choices.ja-zh-Hans.csv"
        self.assertTrue(manifest.is_file(), "choice whitelist is missing")
        if not manifest.is_file():
            return

        rows = read_csv(manifest)
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
        strings = read_tsv(TRANSLATIONS / "ui-strings.ja-zh-Hans.tsv")
        by_id = {row["id"]: row for row in strings}

        self.assertIn("50025", by_id)
        self.assertEqual(by_id["50025"]["jp"], "音量")
        self.assertEqual(by_id["50025"]["zh_cn"], "音声")

    def test_character_name_cards_are_generated_from_japanese_evidence(self):
        manifest = IMAGE_COPY / "character-name-cards.ja-zh-Hans.tsv"
        self.assertTrue(manifest.is_file(), "character-card manifest is missing")
        if not manifest.is_file():
            return

        rows = read_tsv(manifest)
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

        copied = read_tsv(IMAGE_COPY / "schema.tsv")
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
        rows = read_tsv(IMAGE_COPY / "telop.ja-zh-Hans.tsv")

        self.assertEqual(len(rows), 74)
        self.assertEqual({row["asset_id"] for row in rows}, expected)
        for row in rows:
            self.assertTrue(row["resource_file"].endswith(f"add_telop_{row['asset_id']}.webp"))
            self.assertTrue(row["scene"])
            self.assertTrue(row["speaker_jp"])
            self.assertTrue(row["jp_voice"])
            self.assertRegex(row["source_text_sha256"], r"^[0-9A-F]{64}$")
            self.assertTrue(row["zh_cn"])
            self.assertNotIn("jp_text", row)

    def test_location_and_date_cards_are_an_explicit_jp_only_whitelist(self):
        rows = read_tsv(IMAGE_COPY / "location-date-cards.ja-zh-Hans.tsv")
        by_source = {row["source_relative"]: row for row in rows}

        self.assertEqual(len(rows), 61)
        self.assertEqual(len(by_source), 61)
        self.assertEqual(sum(row["kind"] == "location" for row in rows), 54)
        self.assertEqual(sum(row["kind"] == "date" for row in rows), 7)
        for row in rows:
            self.assertIn(row["kind"], {"location", "date"})
            self.assertTrue(row["source_relative"].endswith(".avif"))
            self.assertEqual(int(row["source_line_count"]), row["zh_cn"].count("|") + 1)
            self.assertRegex(row["source_text_sha256"], r"^[0-9A-F]{64}$")
            self.assertTrue(row["zh_cn"])
            self.assertIsNone(re.search(r"[ぁ-ゖァ-ヺ]", row["zh_cn"]))
            self.assertNotIn("jp_text", row)

        defense = by_source["010_場所指定/EVテロップ_第一防衛線　丹波戦区.avif"]
        self.assertEqual(defense["zh_cn"], "第一防卫线 丹波战区")
        school = by_source[
            "010_場所指定/EVテロップ_山百合女子衛士訓練学校　愛宕山実機演習区域.avif"
        ]
        self.assertIn("帝国斯卫军附属·山百合女子卫士训练学校", school["zh_cn"])

    def test_image_and_uistring_whitelists_have_fixed_sizes_and_unique_ids(self):
        images = read_tsv(IMAGE_COPY / "ui.ja-zh-Hans.tsv")
        boot_notices = read_tsv(IMAGE_COPY / "boot-notice.tsv")
        data_spec_images = read_tsv(IMAGE_COPY / "schema.tsv")
        strings = read_tsv(TRANSLATIONS / "ui-strings.ja-zh-Hans.tsv")

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
