import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[3]
IMPERIAL_TOOLS = ROOT / "AGE2" / "games" / "imperial-capital-burns" / "tools"
RENDER_TEST_FONT = Path("C:/Windows/Fonts/msyhbd.ttc")
TEST_LOCK_MANIFEST = {
    "source_image_lock_name": "synthetic-source-image-lock.json",
    "source_image_lock_sha256": "A" * 64,
}
SPEC = importlib.util.spec_from_file_location(
    "phase1_assets", IMPERIAL_TOOLS / "phase1_assets.py"
)
phase1_assets = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phase1_assets)

sys.path.insert(0, str(IMPERIAL_TOOLS))
BUILD_SPEC = importlib.util.spec_from_file_location(
    "build_phase1", IMPERIAL_TOOLS / "build_phase1.py"
)
build_phase1 = importlib.util.module_from_spec(BUILD_SPEC)
assert BUILD_SPEC.loader is not None
BUILD_SPEC.loader.exec_module(build_phase1)


class ImageSlotTests(unittest.TestCase):
    def test_telop_position_patch_changes_only_shifted_runtime_overlays(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "localized"
            output = root / "payload"
            source.mkdir()
            script = source / "scene.xml"
            original = (
                b'<?xml version="1.0" encoding="utf-8"?>\n'
                b'<node><message id="game_t00001" speaker="$game_t00002" '
                b'text="$game_t00001" voice="JP_001"/>'
                b'<chara img_base="00no_text_telop/add_telop_73" '
                b'pos="0,-2145,723"/>'
                b'<chara img_base="00no_text_telop/add_telop_01" '
                b'pos="0,-1550,723"/>'
                b'<chara img_base="character/yui" pos="0,-2145,723"/>'
                b'</node>\n'
            )
            script.write_bytes(original)

            result = build_phase1.patch_telop_positions(source, output)

            patched = (output / "scene.xml").read_bytes()
            self.assertEqual({"scene.xml": 1}, result)
            self.assertEqual(
                original.replace(
                    b'img_base="00no_text_telop/add_telop_73" pos="0,-2145,723"',
                    b'img_base="00no_text_telop/add_telop_73" pos="0,-1550,723"',
                ),
                patched,
            )
            self.assertIn(b'id="game_t00001"', patched)
            self.assertIn(b'voice="JP_001"', patched)
            self.assertIn(b'img_base="character/yui" pos="0,-2145,723"', patched)

    def test_telop_position_patch_rejects_unknown_runtime_position(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "localized"
            source.mkdir()
            (source / "scene.xml").write_bytes(
                b'<node><chara img_base="00no_text_telop/add_telop_94" '
                b'pos="0,-1999,723"/></node>'
            )

            with self.assertRaisesRegex(RuntimeError, "unexpected add_telop position"):
                build_phase1.patch_telop_positions(source, root / "payload")

    def test_character_card_validator_checks_each_expected_output(self):
        self.assertTrue(
            hasattr(build_phase1, "validate_character_name_cards"),
            "per-card payload validation is missing",
        )
        if not hasattr(build_phase1, "validate_character_name_cards"):
            return

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "option" / "11_name00_ja.webp"
            target.parent.mkdir(parents=True)
            Image.new("RGBA", (224, 96), (0, 0, 0, 0)).save(
                target, format="WEBP", lossless=True
            )
            with self.assertRaisesRegex(RuntimeError, "empty alpha"):
                build_phase1.validate_character_name_cards(
                    root, [{"target_ja": "option/11_name00_ja.webp"}]
                )

    def test_telop_reference_scanner_reads_only_actual_add_telop_ids(self):
        self.assertTrue(
            hasattr(build_phase1, "find_telop_references"),
            "telop reference scanner is missing",
        )
        if not hasattr(build_phase1, "find_telop_references"):
            return

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scene.xml").write_text(
                '<root><chara img_base="add_telop_01"/>'
                '<chara img_base="add_telop_24a_en"/>'
                '<comment note="add_telop_bad"/></root>\n',
                encoding="utf-8",
            )
            (root / "ignored.txt").write_text("add_telop_99", encoding="utf-8")

            self.assertEqual(build_phase1.find_telop_references(root), {"01", "24a"})

    def test_location_date_reference_scanner_normalizes_technical_en_slots(self):
        self.assertTrue(
            hasattr(build_phase1, "find_location_date_references"),
            "location/date reference scanner is missing",
        )
        if not hasattr(build_phase1, "find_location_date_references"):
            return
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scene.xml").write_text(
                '<root><bg img="path/140_テロップ/010_場所指定/EVテロップ_日本帝国_en.avif"/>'
                '<bg img="path/140_テロップ/020_日時指定/EVテロップ_数時間後.avif"/>'
                '<comment note="140_テロップ/010_場所指定/not-an-asset.txt"/></root>',
                encoding="utf-8",
            )
            self.assertEqual(
                build_phase1.find_location_date_references(root),
                {
                    "010_場所指定/EVテロップ_日本帝国.avif",
                    "020_日時指定/EVテロップ_数時間後.avif",
                },
            )
            calls = build_phase1.collect_location_date_calls(root)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]["kind"], "location")
            self.assertEqual(calls[0]["source_relative"], "010_場所指定/EVテロップ_日本帝国.avif")
            self.assertEqual(calls[1]["kind"], "date")

    @unittest.skipUnless(
        RENDER_TEST_FONT.is_file(),
        "pixel geometry requires the Windows release font",
    )
    def test_telop_renderer_uses_verified_canvas_center_and_bottom_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "add_telop_01.webp"
            build_phase1.render_telop(
                "这是中文字幕位置测试",
                RENDER_TEST_FONT,
                output,
            )
            with Image.open(output) as image:
                rgba = image.convert("RGBA")
                bbox = rgba.getchannel("A").getbbox()

        self.assertEqual((1280, 720), rgba.size)
        self.assertIsNotNone(bbox)
        assert bbox is not None
        self.assertEqual(673, bbox[3])
        self.assertLessEqual(abs(((bbox[0] + bbox[2]) / 2) - 640), 12)

    def test_telop_call_audit_enumerates_actual_xml_attributes_and_chapters(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "０２０：１９９７年_07：装甲剣術教練.xml").write_text(
                '<root><chara __line__="123" img_base="path/add_telop_01"/>'
                '<chara __line__="456" img_base="path/add_telop_24a_en"/></root>',
                encoding="utf-8",
            )

            calls = build_phase1.collect_telop_calls(root)

        self.assertEqual(
            [
                {
                    "asset_id": "01",
                    "chapter": "020",
                    "scene": "０２０：１９９７年_07：装甲剣術教練",
                    "xml_line": "123",
                    "attribute": "img_base",
                    "resource": "path/add_telop_01",
                },
                {
                    "asset_id": "24a",
                    "chapter": "020",
                    "scene": "０２０：１９９７年_07：装甲剣術教練",
                    "xml_line": "456",
                    "attribute": "img_base",
                    "resource": "path/add_telop_24a_en",
                },
            ],
            calls,
        )

    @unittest.skipUnless(
        RENDER_TEST_FONT.is_file(),
        "pixel geometry requires the Windows release font",
    )
    def test_character_name_renderer_uses_original_canvas_and_japanese_alpha_band(self):
        self.assertTrue(
            hasattr(phase1_assets, "render_character_name_card"),
            "character-card renderer is missing",
        )
        if not hasattr(phase1_assets, "render_character_name_card"):
            return

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = root / "11_name00_ja.webp"
            output = root / "out" / "11_name00_ja.webp"
            font = RENDER_TEST_FONT
            image = Image.new("RGBA", (224, 96), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((18, 46, 205, 86), fill=(255, 255, 255, 255))
            image.save(template, format="WEBP", lossless=True)

            phase1_assets.render_character_name_card(template, "篁唯依", font, output)

            with Image.open(output) as rendered:
                self.assertEqual(rendered.size, (224, 96))
                alpha_bbox = rendered.convert("RGBA").getchannel("A").getbbox()
            self.assertIsNotNone(alpha_bbox)
            assert alpha_bbox is not None
            self.assertGreaterEqual(alpha_bbox[1], 40)
            self.assertLessEqual(alpha_bbox[3], 96)

    @unittest.skipUnless(
        RENDER_TEST_FONT.is_file(),
        "pixel geometry requires the Windows release font",
    )
    def test_long_character_name_keeps_glow_inside_canvas(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = root / "11_name22_ja.webp"
            output = root / "out" / "11_name22_ja.webp"
            font = RENDER_TEST_FONT
            image = Image.new("RGBA", (224, 96), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle((2, 46, 221, 86), fill=(255, 255, 255, 255))
            image.save(template, format="WEBP", lossless=True)

            phase1_assets.render_character_name_card(
                template, "克劳斯·哈尔特维克克劳斯", font, output
            )

            with Image.open(output) as rendered:
                alpha_bbox = rendered.convert("RGBA").getchannel("A").getbbox()
            self.assertIsNotNone(alpha_bbox)
            assert alpha_bbox is not None
            self.assertGreaterEqual(alpha_bbox[0], 2)
            self.assertLessEqual(alpha_bbox[2], 222)

    @unittest.skipUnless(
        RENDER_TEST_FONT.is_file(),
        "pixel geometry requires the Windows release font",
    )
    def test_location_card_renderer_preserves_jp_line_centers_and_avif_canvas(self):
        self.assertTrue(
            hasattr(phase1_assets, "render_location_date_card"),
            "location/date AVIF renderer is missing",
        )
        if not hasattr(phase1_assets, "render_location_date_card"):
            return

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = root / "jp.avif"
            output = root / "cn.avif"
            source = Image.new("RGB", (1280, 720), "black")
            draw = ImageDraw.Draw(source)
            draw.rectangle((430, 270, 850, 335), fill="white")
            draw.rectangle((250, 380, 1030, 450), fill="white")
            source.save(template, format="AVIF", quality=100, subsampling="4:4:4")

            phase1_assets.render_location_date_card(
                template,
                "第一行|帝国斯卫军附属·山百合女子卫士训练学校",
                RENDER_TEST_FONT,
                output,
            )

            with Image.open(output) as rendered:
                self.assertEqual(rendered.size, (1280, 720))
                self.assertEqual(rendered.convert("RGB").getpixel((0, 0)), (0, 0, 0))
            source_boxes = phase1_assets.detect_text_line_boxes(template)
            output_boxes = phase1_assets.detect_text_line_boxes(output)
            self.assertEqual(len(output_boxes), 2)
            for source_box, output_box in zip(source_boxes, output_boxes):
                source_center = ((source_box[0] + source_box[2]) / 2, (source_box[1] + source_box[3]) / 2)
                output_center = ((output_box[0] + output_box[2]) / 2, (output_box[1] + output_box[3]) / 2)
                self.assertLessEqual(abs(source_center[0] - output_center[0]), 2)
                self.assertLessEqual(abs(source_center[1] - output_center[1]), 2)
                self.assertLessEqual(output_box[2] - output_box[0], source_box[2] - source_box[0])
                self.assertLessEqual(output_box[3] - output_box[1], source_box[3] - source_box[1])

    def test_location_card_renderer_rejects_line_count_mismatch(self):
        if not hasattr(phase1_assets, "render_location_date_card"):
            self.fail("location/date AVIF renderer is missing")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = root / "jp.avif"
            source = Image.new("RGB", (1280, 720), "black")
            ImageDraw.Draw(source).rectangle((400, 320, 880, 400), fill="white")
            source.save(template, format="AVIF", quality=100, subsampling="4:4:4")
            with self.assertRaisesRegex(ValueError, "line count"):
                phase1_assets.render_location_date_card(
                    template,
                    "第一行|多出一行",
                    Path("C:/Windows/Fonts/msyhbd.ttc"),
                    root / "cn.avif",
                )

    def test_english_asset_is_copied_byte_for_byte_into_japanese_slot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source" / "title" / "button_en.webp"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"synthetic-webp")

            copied = phase1_assets.copy_image_slot(
                root / "source",
                root / "payload",
                "title/button_en.webp",
                "title/button_ja.webp",
            )

            self.assertEqual(copied.read_bytes(), b"synthetic-webp")
            self.assertEqual(source.read_bytes(), b"synthetic-webp")

    def test_target_must_be_japanese_slot(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source" / "button_en.webp"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "_ja.webp"):
                phase1_assets.copy_image_slot(
                    root / "source", root / "payload", "button_en.webp", "button_en.webp"
                )

    def test_manifest_paths_reject_windows_posix_and_parent_escape_forms(self):
        unsafe = (
            "../escape_en.webp",
            r"..\escape_en.webp",
            r"C:\escape_en.webp",
            "C:/escape_en.webp",
            "//server/share/escape_en.webp",
            "/absolute/escape_en.webp",
            "option//escape_en.webp",
            "option/./escape_en.webp",
        )
        for value in unsafe:
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "unsafe relative path"):
                    phase1_assets.safe_relative(value)

    def test_manifest_rows_copy_into_the_requested_texture_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source" / "option" / "11_title000_en.webp"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"english-ui")

            build_phase1.copy_image_rows(
                root / "source",
                root / "payload" / "root" / "assets" / "data_spec" / "gui" / "textures",
                [
                    {
                        "source_en": "option/11_title000_en.webp",
                        "target_ja": "option/11_title000_ja.webp",
                    }
                ],
                {
                    "option/11_title000_en.webp": {
                        "target_ja": "option/11_title000_ja.webp",
                        "source_sha256": hashlib.sha256(
                            b"english-ui"
                        ).hexdigest().upper(),
                    }
                },
            )

            copied = (
                root
                / "payload"
                / "root"
                / "assets"
                / "data_spec"
                / "gui"
                / "textures"
                / "option"
                / "11_title000_ja.webp"
            )
            self.assertEqual(copied.read_bytes(), b"english-ui")

    def test_copy_manifest_rejects_wrong_or_incomplete_source_hash_lock(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source" / "option" / "title_en.webp"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"official")
            rows = [
                {
                    "source_en": "option/title_en.webp",
                    "target_ja": "option/title_ja.webp",
                }
            ]
            with self.assertRaisesRegex(ValueError, "mapping mismatch"):
                build_phase1.copy_image_rows(
                    root / "source", root / "payload", rows, {}
                )
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                build_phase1.copy_image_rows(
                    root / "source",
                    root / "payload",
                    rows,
                    {
                        "option/title_en.webp": {
                            "target_ja": "option/title_ja.webp",
                            "source_sha256": "0" * 64,
                        }
                    },
                )
            self.assertFalse((root / "payload" / "option" / "title_ja.webp").exists())

    def test_copy_manifest_rejects_a_locked_target_swap(self):
        rows = [
            {"source_en": "a_en.webp", "target_ja": "b_ja.webp"},
            {"source_en": "b_en.webp", "target_ja": "a_ja.webp"},
        ]
        records = {
            "a_en.webp": {"target_ja": "a_ja.webp", "source_sha256": "A" * 64},
            "b_en.webp": {"target_ja": "b_ja.webp", "source_sha256": "B" * 64},
        }
        with self.assertRaisesRegex(ValueError, "changed_targets"):
            build_phase1.validate_copy_image_rows(rows, records)

    def test_public_source_image_lock_exactly_covers_both_copy_manifests(self):
        copy_root = (
            ROOT
            / "AGE2"
            / "games"
            / "imperial-capital-burns"
            / "images"
            / "copy"
        )
        lock, lock_sha256 = build_phase1.read_source_image_lock(
            copy_root / "source-image-lock.v2.json",
            expected_manifests={
                "data/gui/textures": copy_root / "ui.ja-zh-Hans.tsv",
                "data_spec/gui/textures": copy_root / "schema.tsv",
            },
        )
        self.assertRegex(lock_sha256, r"[0-9A-F]{64}\Z")
        self.assertEqual(
            {
                source: record["target_ja"]
                for source, record in lock["data/gui/textures"].items()
            },
            {
                row["source_en"]: row["target_ja"]
                for row in build_phase1.read_tsv(copy_root / "ui.ja-zh-Hans.tsv")
            },
        )
        self.assertEqual(
            {
                source: record["target_ja"]
                for source, record in lock["data_spec/gui/textures"].items()
            },
            {
                row["source_en"]: row["target_ja"]
                for row in build_phase1.read_tsv(copy_root / "schema.tsv")
            },
        )

    def test_tda_boot_notices_are_copied_byte_for_byte_into_imperial_slots(self):
        self.assertTrue(
            hasattr(build_phase1, "copy_tda_boot_notice_rows"),
            "TDA boot-notice copier is missing",
        )
        if not hasattr(build_phase1, "copy_tda_boot_notice_rows"):
            return
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "tda" / "00_note000_ja.webp"
            source.parent.mkdir(parents=True)
            Image.new("RGB", (32, 24), "white").save(
                source, format="WEBP", lossless=True
            )
            vertical = source.parent / "00_v_note000_ja.webp"
            Image.new("RGB", (24, 32), "white").save(
                vertical, format="WEBP", lossless=True
            )
            digest = hashlib.sha256(source.read_bytes()).hexdigest().upper()
            vertical_digest = hashlib.sha256(vertical.read_bytes()).hexdigest().upper()
            rows = [
                {
                    "source_tda": "00_note000_ja.webp",
                    "target_ja": "boot/00_note000_ja.webp",
                    "width": "32",
                    "height": "24",
                    "sha256": digest,
                },
                {
                    "source_tda": "00_v_note000_ja.webp",
                    "target_ja": "boot/00_v_note000_ja.webp",
                    "width": "24",
                    "height": "32",
                    "sha256": vertical_digest,
                },
            ]

            build_phase1.copy_tda_boot_notice_rows(
                source.parent, root / "payload", rows
            )

            target = root / "payload" / "boot" / "00_note000_ja.webp"
            self.assertEqual(target.read_bytes(), source.read_bytes())


class InstallerTargetTests(unittest.TestCase):
    def test_font_config_matches_tda_all_bold_roles(self):
        root = ET.fromstring(build_phase1.font_config_text())
        params = {
            item.findtext("Label"): {
                "family": item.findtext("FamilyName"),
                "bold": item.findtext("Bold"),
                "file": item.findtext("File"),
            }
            for item in root.findall("./FontParamList/FontParam")
        }

        self.assertEqual(
            {
                "family": "beatfont1",
                "bold": "true",
                "file": "SourceHanSansSC-Bold.otf",
            },
            params["Common"],
        )
        self.assertEqual(
            {
                "family": "message",
                "bold": "true",
                "file": "SourceHanSansSC-Bold.otf",
            },
            params["Message"],
        )
        self.assertEqual(
            {
                "family": "speaker",
                "bold": "true",
                "file": "SourceHanSansSC-Bold.otf",
            },
            params["Speaker"],
        )
        self.assertEqual(
            {
                "family": "hud",
                "bold": "true",
                "file": "SourceHanSansSC-Bold.otf",
            },
            params["Hud"],
        )

    def test_tda_font_payload_uses_only_the_required_root_font_files(self):
        self.assertEqual(
            {
                "Font.cfg",
                "Font_en.cfg",
                "Font_zh_hans.cfg",
                "SourceHanSansSC-Bold.otf",
                "SourceHanSansSC.otf",
                "SourceHanSansSC-LICENSE.txt",
            },
            set(build_phase1.FONT_HASHES)
            | set(build_phase1.FONT_CONFIG_NAMES)
            | {build_phase1.FONT_LICENSE_PAYLOAD_NAME},
        )

    def test_font_license_is_copied_byte_for_byte_and_manifested(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "OFL.txt"
            source.write_bytes(
                b"SIL OPEN FONT LICENSE Version 1.1\r\nSynthetic test fixture.\r\n"
            )
            font_root = (
                root
                / "output"
                / "payload"
                / "root"
                / "assets"
                / "data"
                / "gui"
                / "font"
            )
            (font_root / "SourceHanSansSC.otf").parent.mkdir(parents=True)
            (font_root / "SourceHanSansSC.otf").write_bytes(b"synthetic-font")

            target = build_phase1.copy_font_license(source, font_root)
            build_phase1.write_manifest(root / "output", **TEST_LOCK_MANIFEST)

            self.assertEqual(target.read_bytes(), source.read_bytes())
            manifest = json.loads(
                (root / "output" / "payload-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            license_rows = [
                row
                for row in manifest["files"]
                if row["path"] == build_phase1.FONT_LICENSE_PAYLOAD_PATH
            ]
            self.assertEqual(len(license_rows), 1)
            self.assertEqual(license_rows[0]["size"], source.stat().st_size)
            self.assertEqual(
                license_rows[0]["sha256"],
                hashlib.sha256(source.read_bytes()).hexdigest().upper(),
            )

    def test_manifest_rejects_font_binary_without_nonempty_license(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            font_root = (
                output
                / "payload"
                / "root"
                / "assets"
                / "data"
                / "gui"
                / "font"
            )
            font_root.mkdir(parents=True)
            (font_root / "SourceHanSansSC-Bold.otf").write_bytes(b"synthetic-font")

            with self.assertRaisesRegex(RuntimeError, "license text"):
                build_phase1.write_manifest(output, **TEST_LOCK_MANIFEST)
            self.assertFalse((output / "payload-manifest.json").exists())

            (font_root / build_phase1.FONT_LICENSE_PAYLOAD_NAME).write_text(
                "  \r\n\t", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "license text"):
                build_phase1.write_manifest(output, **TEST_LOCK_MANIFEST)
            self.assertFalse((output / "payload-manifest.json").exists())

    def test_font_license_copy_rejects_missing_empty_or_binary_input(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            target = root / "payload-font"
            with self.assertRaises(FileNotFoundError):
                build_phase1.copy_font_license(root / "missing.txt", target)

            empty = root / "empty.txt"
            empty.write_text(" \r\n\t", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "empty"):
                build_phase1.copy_font_license(empty, target)

            binary = root / "binary.txt"
            binary.write_bytes(b"license\x00text")
            with self.assertRaisesRegex(ValueError, "plain text"):
                build_phase1.copy_font_license(binary, target)

    def test_main_rejects_missing_license_before_creating_staging_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "new-output"
            unused = root / "unused"
            argv = [
                "build_phase1.py",
                "--repo",
                str(root),
                "--gui-root",
                str(unused),
                "--data-spec-gui-root",
                str(unused),
                "--uistring-dec",
                str(unused),
                "--tda-font-root",
                str(unused),
                "--font-license",
                str(root / "missing-license.txt"),
                "--tda-boot-root",
                str(unused),
                "--fsnr-main",
                str(unused),
                "--jp-script-root",
                str(unused),
                "--telop-reference-root",
                str(unused),
                "--location-date-card-root",
                str(unused),
                "--output",
                str(output),
            ]

            with mock.patch.object(sys, "argv", argv):
                with self.assertRaises(FileNotFoundError):
                    build_phase1.main()

            self.assertFalse(output.exists())

    def test_main_rejects_invalid_source_lock_before_creating_staging_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "new-output"
            unused = root / "unused"
            license_path = root / "font-license.txt"
            license_path.write_text("synthetic test license\n", encoding="utf-8")
            argv = [
                "build_phase1.py",
                "--repo",
                str(ROOT),
                "--gui-root",
                str(unused),
                "--data-spec-gui-root",
                str(unused),
                "--uistring-dec",
                str(unused),
                "--tda-font-root",
                str(unused),
                "--font-license",
                str(license_path),
                "--tda-boot-root",
                str(unused),
                "--fsnr-main",
                str(unused),
                "--jp-script-root",
                str(unused),
                "--telop-reference-root",
                str(unused),
                "--location-date-card-root",
                str(unused),
                "--output",
                str(output),
            ]

            with mock.patch.object(sys, "argv", argv):
                with mock.patch.object(
                    build_phase1,
                    "read_source_image_lock",
                    side_effect=ValueError("synthetic invalid lock"),
                ):
                    with self.assertRaisesRegex(ValueError, "invalid lock"):
                        build_phase1.main()

            self.assertFalse(output.exists())

    def test_written_font_configs_are_hash_locked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_phase1.write_font_configs(root)
            hashes = {
                hashlib.sha256((root / name).read_bytes()).hexdigest().upper()
                for name in build_phase1.FONT_CONFIG_NAMES
            }

        self.assertEqual(
            {"72F473093286D0DFC08085BBD85403D35F275B3CFC248102B26B534451D889BC"},
            hashes,
        )

    def test_phase_one_build_cli_has_no_egpack_input(self):
        self.assertTrue(
            hasattr(build_phase1, "create_parser"),
            "phase-one builder must expose its non-story CLI contract",
        )
        if not hasattr(build_phase1, "create_parser"):
            return

        parser = build_phase1.create_parser()
        options = {action.dest for action in parser._actions}
        self.assertNotIn("egpack_root", options)
        self.assertNotIn("tda_smash_font_root", options)
        self.assertIn("telop_reference_root", options)
        self.assertIn("location_date_card_root", options)
        self.assertIn("tda_boot_root", options)
        self.assertIn("font_license", options)

    def test_installer_targets_the_tm_local_appdata_overlay(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            payload = output / "payload" / "root"
            payload.mkdir(parents=True)
            (payload / "synthetic.bin").write_bytes(b"payload")
            build_phase1.write_manifest(output, **TEST_LOCK_MANIFEST)
            build_phase1.write_installers(output)

            install_bat = (output / "install.bat").read_text(encoding="ascii")
            install_ps1 = (output / "install.ps1").read_text(encoding="utf-8-sig")
            uninstall_ps1 = (output / "uninstall.ps1").read_text(encoding="utf-8-sig")
            readme = (output / "README.txt").read_text(encoding="utf-8-sig")
            deck = (output / "STEAM_DECK_MANUAL.txt").read_text(encoding="utf-8-sig")

            self.assertEqual(
                {
                    "install.bat",
                    "install.ps1",
                    "uninstall.ps1",
                    "payload-manifest.json",
                    "README.txt",
                    "STEAM_DECK_MANUAL.txt",
                    "payload",
                },
                {path.name for path in output.iterdir()},
            )
            self.assertIn("install.ps1", install_bat)
            self.assertIn(r'ancr\tm\data', install_ps1)
            self.assertIn(build_phase1.PACK_SHA256, install_ps1)
            self.assertIn("payload-manifest.json", install_ps1)
            self.assertIn("payload-manifest.json", uninstall_ps1)
            self.assertIn("卸载", readme)
            self.assertIn(build_phase1.FONT_LICENSE_PAYLOAD_NAME, readme)
            self.assertIn("compatdata/2630300", deck)
            manifest = __import__("json").loads(
                (output / "payload-manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["original_pack_sha256"], build_phase1.PACK_SHA256)
            self.assertEqual(manifest["files"][0]["path"], "root/synthetic.bin")


if __name__ == "__main__":
    unittest.main()
