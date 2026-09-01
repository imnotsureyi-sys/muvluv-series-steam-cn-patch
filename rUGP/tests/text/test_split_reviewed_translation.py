from __future__ import annotations

import csv
import io
import unittest

from rUGP.tools.text.export_reviewed_translation import PUBLIC_COLUMNS, public_csv_bytes
from rUGP.tools.text.split_reviewed_translation import (
    SplitError,
    combine_shards,
    split_payload,
)


def row(order: int, rio: str) -> dict[str, str]:
    return {
        "call_order": str(order),
        "stable_id": f"pm:static:{rio}:{order}:{order * 2}",
        "rio_file": rio,
        "scene": f"crsa:{rio}@{order}",
        "source_text_sha256": "A" * 64,
        "translated_text": f"译文 {order}",
    }


class SplitReviewedTranslationTests(unittest.TestCase):
    def test_rio_shards_reconstruct_the_exact_canonical_table(self) -> None:
        payload = public_csv_bytes(
            [
                row(1, "game.rio.002"),
                row(2, "game.rio.002"),
                row(3, "game.rio.003"),
            ]
        )
        files, manifest = split_payload(payload)
        self.assertEqual(list(files), ["game.rio.002.zh-Hans.csv", "game.rio.003.zh-Hans.csv"])
        self.assertEqual([item["rows"] for item in manifest], [2, 1])
        self.assertEqual(
            combine_shards([files[item["path"]] for item in manifest]), payload
        )

    def test_rejects_noncanonical_or_noncontiguous_rio_groups(self) -> None:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=PUBLIC_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            [
                row(1, "game.rio.002"),
                row(2, "game.rio.003"),
                row(3, "game.rio.002"),
            ]
        )
        with self.assertRaisesRegex(SplitError, "not one contiguous group"):
            split_payload(stream.getvalue().encode("utf-8"))

    def test_rejects_semantically_invalid_public_rows(self) -> None:
        base = row(1, "game.rio.002")
        mutations = {
            "malformed identity": {**base, "stable_id": "garbage"},
            "identity RIO mismatch": {
                **base,
                "stable_id": "pm:static:other.rio.002:1:2",
            },
            "scene mismatch": {**base, "scene": "crsa:game.rio.002@999"},
            "unsafe RIO": {
                **base,
                "stable_id": "pm:static:../game.rio:1:2",
                "rio_file": "../game.rio",
                "scene": "crsa:../game.rio@1",
            },
            "invalid source hash": {**base, "source_text_sha256": "not-a-hash"},
            "empty translation": {**base, "translated_text": ""},
            "embedded NUL": {**base, "translated_text": "bad\x00text"},
        }
        for name, invalid in mutations.items():
            with self.subTest(name=name):
                with self.assertRaises(SplitError):
                    split_payload(public_csv_bytes([invalid]))

        duplicate = row(1, "game.rio.002")
        second = row(2, "game.rio.002")
        second["stable_id"] = duplicate["stable_id"]
        with self.assertRaisesRegex(SplitError, "duplicate stable identity"):
            split_payload(public_csv_bytes([duplicate, second]))

    def test_rejects_case_insensitive_rio_and_output_name_collision(self) -> None:
        with self.assertRaisesRegex(SplitError, "case-insensitive RIO/output"):
            split_payload(
                public_csv_bytes(
                    [
                        row(1, "Game.rio.002"),
                        row(2, "game.rio.002"),
                    ]
                )
            )


if __name__ == "__main__":
    unittest.main()
