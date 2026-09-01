from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


from localization.tools.images import render_deterministic_localized_text as MODULE
from localization.tools.images import verify_localized_image_invariants as INVARIANTS


FONT = (
    Path(os.environ["WINDIR"]) / "Fonts" / "NotoSansSC-VF.ttf"
    if os.environ.get("WINDIR")
    else Path("__missing_windows_font__")
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def render_shared_baseline_reference(
    text: str,
    font: ImageFont.FreeTypeFont,
    tracking_px: float,
    supersample: int,
    glyph_y_offsets_px: dict[str, float] | None = None,
) -> tuple[Image.Image, float]:
    """Independent Pillow reference for baseline-aligned tracked glyphs."""

    tracking = tracking_px * supersample
    offsets = glyph_y_offsets_px or {}
    glyphs: list[tuple[str, tuple[int, int, int, int], float, float]] = []
    cursor = 0.0
    left = float("inf")
    top = float("inf")
    right = float("-inf")
    bottom = float("-inf")
    for index, char in enumerate(text):
        bbox = font.getbbox(char, stroke_width=0, anchor="ls")
        y_offset = float(offsets.get(char, 0.0)) * supersample
        glyphs.append((char, bbox, cursor, y_offset))
        left = min(left, cursor + bbox[0])
        top = min(top, bbox[1] + y_offset)
        right = max(right, cursor + bbox[2])
        bottom = max(bottom, bbox[3] + y_offset)
        cursor += float(font.getlength(char))
        if index + 1 < len(text):
            cursor += tracking

    origin_x = int(np.floor(left))
    origin_y = int(np.floor(top))
    baseline_y = float(-origin_y)
    image = Image.new(
        "L",
        (
            max(1, int(np.ceil(right)) - origin_x),
            max(1, int(np.ceil(bottom)) - origin_y),
        ),
        0,
    )
    draw = ImageDraw.Draw(image)
    for char, _bbox, xpos, y_offset in glyphs:
        draw.text(
            (round(xpos - origin_x), round(baseline_y + y_offset)),
            char,
            font=font,
            fill=255,
            anchor="ls",
        )
    crop = image.getbbox()
    assert crop is not None
    return image.crop(crop), baseline_y - crop[1]


class DeterministicLocalizedTextTest(unittest.TestCase):
    def profile(self, directory: Path) -> Path:
        data = {
            "schema": "photon-deterministic-text-style/v2",
            "profile_id": "fixture",
            "license": {"font": "Noto Sans SC", "spdx": "OFL-1.1"},
            "render": {
                "supersample": 8,
                "font_path": str(FONT),
                "font_sha256": sha256_file(FONT),
                "font_weight": 700,
                "font_size_px": 22,
                "scale_x": 0.85,
                "tracking_px": -0.4,
                "anchor_px": [40, 25],
                "horizontal_align": "center",
                "vertical_align": "center",
                "fill": {"top_rgba": [255, 255, 255, 255], "bottom_rgba": [255, 180, 210, 255]},
                "strokes": [
                    {"width_px": 2.0, "rgba": [100, 0, 80, 255]},
                    {"width_px": 1.0, "rgba": [180, 0, 100, 255]}
                ],
                "shadow": {"rgba": [40, 0, 60, 220], "offset_px": [1, 2], "spread_px": 0.5, "blur_px": 0.5}
            }
        }
        path = directory / "profile.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def fixture(self, directory: Path) -> tuple[Path, Path, Path]:
        source = np.zeros((50, 80, 4), dtype=np.uint8)
        source[:, :, :3] = (20, 40, 60)
        source[:, :, 3] = np.arange(80, dtype=np.uint8)[None, :] * 3
        background = source.copy()
        source[14:36, 18:62, :3] = (250, 250, 250)
        old = np.zeros((50, 80), dtype=np.uint8)
        old[12:38, 15:65] = 255
        paths = directory / "source.png", directory / "background.png", directory / "old.png"
        Image.fromarray(source, "RGBA").save(paths[0])
        Image.fromarray(background, "RGBA").save(paths[1])
        Image.fromarray(old, "L").save(paths[2])
        return paths

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_renders_deterministically_and_guards_outside_union(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source, background, old = self.fixture(directory)
            profile = self.profile(directory)
            kwargs = dict(
                source_path=source,
                clean_background_path=background,
                old_text_mask_path=old,
                target_text="读取",
                profile_path=profile,
            )
            first = MODULE.render_localized(
                output_path=directory / "a.png",
                allowed_mask_path=directory / "allowed-a.png",
                qa_path=directory / "qa-a.json",
                **kwargs,
            )
            second = MODULE.render_localized(
                output_path=directory / "b.png",
                allowed_mask_path=directory / "allowed-b.png",
                qa_path=directory / "qa-b.json",
                **kwargs,
            )
            self.assertEqual((directory / "a.png").read_bytes(), (directory / "b.png").read_bytes())
            self.assertTrue(first["outside_allowed_mask_exact"])
            self.assertEqual(first["outside_allowed_mask_changed_pixels"], 0)
            self.assertEqual(first["metrics"]["supersample"], 8)
            self.assertEqual(first["metrics"]["variable_font_weight"], 700)
            self.assertEqual(first["metrics"]["font_lock"]["sha256"], sha256_file(FONT))
            self.assertEqual(first["metrics"]["font_lock"]["weight_axis_name"], "Weight")
            self.assertEqual(first["metrics"]["font_lock"]["applied_weight"], 700)
            self.assertEqual(first["changed_pixels"], second["changed_pixels"])
            invariant_report = INVARIANTS.verify(
                source,
                directory / "a.png",
                directory / "allowed-a.png",
                directory / "invariant.json",
                asset_id="fixture",
            )
            self.assertEqual(invariant_report["status"], "pass")
            self.assertTrue(invariant_report["outside_allowed_mask_alpha_exact"])

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_relative_font_path_is_resolved_from_the_profile_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source, background, old = self.fixture(directory)
            profile_path = self.profile(directory)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["render"]["font_path"] = os.path.relpath(FONT, directory)
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            report = MODULE.render_localized(
                source_path=source,
                clean_background_path=background,
                old_text_mask_path=old,
                target_text="读取",
                profile_path=profile_path,
                output_path=directory / "candidate.png",
                allowed_mask_path=directory / "allowed.png",
                qa_path=directory / "qa.json",
            )
            self.assertEqual(report["status"], "pass")

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_refuses_output_aliases_and_existing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source, background, old = self.fixture(directory)
            profile = self.profile(directory)
            with self.assertRaisesRegex(FileExistsError, "aliases an input"):
                MODULE.render_localized(
                    source_path=source,
                    clean_background_path=background,
                    old_text_mask_path=old,
                    target_text="读取",
                    profile_path=profile,
                    output_path=source,
                    allowed_mask_path=directory / "allowed.png",
                    qa_path=directory / "qa.json",
                )
            occupied = directory / "candidate.png"
            occupied.write_bytes(b"reviewed")
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                MODULE.render_localized(
                    source_path=source,
                    clean_background_path=background,
                    old_text_mask_path=old,
                    target_text="读取",
                    profile_path=profile,
                    output_path=occupied,
                    allowed_mask_path=directory / "allowed-2.png",
                    qa_path=directory / "qa-2.json",
                )
            self.assertEqual(occupied.read_bytes(), b"reviewed")

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_explicit_weight_changes_the_rendered_outline(self) -> None:
        digest = sha256_file(FONT)
        thin, thin_lock = MODULE.load_variable_font(FONT, 36, 300, 8, digest)
        black, black_lock = MODULE.load_variable_font(FONT, 36, 900, 8, digest)
        thin_mask = MODULE.render_tracking_mask("读取", thin, 0, 8).image
        black_mask = MODULE.render_tracking_mask("读取", black, 0, 8).image
        self.assertEqual(thin_lock["applied_weight"], 300)
        self.assertEqual(black_lock["applied_weight"], 900)
        self.assertNotEqual(thin_mask.tobytes(), black_mask.tobytes())

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_cjk_and_punctuation_share_one_font_baseline(self) -> None:
        font, _lock = MODULE.load_variable_font(FONT, 22, 700, 8, sha256_file(FONT))
        samples = (
            "窗口",
            "全屏",
            "显示模式",
            "自动快速保存：选项",
            "莫妮卡·贾科萨。",
        )
        for text in samples:
            with self.subTest(text=text):
                actual = MODULE.render_tracking_mask(text, font, -0.4, 8)
                expected, expected_baseline = render_shared_baseline_reference(text, font, -0.4, 8)
                self.assertEqual(actual.image.tobytes(), expected.tobytes())
                self.assertEqual(actual.image.size, expected.size)
                self.assertEqual(actual.baseline_from_top_hi, expected_baseline)

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_tracking_and_explicit_glyph_offsets_remain_relative_to_shared_baseline(self) -> None:
        font, _lock = MODULE.load_variable_font(FONT, 22, 700, 8, sha256_file(FONT))
        text = "窗口：·。"
        offsets = {"：": 1.5, "·": -0.5, "。": 2.0}
        actual = MODULE.render_tracking_mask(text, font, 1.25, 8, offsets)
        expected, expected_baseline = render_shared_baseline_reference(
            text,
            font,
            1.25,
            8,
            offsets,
        )
        unshifted = MODULE.render_tracking_mask(text, font, 1.25, 8)
        self.assertEqual(actual.image.tobytes(), expected.tobytes())
        self.assertEqual(actual.image.size, expected.size)
        self.assertEqual(actual.baseline_from_top_hi, expected_baseline)
        self.assertNotEqual(actual.image.tobytes(), unshifted.image.tobytes())

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_render_metrics_detect_glyph_and_effect_canvas_edge_contact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            profile_path = self.profile(directory)
            centered = json.loads(profile_path.read_text(encoding="utf-8"))
            centered["render"]["anchor_px"] = [110, 40]
            _overlay, _effect, safe = MODULE.render_effects(
                "显示模式：窗口。",
                centered,
                (220, 80),
            )
            self.assertFalse(safe["glyph_touches_canvas_edge"])
            self.assertFalse(safe["effect_touches_canvas_edge"])
            self.assertGreater(min(safe["glyph_edge_clearance_px"].values()), 0)
            self.assertGreater(min(safe["effect_edge_clearance_px"].values()), 0)

            clipped = json.loads(profile_path.read_text(encoding="utf-8"))
            clipped["render"]["anchor_px"] = [0, 80]
            clipped["render"]["horizontal_align"] = "left"
            clipped["render"]["vertical_align"] = "bottom"
            _overlay, _effect, unsafe = MODULE.render_effects(
                "显示模式",
                clipped,
                (220, 80),
            )
            self.assertTrue(unsafe["glyph_touches_canvas_edge"])
            self.assertTrue(unsafe["effect_touches_canvas_edge"])
            self.assertEqual(unsafe["glyph_edge_clearance_px"]["left"], 0)
            self.assertEqual(unsafe["glyph_edge_clearance_px"]["bottom"], 0)
            self.assertEqual(unsafe["effect_edge_clearance_px"]["left"], 0)
            self.assertEqual(unsafe["effect_edge_clearance_px"]["bottom"], 0)

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_effect_mask_covers_every_nonzero_overlay_alpha_pixel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            profile = json.loads(self.profile(directory).read_text(encoding="utf-8"))
            profile["render"]["anchor_px"] = [54, 26]
            overlay, effect, _metrics = MODULE.render_effects("莫妮卡·贾科萨。", profile, (112, 52))
            alpha = np.asarray(overlay.getchannel("A"), dtype=np.uint8)
            allowed = np.asarray(effect, dtype=np.uint8)
            self.assertFalse(np.any((alpha > 0) & (allowed == 0)))

    @unittest.skipUnless(FONT.is_file(), "Noto Sans SC variable font unavailable")
    def test_rejects_font_binary_not_matching_profile_hash(self) -> None:
        with self.assertRaisesRegex(ValueError, "font SHA-256 mismatch"):
            MODULE.load_variable_font(FONT, 22, 700, 8, "0" * 64)

    def test_rejects_non_v2_supersample(self) -> None:
        profile = {
            "schema": "photon-deterministic-text-style/v2",
            "license": {"font": "Noto Sans SC", "spdx": "OFL-1.1"},
            "render": {
                "supersample": 4,
                "scale_x": 1,
                "font_weight": 700,
                "font_path": str(FONT),
                "font_sha256": "0" * 64,
                "horizontal_align": "center",
                "vertical_align": "center",
                "fill": {"top_rgba": [255, 255, 255, 255]}
            }
        }
        with self.assertRaisesRegex(ValueError, "exactly 8x"):
            MODULE.validate_profile(profile)

    def test_rejects_profile_without_ofl_font_provenance(self) -> None:
        profile = {
            "schema": "photon-deterministic-text-style/v2",
            "license": {"font": "Example", "spdx": "proprietary"},
            "render": {},
        }
        with self.assertRaisesRegex(ValueError, "OFL-1.1"):
            MODULE.validate_profile(profile)

    def test_glyph_bbox_gradient_uses_the_visible_glyph_height(self) -> None:
        mask = Image.new("L", (5, 10), 0)
        pixels = np.asarray(mask).copy()
        pixels[3:7, 1:4] = 255
        mask = Image.fromarray(pixels, "L")
        top = (250, 250, 250, 255)
        bottom = (250, 100, 150, 255)
        rendered = np.asarray(MODULE.gradient_tint(mask, top, bottom, "glyph_bbox"))
        self.assertTupleEqual(tuple(rendered[3, 2]), top)
        self.assertTupleEqual(tuple(rendered[6, 2]), bottom)
        self.assertEqual(rendered[2, 2, 3], 0)

    def test_rejects_unknown_gradient_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported gradient scope"):
            MODULE.gradient_tint(
                Image.new("L", (2, 2), 255),
                (255, 255, 255, 255),
                (255, 0, 0, 255),
                "unknown",
            )

    def test_fast_mask_expansion_matches_pillow_square_max_filter(self) -> None:
        rng = np.random.default_rng(20260824)
        pixels = rng.integers(0, 256, (37, 53), dtype=np.uint8)
        source = Image.fromarray(pixels, "L")
        for radius in (1, 3, 10):
            with self.subTest(radius=radius):
                expected = source.filter(ImageFilter.MaxFilter(radius * 2 + 1))
                actual = MODULE.expand_mask(source, radius, 1)
                self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_gradient_gamma_holds_the_light_color_longer(self) -> None:
        mask = Image.new("L", (1, 5), 255)
        top = (254, 254, 254, 255)
        bottom = (254, 100, 150, 255)
        linear = np.asarray(MODULE.gradient_tint(mask, top, bottom, "glyph_bbox", 1.0))
        delayed = np.asarray(MODULE.gradient_tint(mask, top, bottom, "glyph_bbox", 2.0))
        self.assertGreater(delayed[2, 0, 1], linear[2, 0, 1])
        self.assertTupleEqual(tuple(delayed[0, 0]), top)
        self.assertTupleEqual(tuple(delayed[-1, 0]), bottom)


if __name__ == "__main__":
    unittest.main()
