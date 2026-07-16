import importlib.util
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "phase1_assets", ROOT / "tools" / "imperial" / "phase1_assets.py"
)
phase1_assets = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(phase1_assets)

IMPERIAL_TOOLS = ROOT / "tools" / "imperial"
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

    def test_telop_renderer_uses_verified_canvas_center_and_bottom_baseline(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "add_telop_01.webp"
            build_phase1.render_telop(
                "这是中文字幕位置测试",
                Path("C:/Windows/Fonts/msyhbd.ttc"),
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
            font = Path("C:/Windows/Fonts/msyhbd.ttc")
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

    def test_long_character_name_keeps_glow_inside_canvas(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            template = root / "11_name22_ja.webp"
            output = root / "out" / "11_name22_ja.webp"
            font = Path("C:/Windows/Fonts/msyhbd.ttc")
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
                Path("C:/Windows/Fonts/msyhbd.ttc"),
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
    def test_font_config_uses_regular_body_and_bold_speaker_roles(self):
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
                "family": "Source Han Sans SC",
                "bold": "false",
                "file": "SourceHanSansSC.otf",
            },
            params["Common"],
        )
        self.assertEqual(
            {
                "family": "Source Han Sans SC",
                "bold": "false",
                "file": "SourceHanSansSC.otf",
            },
            params["Message"],
        )
        self.assertEqual(
            {
                "family": "Source Han Sans SC",
                "bold": "true",
                "file": "SourceHanSansSC-Bold.otf",
            },
            params["Speaker"],
        )

    def test_tda_font_payload_uses_only_the_required_root_font_files(self):
        self.assertEqual(
            {
                "Font.cfg",
                "Font_en.cfg",
                "Font_zh_hans.cfg",
                "SourceHanSansSC-Bold.otf",
                "SourceHanSansSC.otf",
            },
            set(build_phase1.FONT_HASHES),
        )

    def test_written_font_configs_are_hash_locked(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            build_phase1.write_font_configs(root)
            hashes = {
                hashlib.sha256((root / name).read_bytes()).hexdigest().upper()
                for name in build_phase1.FONT_CONFIG_NAMES
            }

        self.assertEqual(
            {"51A9E79A17C09BD77192B368BC23ABE2067D984AC807BFA928CC251ACDD70D23"},
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

    def test_installer_targets_the_tm_local_appdata_overlay(self):
        with tempfile.TemporaryDirectory() as td:
            output = Path(td)
            build_phase1.write_installers(output)

            install_bat = (output / "install.bat").read_text(encoding="ascii")
            readme = (output / "README.txt").read_text(encoding="utf-8-sig")
            deck = (output / "SteamDeck手动安装.txt").read_text(encoding="utf-8-sig")

            self.assertEqual(
                {"install.bat", "README.txt", "SteamDeck手动安装.txt"},
                {path.name for path in output.iterdir()},
            )
            self.assertIn(r'%LOCALAPPDATA%\ancr\tm\data', install_bat)
            self.assertIn(r'robocopy "%~dp0payload" "%TARGET%" /E', install_bat)
            self.assertIn("只把其中的 root 目录复制", readme)
            self.assertIn("compatdata/2630300", deck)
            self.assertIn("复制里面的 root 目录", deck)
            self.assertNotIn(".smash", deck)
            self.assertNotIn("cp -a", deck)


if __name__ == "__main__":
    unittest.main()
