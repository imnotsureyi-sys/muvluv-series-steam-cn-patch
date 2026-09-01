from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image


from localization.tools.images import verify_localized_image_invariants as MODULE


class VerifyLocalizedImageInvariantsTest(unittest.TestCase):
    def fixture(self, directory: Path) -> tuple[Path, Path, Path]:
        source = np.zeros((8, 10, 4), dtype=np.uint8)
        source[:, :, :3] = (30, 40, 50)
        source[:, :, 3] = np.arange(10, dtype=np.uint8)[None, :] * 20
        candidate = source.copy()
        candidate[2:5, 3:7, :3] = (220, 210, 200)
        mask = np.zeros((8, 10), dtype=np.uint8)
        mask[1:6, 2:8] = 255
        source_path = directory / "source.png"
        candidate_path = directory / "candidate.png"
        mask_path = directory / "mask.png"
        Image.fromarray(source, mode="RGBA").save(source_path)
        Image.fromarray(candidate, mode="RGBA").save(candidate_path)
        Image.fromarray(mask, mode="L").save(mask_path)
        return source_path, candidate_path, mask_path

    def test_passes_exact_alpha_and_masked_rgb_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            source, candidate, mask = self.fixture(directory)
            report = MODULE.verify(
                source, candidate, mask, directory / "qa.json", asset_id="fixture"
            )
            self.assertEqual(report["status"], "pass")
            self.assertTrue(report["size_exact"])
            self.assertTrue(report["alpha_exact"])
            self.assertTrue(report["outside_allowed_mask_exact"])
            self.assertEqual(report["changed_pixels"], 12)
            self.assertEqual(report["changed_bbox"], [3, 2, 7, 5])

    def test_allows_alpha_change_inside_the_authorized_mask(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            source, candidate, mask = self.fixture(directory)
            image = np.asarray(Image.open(candidate).convert("RGBA")).copy()
            image[3, 4, 3] ^= 1
            Image.fromarray(image, mode="RGBA").save(candidate)
            report = MODULE.verify(
                source, candidate, mask, directory / "qa.json", asset_id="fixture"
            )
            self.assertEqual(report["status"], "pass")
            self.assertFalse(report["alpha_exact_everywhere"])
            self.assertTrue(report["outside_allowed_mask_alpha_exact"])
            self.assertEqual(report["alpha_changed_pixels_inside_allowed_mask"], 1)
            self.assertEqual(report["alpha_changed_pixels_outside_allowed_mask"], 0)

    def test_rejects_alpha_change_outside_the_authorized_mask(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            source, candidate, mask = self.fixture(directory)
            image = np.asarray(Image.open(candidate).convert("RGBA")).copy()
            image[7, 9, 3] ^= 1
            Image.fromarray(image, mode="RGBA").save(candidate)
            with self.assertRaisesRegex(AssertionError, "alpha changed outside allowed mask"):
                MODULE.verify(source, candidate, mask, directory / "qa.json", asset_id="fixture")

    def test_rejects_change_outside_mask(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            source, candidate, mask = self.fixture(directory)
            image = np.asarray(Image.open(candidate).convert("RGBA")).copy()
            image[7, 9, 0] ^= 1
            Image.fromarray(image, mode="RGBA").save(candidate)
            with self.assertRaisesRegex(AssertionError, "outside allowed mask"):
                MODULE.verify(source, candidate, mask, directory / "qa.json", asset_id="fixture")

    def test_refuses_to_overwrite_an_input_or_existing_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            source, candidate, mask = self.fixture(directory)
            with self.assertRaisesRegex(FileExistsError, "aliases an input"):
                MODULE.verify(source, candidate, mask, source, asset_id="fixture")
            report_path = directory / "qa.json"
            report_path.write_text("reviewed", encoding="utf-8")
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                MODULE.verify(source, candidate, mask, report_path, asset_id="fixture")
            self.assertEqual(report_path.read_text(encoding="utf-8"), "reviewed")


if __name__ == "__main__":
    unittest.main()
