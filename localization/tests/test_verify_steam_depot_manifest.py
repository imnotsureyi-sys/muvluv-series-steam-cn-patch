from __future__ import annotations

import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

from localization.tools.verify_steam_depot_manifest import (
    METADATA_MAGIC,
    PAYLOAD_MAGIC,
    parse_depot_manifest,
    verify_named_files,
)


def varint(value: int) -> bytes:
    output = bytearray()
    while value >= 0x80:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def field_varint(number: int, value: int) -> bytes:
    return varint(number << 3) + varint(value)


def field_bytes(number: int, value: bytes) -> bytes:
    return varint((number << 3) | 2) + varint(len(value)) + value


def build_manifest(name: str, content: bytes, *, encrypted: bool = False) -> bytes:
    split = max(1, len(content) // 2)
    chunks = []
    for offset, value in ((0, content[:split]), (split, content[split:])):
        if not value:
            continue
        chunks.append(
            field_bytes(1, hashlib.sha1(value).digest())
            + field_varint(2, 0)
            + field_varint(3, offset)
            + field_varint(4, len(value))
            + field_varint(5, len(value))
        )
    mapping = (
        field_bytes(1, name.encode("utf-8"))
        + field_varint(2, len(content))
        + field_varint(3, 0)
        + field_bytes(4, hashlib.sha1(name.encode("utf-8")).digest())
        + field_bytes(5, hashlib.sha1(content).digest())
        + b"".join(field_bytes(6, chunk) for chunk in chunks)
    )
    payload = field_bytes(1, mapping)
    metadata = (
        field_varint(1, 123)
        + field_varint(2, 456)
        + field_varint(4, int(encrypted))
        + field_varint(5, len(content))
        + field_varint(7, len(chunks))
    )
    return (
        struct.pack("<II", PAYLOAD_MAGIC, len(payload))
        + payload
        + struct.pack("<II", METADATA_MAGIC, len(metadata))
        + metadata
        + b"synthetic-signature-section"
    )


class SteamDepotManifestTests(unittest.TestCase):
    def test_matching_file_has_manifest_chunk_and_full_content_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            content = b"synthetic pack bytes"
            manifest = root / "123_456.manifest"
            manifest.write_bytes(build_manifest("obb/pack.bin", content))
            local = root / "pack.bin"
            local.write_bytes(content)

            result = verify_named_files(manifest, {"obb/pack.bin": local})

            self.assertTrue(result["all_requested_files_match"])
            self.assertEqual(result["manifest"]["metadata"]["depot_id"], 123)
            row = result["verified_files"][0]
            self.assertTrue(row["content_matches_manifest"])
            self.assertTrue(row["chunk_coverage_exact"])
            self.assertEqual(row["failed_chunks"], [])
            serialized = str(result)
            self.assertNotIn(str(root), serialized)

    def test_changed_file_fails_full_and_chunk_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = b"abcdefghij"
            manifest = root / "depot.manifest"
            manifest.write_bytes(build_manifest("game/data.bin", expected))
            local = root / "data.bin"
            local.write_bytes(b"abcdXfghij")

            result = verify_named_files(manifest, {"game/data.bin": local})

            self.assertFalse(result["all_requested_files_match"])
            row = result["verified_files"][0]
            self.assertFalse(row["sha1_matches"])
            self.assertGreater(len(row["failed_chunks"]), 0)

    def test_missing_name_and_duplicate_request_are_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = root / "depot.manifest"
            manifest.write_bytes(build_manifest("game/data.bin", b"data"))
            local = root / "data.bin"
            local.write_bytes(b"data")
            result = verify_named_files(manifest, {"missing.bin": local})
            self.assertFalse(result["all_requested_files_match"])
            self.assertEqual(result["missing_manifest_entries"], ["missing.bin"])
            with self.assertRaisesRegex(ValueError, "case-insensitively unique"):
                verify_named_files(
                    manifest,
                    {"GAME/DATA.BIN": local, "game/data.bin": local},
                )

    def test_encrypted_unsafe_and_truncated_manifests_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            encrypted = root / "encrypted.manifest"
            encrypted.write_bytes(build_manifest("game/data.bin", b"data", encrypted=True))
            with self.assertRaisesRegex(ValueError, "encrypted"):
                parse_depot_manifest(encrypted)

            unsafe = root / "unsafe.manifest"
            unsafe.write_bytes(build_manifest("../escape.bin", b"data"))
            with self.assertRaisesRegex(ValueError, "unsafe manifest filename"):
                parse_depot_manifest(unsafe)

            truncated = root / "truncated.manifest"
            truncated.write_bytes(struct.pack("<II", PAYLOAD_MAGIC, 99) + b"short")
            with self.assertRaisesRegex(ValueError, "truncated"):
                parse_depot_manifest(truncated)


if __name__ == "__main__":
    unittest.main()
