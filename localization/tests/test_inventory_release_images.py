from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from PIL import Image

from localization.tools.images.inventory_release_images import (
    build_inventory,
    normalize_archive_path,
    write_inventory,
)


def make_webp(color: tuple[int, int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGBA", (3, 2), color).save(output, format="WEBP", lossless=True)
    return output.getvalue()


class ReleaseImageInventoryTests(unittest.TestCase):
    def test_normalizes_wrapper_and_windows_separators(self) -> None:
        archive_path, payload_path = normalize_archive_path(
            r"wrapper\payload\root\assets\data\gui\button_zh.webp"
        )
        self.assertEqual(
            archive_path,
            "wrapper/payload/root/assets/data/gui/button_zh.webp",
        )
        self.assertEqual(payload_path, "root/assets/data/gui/button_zh.webp")

    def test_rejects_unsafe_archive_paths(self) -> None:
        for path in (
            "../payload/root/button.webp",
            "/payload/root/button.webp",
            r"C:\payload\root\button.webp",
            "payload//root/button.webp",
            "payload/./root/button.webp",
        ):
            with self.subTest(path=path), self.assertRaisesRegex(
                ValueError, "unsafe archive member"
            ):
                normalize_archive_path(path)

    def test_builds_deterministic_decoded_inventory(self) -> None:
        image_bytes = make_webp((1, 2, 3, 128))
        with tempfile.TemporaryDirectory() as directory:
            zip_path = Path(directory) / "patch.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("wrapper/payload/root/ui/button_zh.webp", image_bytes)
                archive.writestr("wrapper/payload/README.txt", "not an image")

            zip_sha256 = hashlib.sha256(zip_path.read_bytes()).hexdigest().upper()
            inventory = build_inventory(
                zip_path,
                game_id="synthetic",
                engine="AGE2",
                release_tag="test-v1",
                source_url="https://example.invalid/test-v1/patch.zip",
                expected_zip_sha256=zip_sha256,
            )

        self.assertEqual(inventory["image_count"], 1)
        self.assertEqual(inventory["format_counts"], {"WEBP": 1})
        self.assertEqual(inventory["filename_locale_hint_counts"], {"zh": 1})
        self.assertEqual(inventory["entries"][0]["width"], 3)
        self.assertEqual(inventory["entries"][0]["height"], 2)
        self.assertEqual(inventory["entries"][0]["mode"], "RGBA")
        self.assertEqual(
            inventory["entries"][0]["sha256"],
            hashlib.sha256(image_bytes).hexdigest().upper(),
        )

    def test_rejects_wrong_zip_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            zip_path = Path(directory) / "patch.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("payload/root/ui/button.webp", make_webp((0, 0, 0, 0)))

            with self.assertRaisesRegex(ValueError, "ZIP SHA-256 mismatch"):
                build_inventory(
                    zip_path,
                    game_id="synthetic",
                    engine="AGE2",
                    release_tag="test-v1",
                    source_url="https://example.invalid/test-v1/patch.zip",
                    expected_zip_sha256="0" * 64,
                )

    def test_rejects_case_insensitive_duplicate_image_paths(self) -> None:
        image_bytes = make_webp((1, 2, 3, 255))
        with tempfile.TemporaryDirectory() as directory:
            zip_path = Path(directory) / "patch.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                archive.writestr("payload/root/ui/Button.webp", image_bytes)
                archive.writestr("payload/root/ui/button.webp", image_bytes)

            with self.assertRaisesRegex(ValueError, "case-insensitive"):
                build_inventory(
                    zip_path,
                    game_id="synthetic",
                    engine="AGE2",
                    release_tag="test-v1",
                    source_url="https://example.invalid/test-v1/patch.zip",
                )

    def test_inventory_output_is_create_only_and_cannot_alias_an_input(self) -> None:
        inventory = {"schema": "synthetic/v1"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "inventory.json"
            write_inventory(output, inventory)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")), inventory
            )
            with self.assertRaisesRegex(FileExistsError, "already exists"):
                write_inventory(output, inventory)

            source = root / "source.zip"
            source.write_bytes(b"source")
            with self.assertRaisesRegex(FileExistsError, "aliases an input"):
                write_inventory(source, inventory, inputs=[source])

    def test_public_age2_inventories_are_complete_and_self_consistent(self) -> None:
        root = Path(__file__).resolve().parents[2]
        release_index = json.loads(
            (root / "docs" / "player" / "release-index.json").read_text(
                encoding="utf-8"
            )
        )
        releases = {
            item["game_id"]: item for item in release_index["player_packages"]
        }
        expected_counts = {
            "tda00": (70, 59),
            "tda01": (93, 71),
            "tda02": (100, 80),
            "tda03": (152, 90),
            "imperial-capital-burns": (315, 232),
        }
        total = 0
        for game_id, (image_count, unique_count) in expected_counts.items():
            manifest_path = (
                root / "AGE2" / "games" / game_id / "images" / "release-inventory.json"
            )
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries = manifest["entries"]
            self.assertEqual(manifest["schema"], "muvluv-release-image-inventory/v1")
            self.assertEqual(manifest["game_id"], game_id)
            self.assertEqual(manifest["engine"], "AGE2")
            self.assertEqual(manifest["release_tag"], releases[game_id]["release_tag"])
            self.assertEqual(manifest["release_asset"], releases[game_id]["asset_name"])
            self.assertEqual(
                manifest["release_asset_url"], releases[game_id]["asset_url"]
            )
            self.assertEqual(
                manifest["release_asset_sha256"], releases[game_id]["asset_sha256"]
            )
            self.assertEqual(manifest["image_count"], image_count)
            self.assertEqual(manifest["unique_content_count"], unique_count)
            self.assertEqual(
                manifest["duplicate_content_reference_count"],
                image_count - unique_count,
            )
            self.assertEqual(len(entries), image_count)
            self.assertEqual(len({entry["path"] for entry in entries}), image_count)
            self.assertEqual(len({entry["sha256"] for entry in entries}), unique_count)
            self.assertTrue(all(entry["format"] == "WEBP" for entry in entries))
            self.assertTrue(all(entry["bytes"] > 0 for entry in entries))
            self.assertEqual(
                manifest["filename_locale_hint_counts"].get("en", 0),
                releases[game_id]["en_named_image_members"],
            )
            self.assertTrue(
                all(
                    len(entry["sha256"]) == 64
                    and entry["sha256"] == entry["sha256"].upper()
                    for entry in entries
                )
            )
            total += image_count
        self.assertEqual(total, 730)


if __name__ == "__main__":
    unittest.main()
