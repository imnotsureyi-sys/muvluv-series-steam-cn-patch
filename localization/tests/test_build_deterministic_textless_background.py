from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


from localization.tools.images import build_deterministic_textless_background as MODULE


class DeterministicTextlessBackgroundTest(unittest.TestCase):
    def test_harmonic_fill_preserves_outside_and_alpha(self) -> None:
        h, w = 30, 60
        y, x = np.mgrid[:h, :w]
        rgb = np.stack((20 + x * 2, 40 + y * 3, 80 + x + y), axis=2)
        rgba = np.concatenate(
            (np.clip(rgb, 0, 255).astype(np.uint8), np.full((h, w, 1), 173, np.uint8)),
            axis=2,
        )
        mask = np.zeros((h, w), dtype=bool)
        mask[10:20, 18:43] = True
        corrupted = rgba.copy()
        corrupted[mask, :3] = 255
        recovered, _, _ = MODULE.harmonic_inpaint(
            corrupted[:, :, :3], mask, max_iterations=3000, tolerance=0.001
        )
        out = corrupted.copy()
        out[mask, :3] = recovered[mask]
        self.assertTrue(np.array_equal(out[~mask], corrupted[~mask]))
        self.assertTrue(np.array_equal(out[:, :, 3], corrupted[:, :, 3]))
        self.assertLess(float(np.abs(out[mask, :3].astype(int) - rgba[mask, :3]).mean()), 3.0)

    def test_mask_is_limited_to_patch(self) -> None:
        image = Image.new("RGBA", (80, 40), (80, 20, 120, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 10, 10), fill="white")
        draw.rectangle((30, 15, 45, 25), fill="white")
        mask = MODULE.build_mask(
            image,
            (20, 10, 60, 35),
            neutral_tolerance=5,
            fill_floor=220,
            fill_ceiling=255,
            dilate=2,
        )
        arr = np.asarray(mask) > 0
        self.assertFalse(arr[:10, :15].any())
        self.assertTrue(arr[15:26, 30:46].all())

    def test_solver_rejects_invalid_or_unconverged_runs(self) -> None:
        source = np.random.default_rng(20260901).integers(
            0, 256, (7, 7, 3), dtype=np.uint8
        )
        mask = np.zeros((7, 7), dtype=bool)
        mask[2:5, 2:5] = True
        with self.assertRaisesRegex(ValueError, "max_iterations must be positive"):
            MODULE.harmonic_inpaint(source, mask, max_iterations=0, tolerance=0.01)
        with self.assertRaisesRegex(ValueError, "tolerance must be finite and positive"):
            MODULE.harmonic_inpaint(
                source, mask, max_iterations=10, tolerance=float("inf")
            )
        with self.assertRaisesRegex(RuntimeError, "did not converge"):
            MODULE.harmonic_inpaint(
                source, mask, max_iterations=1, tolerance=1e-12
            )


if __name__ == "__main__":
    unittest.main()
