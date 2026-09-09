"""Tiny synthetic pixel fixtures only; never edit or write game artwork."""
from contextlib import redirect_stdout, redirect_stderr
from io import BytesIO, StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from rUGP.tools.images import check_localized_image as checker


def png(image):
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def pixels(size=(4, 3), fill=(10, 20, 30, 255), changes=()):
    image = Image.new("RGBA", size, fill)
    for x, y, rgba in changes:
        image.putpixel((x, y), rgba)
    return image


class LocalizedImageCheckTests(unittest.TestCase):
    def test_changed_rgb_with_unchanged_alpha_is_detected(self):
        source = png(pixels())
        candidate = png(pixels(changes=[(1, 1, (11, 20, 30, 255))]))
        report = checker.check_localized_png(source, candidate, [[1, 1, 2, 2]])
        self.assertEqual(report["status"], "PASS_MECHANICAL_CHECKS_ONLY")
        self.assertEqual(report["pixel_comparison"]["changed_bbox"], [1, 1, 2, 2])
        self.assertEqual(report["pixel_comparison"]["changed_inside_allowed_regions"], 1)
        self.assertEqual(report["pixel_comparison"]["alpha_changed_pixels"], 0)

    def test_exclusive_region_edge_is_protected(self):
        report = checker.check_localized_png(png(pixels()), png(pixels(changes=[(2, 1, (1, 2, 3, 255))])),
                                             [[1, 1, 2, 2]])
        self.assertEqual(report["failures"], ["protected_rgba_pixels_changed"])
        self.assertEqual(report["pixel_comparison"]["outside_change_bbox"], [2, 1, 3, 2])

    def test_overlapping_regions_count_union_not_duplicate_area(self):
        raw = png(pixels())
        report = checker.check_localized_png(raw, raw, [[0, 0, 2, 2], [1, 1, 3, 3]])
        self.assertEqual((report["policy"]["allowed_pixels"], report["policy"]["protected_pixels"]), (7, 5))

    def test_unmodified_image_is_not_promoted_to_translation_or_runtime_acceptance(self):
        raw = png(pixels())
        report = checker.check_localized_png(raw, raw, [])
        self.assertEqual(report["status"], "PASS_MECHANICAL_CHECKS_ONLY")
        self.assertTrue(report["pixel_comparison"]["candidate_pixels_identical_to_source"])
        self.assertIsNone(report["pixel_comparison"]["changed_bbox"])
        for key in ("translation_accepted", "layout_accepted", "runtime_accepted", "inputs_modified"):
            self.assertFalse(report[key])
        self.assertEqual((report["images_written"], report["game_files_written"]), (0, 0))

    def test_transparency_lost_in_same_size_rgb_is_rejected(self):
        source = pixels(fill=(0, 0, 0, 0), changes=[(1, 1, (10, 20, 30, 128))])
        report = checker.check_localized_png(png(source), png(source.convert("RGB")), [[1, 1, 2, 2]])
        self.assertEqual(report["failures"], ["source_transparency_has_no_candidate_storage",
                                             "source_transparency_was_flattened", "protected_rgba_pixels_changed"])
        self.assertEqual(report["pixel_comparison"]["alpha_changed_outside_allowed_regions"], 11)

    def test_opaque_rgba_does_not_hide_a_flattened_alpha_failure(self):
        source = png(pixels(fill=(0, 0, 0, 0)))
        candidate = png(pixels(fill=(0, 0, 0, 255)))
        report = checker.check_localized_png(source, candidate, [[0, 0, 4, 3]])
        self.assertTrue(report["candidate"]["stores_alpha"])
        self.assertEqual(report["failures"], ["source_transparency_was_flattened"])

    def test_nonopaque_alpha_can_change_inside_regions_unless_globally_locked(self):
        source = png(pixels(fill=(0, 0, 0, 0), changes=[(1, 1, (10, 20, 30, 128))]))
        candidate = png(pixels(fill=(0, 0, 0, 0), changes=[(1, 1, (10, 20, 30, 200))]))
        report = checker.check_localized_png(source, candidate, [[1, 1, 2, 2]])
        locked = checker.check_localized_png(source, candidate, [[1, 1, 2, 2]], preserve_alpha_everywhere=True)
        self.assertEqual(report["failures"], [])
        self.assertEqual(locked["failures"], ["alpha_changed_under_global_preservation_policy"])
        self.assertEqual(locked["pixel_comparison"]["alpha_changed_pixels"], 1)

    def test_rgb_under_zero_alpha_is_still_protected_byte_for_byte(self):
        source = png(pixels(fill=(0, 0, 0, 0)))
        candidate = png(pixels(fill=(0, 0, 0, 0), changes=[(2, 1, (1, 0, 0, 0))]))
        report = checker.check_localized_png(source, candidate, [])
        self.assertEqual(report["pixel_comparison"]["outside_change_bbox"], [2, 1, 3, 2])
        self.assertEqual(report["pixel_comparison"]["alpha_changed_pixels"], 0)
        self.assertEqual(report["failures"], ["protected_rgba_pixels_changed"])

    def test_dimension_mismatch_skips_comparison_without_resampling(self):
        source = png(pixels())
        candidate = png(pixels(size=(8, 6)))
        report = checker.check_localized_png(source, candidate, [])
        self.assertEqual(report["failures"], ["dimensions_changed"])
        self.assertEqual(report["candidate"]["dimensions"], [8, 6])
        self.assertIsNone(report["pixel_comparison"])
        self.assertIn("no resampling", report["pixel_comparison_skipped_reason"])

    def test_rgb_is_valid_when_source_and_candidate_are_genuinely_opaque(self):
        source = pixels()
        report = checker.check_localized_png(png(source), png(source.convert("RGB")), [])
        self.assertFalse(report["candidate"]["stores_alpha"])
        self.assertEqual(report["status"], "PASS_MECHANICAL_CHECKS_ONLY")

    def test_palette_transparency_is_recognized(self):
        palette = Image.new("P", (2, 1), 0)
        palette.putpalette([0, 0, 0, 10, 20, 30] + [0] * 762)
        palette.putpixel((1, 0), 1)
        palette.info["transparency"] = 0
        report = checker.check_localized_png(png(palette.convert("RGBA")), png(palette), [])
        self.assertTrue(report["candidate"]["stores_alpha"])
        self.assertEqual(report["candidate"]["transparent_pixels"], 1)
        self.assertEqual(report["failures"], [])

    def test_invalid_regions_and_policy_fail_closed(self):
        raw = png(pixels())
        for regions in (None, "bad", [None], [[1, 2, 3]], [[True, 0, 2, 2]], [[0, 0, 1.5, 2]],
                        [[0, 0, 0, 1]], [[-1, 0, 1, 1]], [[0, 0, 5, 1]], [[0, 2, 1, 4]],
                        [[0, 0, 1, 1]] * 1025):
            with self.subTest(regions=str(regions)[:80]), self.assertRaises(checker.LocalizedImageCheckError):
                checker.check_localized_png(raw, raw, regions)
        with self.assertRaises(checker.LocalizedImageCheckError):
            checker.check_localized_png(raw, raw, [], preserve_alpha_everywhere=1)

    def test_bad_format_and_truncated_png_fail(self):
        source = png(pixels())
        jpeg = BytesIO()
        pixels().convert("RGB").save(jpeg, format="JPEG")
        for raw in (b"", b"not png", source[:40], jpeg.getvalue()):
            with self.subTest(size=len(raw)), self.assertRaises(checker.LocalizedImageCheckError):
                checker.check_localized_png(source, raw, [])

    def test_animated_png_is_not_accepted_as_single_frame(self):
        animated = BytesIO()
        pixels().save(animated, format="PNG", save_all=True, append_images=[pixels(fill=(100, 100, 100, 255))])
        with self.assertRaisesRegex(checker.LocalizedImageCheckError, "animated PNG"):
            checker.check_localized_png(png(pixels()), animated.getvalue(), [])

    def test_allocation_and_file_byte_limits_are_checked(self):
        raw = png(pixels())
        with patch.object(checker, "MAX_PIXELS", 4), self.assertRaises(checker.LocalizedImageCheckError):
            checker.check_localized_png(raw, raw, [])
        with patch.object(checker, "MAX_PNG_BYTES", 10), self.assertRaises(checker.LocalizedImageCheckError):
            checker.check_localized_png(raw, raw, [])

    def test_cli_reports_facts_and_writes_no_files(self):
        with tempfile.TemporaryDirectory(prefix="crmt-image-check-test-") as folder:
            source, candidate = Path(folder) / "source.png", Path(folder) / "candidate.png"
            original = png(pixels())
            modified = png(pixels(changes=[(1, 1, (99, 88, 77, 255))]))
            source.write_bytes(original)
            candidate.write_bytes(modified)
            before = {p.name: p.read_bytes() for p in Path(folder).iterdir()}
            output = StringIO()
            with redirect_stdout(output):
                status = checker.main(["--source-png", str(source), "--candidate-png", str(candidate),
                                       "--region", "1,1,2,2", "--preserve-alpha-everywhere"])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(output.getvalue())["candidate_file"], "candidate.png")
            self.assertEqual(before, {p.name: p.read_bytes() for p in Path(folder).iterdir()})
            output = StringIO()
            with redirect_stdout(output):
                status = checker.main(["--source-png", str(source), "--candidate-png", str(candidate)])
            self.assertEqual(status, 1)
            self.assertEqual(json.loads(output.getvalue())["failures"], ["protected_rgba_pixels_changed"])

    def test_invalid_cli_inputs_are_distinct_from_a_mechanical_failure(self):
        with tempfile.TemporaryDirectory(prefix="crmt-image-check-test-") as folder:
            source = Path(folder) / "source.png"
            source.write_bytes(png(pixels()))
            output = StringIO()
            with redirect_stdout(output):
                status = checker.main(["--source-png", str(source), "--candidate-png", str(source), "--region", "0,0,20,20"])
            self.assertEqual(status, 2)
            self.assertEqual(json.loads(output.getvalue())["status"], "INVALID_INPUT")
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as context:
                checker.main(["--source-png", str(source), "--candidate-png", str(source), "--region", "one,two"])
            self.assertEqual(context.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
