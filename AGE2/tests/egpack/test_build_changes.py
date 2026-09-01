from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from AGE2.tools.egpack.build_changes import (
    ChangeBuildError,
    build_changes,
    csv_bytes,
    materialize_output,
)
from AGE2.tools.egpack.repack_egpack import CHANGE_COLUMNS


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class BuildChangesTests(unittest.TestCase):
    def make_inputs(self, root: Path) -> tuple[Path, Path]:
        source = "「原文」\\p"
        digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
        manifest = root / "manifest.csv"
        write_csv(
            manifest,
            ("relative_path", "id", "slot", "value_sha256", "text"),
            [
                {
                    "relative_path": "scene.egpack",
                    "id": "game_t00001",
                    "slot": "jp",
                    "value_sha256": digest,
                    "text": source,
                },
                {
                    "relative_path": "scene.egpack",
                    "id": "game_t00002",
                    "slot": "jp",
                    "value_sha256": digest,
                    "text": source,
                },
            ],
        )
        translations = root / "translations.csv"
        write_csv(
            translations,
            ("id", "egpack", "source_text_sha256", "cn_text"),
            [
                {
                    "id": "game_t00001",
                    "egpack": "scene.egpack",
                    "source_text_sha256": digest,
                    "cn_text": "「译文」\\p",
                }
            ],
        )
        return translations, manifest

    def test_hash_only_public_table_joins_to_exact_legal_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            translations, manifest = self.make_inputs(Path(temporary))
            rows = build_changes(translations, manifest, slot="jp")
            payload = csv_bytes(rows)

        self.assertEqual(rows[0]["expected_text"], "「原文」\\p")
        self.assertEqual(rows[0]["replacement_text"], "「译文」\\p")
        self.assertTrue(payload.startswith(b"\xef\xbb\xbfrelative_path,id,slot"))

    def test_source_hash_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            translations, manifest = self.make_inputs(Path(temporary))
            with translations.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            rows[0]["source_text_sha256"] = "0" * 64
            write_csv(
                translations,
                ("id", "egpack", "source_text_sha256", "cn_text"),
                rows,
            )
            with self.assertRaisesRegex(ChangeBuildError, "source hash drift"):
                build_changes(translations, manifest, slot="jp")

    def test_exact_source_table_also_fails_on_text_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, manifest = self.make_inputs(root)
            write_csv(
                translations,
                ("id", "egpack", "jp_text", "cn_text"),
                [
                    {
                        "id": "game_t00001",
                        "egpack": "scene.egpack",
                        "jp_text": "不同原文",
                        "cn_text": "译文",
                    }
                ],
            )
            with self.assertRaisesRegex(ChangeBuildError, "exact source text drift"):
                build_changes(translations, manifest, slot="jp")

    def test_empty_appended_replacement_obeys_the_same_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, manifest = self.make_inputs(root)
            appended = root / "append.csv"
            write_csv(
                appended,
                CHANGE_COLUMNS,
                [
                    {
                        "relative_path": "scene.egpack",
                        "id": "game_t00002",
                        "slot": "jp",
                        "expected_text": "「原文」\\p",
                        "replacement_text": "",
                    }
                ],
            )
            with self.assertRaisesRegex(ChangeBuildError, "appended empty replacement"):
                build_changes(translations, manifest, slot="jp", append=(appended,))
            rows = build_changes(
                translations,
                manifest,
                slot="jp",
                append=(appended,),
                allow_empty=True,
            )
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[1]["replacement_text"], "")

    def test_structural_empty_row_is_verified_then_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, manifest = self.make_inputs(root)
            with manifest.open(encoding="utf-8", newline="") as stream:
                manifest_rows = list(csv.DictReader(stream))
            manifest_rows[1]["value_sha256"] = hashlib.sha256(b"").hexdigest()
            manifest_rows[1]["text"] = ""
            write_csv(
                manifest,
                ("relative_path", "id", "slot", "value_sha256", "text"),
                manifest_rows,
            )
            digest = hashlib.sha256("「原文」\\p".encode("utf-8")).hexdigest()
            write_csv(
                translations,
                ("id", "egpack", "source_text_sha256", "record_kind", "cn_text"),
                [
                    {
                        "id": "game_t00001", "egpack": "scene.egpack",
                        "source_text_sha256": digest, "record_kind": "text",
                        "cn_text": "「译文」\\p",
                    },
                    {
                        "id": "game_t00002", "egpack": "scene.egpack",
                        "source_text_sha256": hashlib.sha256(b"").hexdigest(),
                        "record_kind": "structural_empty", "cn_text": "",
                    },
                ],
            )
            rows = build_changes(translations, manifest, slot="jp")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "game_t00001")

    def test_record_kind_misuse_fails_even_with_allow_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, manifest = self.make_inputs(root)
            digest = hashlib.sha256("「原文」\\p".encode("utf-8")).hexdigest()
            write_csv(
                translations,
                ("id", "egpack", "source_text_sha256", "record_kind", "cn_text"),
                [{
                    "id": "game_t00001", "egpack": "scene.egpack",
                    "source_text_sha256": digest, "record_kind": "text", "cn_text": "",
                }],
            )
            with self.assertRaisesRegex(ChangeBuildError, "text record has an empty replacement"):
                build_changes(translations, manifest, slot="jp", allow_empty=True)

    def test_duplicate_or_malformed_csv_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, manifest = self.make_inputs(root)
            translations.write_text(
                "id,egpack,source_text_sha256,cn_text,cn_text\n"
                "game_t00001,scene.egpack," + "0" * 64 + ",GOOD,EVIL\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ChangeBuildError, "duplicate header"):
                build_changes(translations, manifest, slot="jp")

            translations, manifest = self.make_inputs(root)
            with manifest.open("a", encoding="utf-8", newline="") as stream:
                stream.write("scene.egpack,extra,unexpected,field,hash,text\n")
            with self.assertRaisesRegex(ChangeBuildError, "malformed CSV record"):
                build_changes(translations, manifest, slot="jp")

    def test_output_must_not_alias_any_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, manifest = self.make_inputs(root)
            appended = root / "append.csv"
            appended.write_bytes(b"append input")
            before = {path: path.read_bytes() for path in (translations, manifest, appended)}
            for path in before:
                with self.subTest(path=path.name):
                    with self.assertRaisesRegex(ChangeBuildError, "must not overwrite"):
                        materialize_output(
                            path,
                            b"replacement",
                            inputs=(translations, manifest, appended),
                            force=True,
                        )
                    self.assertEqual(path.read_bytes(), before[path])

            hardlink = root / "translations-hardlink.csv"
            os.link(translations, hardlink)
            with self.assertRaisesRegex(ChangeBuildError, "must not overwrite"):
                materialize_output(
                    hardlink,
                    b"replacement",
                    inputs=(translations, manifest, appended),
                    force=True,
                )
            self.assertEqual(translations.read_bytes(), before[translations])

    def test_existing_output_requires_force_and_force_is_atomic_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            translations, manifest = self.make_inputs(root)
            output = root / "changes.csv"
            output.write_bytes(b"reviewed old output")

            with self.assertRaisesRegex(ChangeBuildError, "without --force"):
                materialize_output(
                    output,
                    b"new output",
                    inputs=(translations, manifest),
                )
            self.assertEqual(output.read_bytes(), b"reviewed old output")

            materialize_output(
                output,
                b"new output",
                inputs=(translations, manifest),
                force=True,
            )
            self.assertEqual(output.read_bytes(), b"new output")
            materialize_output(
                output,
                b"new output",
                inputs=(translations, manifest),
                check=True,
            )
            with self.assertRaisesRegex(ChangeBuildError, "cannot be used together"):
                materialize_output(
                    output,
                    b"new output",
                    inputs=(translations, manifest),
                    check=True,
                    force=True,
                )


if __name__ == "__main__":
    unittest.main()
