from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

from tools.egpack.egpack_codec import (
    EgpackChange,
    EgpackChangeError,
    apply_changes,
    parse_egpack_bytes,
)
from tools.egpack.repack_egpack import CHANGE_COLUMNS, load_changes, main

from .fixtures import build_egpack


class EgpackRepackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original = build_egpack(
            [
                {"id": "game_t00000", "jp": "日本語", "en": "English"},
                {"id": "game_t00001", "jp": "短い", "en": "Second"},
            ]
        )

    def change(
        self,
        text_id: str = "game_t00000",
        slot: str = "jp",
        expected: str = "日本語",
        replacement: str = "这是一段更长的中文",
    ) -> EgpackChange:
        return EgpackChange("scene.egpack", text_id, slot, expected, replacement)

    def test_applies_longer_text_to_only_the_target_slot(self) -> None:
        patched = apply_changes(self.original, [self.change()], source="scene.egpack")
        document = parse_egpack_bytes(patched)

        self.assertEqual(document.records[0].slots["jp"].text, "这是一段更长的中文")
        self.assertEqual(document.records[0].slots["en"].text, "English")
        self.assertEqual(document.records[1].slots["jp"].text, "短い")
        self.assertEqual(len(patched), int.from_bytes(patched[8:12], "little"))

    def test_applies_multiple_changes_in_reverse_offset_order(self) -> None:
        changes = [
            self.change(replacement="中"),
            self.change("game_t00001", "jp", "短い", "第二条更长的中文"),
        ]

        patched = apply_changes(self.original, changes, source="scene.egpack")
        document = parse_egpack_bytes(patched)

        self.assertEqual(document.records[0].slots["jp"].text, "中")
        self.assertEqual(document.records[1].slots["jp"].text, "第二条更长的中文")

    def test_empty_replacement_is_an_intentional_change(self) -> None:
        patched = apply_changes(
            self.original,
            [self.change(replacement="")],
            source="scene.egpack",
        )

        self.assertEqual(parse_egpack_bytes(patched).records[0].slots["jp"].text, "")

    def test_no_changes_is_byte_identical(self) -> None:
        self.assertEqual(apply_changes(self.original, [], source="scene.egpack"), self.original)

    def test_rejects_duplicate_target(self) -> None:
        change = self.change()
        with self.assertRaisesRegex(EgpackChangeError, "duplicate"):
            apply_changes(self.original, [change, change], source="scene.egpack")

    def test_rejects_expected_text_mismatch(self) -> None:
        with self.assertRaisesRegex(EgpackChangeError, "expected_text"):
            apply_changes(
                self.original,
                [self.change(expected="错误原文")],
                source="scene.egpack",
            )

    def test_rejects_unknown_slot_and_missing_id(self) -> None:
        with self.assertRaisesRegex(EgpackChangeError, "unknown slot"):
            apply_changes(self.original, [self.change(slot="xx")], source="scene.egpack")
        with self.assertRaisesRegex(EgpackChangeError, "missing id"):
            apply_changes(
                self.original,
                [self.change(text_id="game_t99999")],
                source="scene.egpack",
            )

    def test_changes_csv_preserves_empty_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "changes.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=CHANGE_COLUMNS)
                writer.writeheader()
                writer.writerow({
                    "relative_path": "scene.egpack",
                    "id": "game_t00000",
                    "slot": "jp",
                    "expected_text": "日本語",
                    "replacement_text": "",
                })

            changes = load_changes(path)

        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].replacement_text, "")

    def test_cli_writes_new_file_without_touching_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source_root = root / "source"
            output_root = root / "output"
            source = source_root / "nested" / "scene.egpack"
            changes_path = root / "changes.csv"
            source.parent.mkdir(parents=True)
            source.write_bytes(self.original)
            self._write_changes(changes_path, "nested/scene.egpack")

            result = main([
                str(source_root),
                "--changes",
                str(changes_path),
                "--output-dir",
                str(output_root),
            ])

            self.assertEqual(result, 0)
            self.assertEqual(source.read_bytes(), self.original)
            patched_path = output_root / "nested" / "scene.egpack"
            self.assertTrue(patched_path.is_file())
            self.assertEqual(
                parse_egpack_bytes(patched_path.read_bytes()).records[0].slots["jp"].text,
                "这是一段更长的中文",
            )

    def test_cli_rejects_existing_output_and_source_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "scene.egpack"
            changes_path = root / "changes.csv"
            output_root = root / "output"
            source.write_bytes(self.original)
            self._write_changes(changes_path, "scene.egpack")
            output_root.mkdir()
            (output_root / "scene.egpack").write_bytes(b"existing")

            with self.assertRaisesRegex(EgpackChangeError, "already exists"):
                main([str(source), "--changes", str(changes_path), "--output-dir", str(output_root)])
            with self.assertRaisesRegex(EgpackChangeError, "overlap"):
                main([str(source), "--changes", str(changes_path), "--output-dir", str(root)])

    def _write_changes(self, path: Path, relative_path: str) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CHANGE_COLUMNS)
            writer.writeheader()
            writer.writerow({
                "relative_path": relative_path,
                "id": "game_t00000",
                "slot": "jp",
                "expected_text": "日本語",
                "replacement_text": "这是一段更长的中文",
            })


if __name__ == "__main__":
    unittest.main()
