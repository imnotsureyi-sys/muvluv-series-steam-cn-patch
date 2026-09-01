from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

from rugp.packaging import build_photon_cn_beta01 as builder
from rugp.runtime import build as runtime_builder


class PhotonPackageBuilderTests(unittest.TestCase):
    def test_source_date_epoch_is_explicit_and_strict(self) -> None:
        self.assertEqual(builder.parse_source_date_epoch("0"), 0)
        self.assertEqual(builder.parse_source_date_epoch("1788220800"), 1788220800)
        for value in ("", "now", "-1", "4354819199"):
            with self.subTest(value=value):
                with self.assertRaises(argparse.ArgumentTypeError):
                    builder.parse_source_date_epoch(value)

    def test_build_toolchain_identity_is_complete_and_portable(self) -> None:
        identity = builder.build_toolchain_identity()
        self.assertEqual(
            set(identity),
            {
                "python",
                "python_implementation",
                "numpy",
                "zlib_compile",
                "zlib_runtime",
            },
        )
        self.assertTrue(all(identity.values()))
        builder.assert_no_absolute_paths(identity)

    def test_runtime_dll_policy_matches_runtime_builder_authorities(self) -> None:
        for package_game, runtime_game in (("PF", "pf"), ("PM", "pm")):
            identities = builder.RUNTIME_DLL_IDENTITIES[package_game]
            self.assertEqual(
                identities["historical_raw_beta01"]["sha256"],
                runtime_builder.GAMES[runtime_game]["release_sha256"],
            )
            self.assertEqual(
                identities["clean_clone_normalized"]["sha256"],
                runtime_builder.GAMES[runtime_game]["release_normalized_sha256"],
            )

    def test_runtime_dll_accepts_exactly_two_controlled_identities(self) -> None:
        historical = b"historical-runtime"
        normalized = b"normalized-runtime"
        identities = {
            "TEST": {
                "historical_raw_beta01": {
                    "bytes": len(historical),
                    "sha256": hashlib.sha256(historical).hexdigest().upper(),
                },
                "clean_clone_normalized": {
                    "bytes": len(normalized),
                    "sha256": hashlib.sha256(normalized).hexdigest().upper(),
                },
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "Ages3ResT.dll"
            with mock.patch.object(builder, "RUNTIME_DLL_IDENTITIES", identities):
                for expected, content in (
                    ("historical_raw_beta01", historical),
                    ("clean_clone_normalized", normalized),
                ):
                    source.write_bytes(content)
                    selected = builder.select_runtime_dll_identity(source, "TEST")
                    self.assertEqual(selected["selected"], expected)
                    self.assertEqual(selected["bytes"], len(content))
                    self.assertEqual(
                        selected["sha256"],
                        hashlib.sha256(content).hexdigest().upper(),
                    )

                unknown = b"unknown-runtime-xx"
                self.assertEqual(len(unknown), len(historical))
                source.write_bytes(unknown)
                with self.assertRaisesRegex(
                    builder.BuildError, "unapproved runtime DLL identity"
                ):
                    builder.select_runtime_dll_identity(source, "TEST")

    def test_runtime_dll_copy_records_selected_identity_in_manifest_row(self) -> None:
        normalized = b"normalized-runtime"
        identity = {
            "TEST": {
                "historical_raw_beta01": {
                    "bytes": len(b"historical-runtime"),
                    "sha256": hashlib.sha256(b"historical-runtime").hexdigest().upper(),
                },
                "clean_clone_normalized": {
                    "bytes": len(normalized),
                    "sha256": hashlib.sha256(normalized).hexdigest().upper(),
                },
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "Ages3ResT.dll"
            source.write_bytes(normalized)
            data = root / "data"
            data.mkdir()
            with mock.patch.object(builder, "RUNTIME_DLL_IDENTITIES", identity):
                row = builder.copy_controlled_runtime_dll(
                    source,
                    builder.RUNTIME_DLL_TARGET,
                    data,
                    "fixed",
                    {"exists": True},
                    "TEST",
                )

            self.assertEqual(
                row["runtime_identity"],
                {
                    "policy": builder.RUNTIME_DLL_IDENTITY_POLICY,
                    "selected": "clean_clone_normalized",
                    "bytes": len(normalized),
                    "sha256": hashlib.sha256(normalized).hexdigest().upper(),
                },
            )
            self.assertEqual(
                (data / "files" / builder.RUNTIME_DLL_TARGET).read_bytes(), normalized
            )

    def test_non_runtime_fixed_file_still_requires_one_exact_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "other.dll"
            source.write_bytes(b"unexpected")
            data = root / "data"
            data.mkdir()
            with self.assertRaisesRegex(builder.BuildError, "hash drift"):
                builder.copy_final_file(
                    source,
                    "other.dll",
                    data,
                    "fixed",
                    {"exists": True},
                    len(b"unexpected"),
                    hashlib.sha256(b"approved").hexdigest().upper(),
                )

    def test_absolute_paths_are_rejected_at_any_manifest_depth(self) -> None:
        builder.assert_no_absolute_paths(
            {"logical": "photonflowers-beta0.1", "paths": ["files/a.bin"]}
        )
        with self.assertRaisesRegex(builder.BuildError, "absolute workstation path"):
            builder.assert_no_absolute_paths(
                {"authorities": {"source": r"C:\\Users\\builder\\approved"}}
            )
        with self.assertRaisesRegex(builder.BuildError, "absolute workstation path"):
            builder.assert_no_absolute_paths({"source": "/home/builder/approved"})

    def test_zip_is_byte_reproducible_across_roots_and_mtimes(self) -> None:
        old_output = builder.OUTPUT
        old_epoch = builder.BUILD_EPOCH
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                archives: list[Path] = []
                for index in (1, 2):
                    output = root / f"build-{index}"
                    package = output / "Muv-Luv test 汉化补丁 Beta0.1"
                    (package / "data" / "nested").mkdir(parents=True)
                    (package / "使用说明.txt").write_text("相同内容\n", encoding="utf-8")
                    (package / "data" / "nested" / "payload.bin").write_bytes(
                        bytes(range(64))
                    )
                    timestamp = 1_600_000_000 + index * 50_000
                    for source in package.rglob("*"):
                        if source.is_file():
                            os.utime(source, (timestamp, timestamp))

                    builder.OUTPUT = output
                    builder.BUILD_EPOCH = 1_700_000_001
                    archive = output / "package.zip"
                    builder.build_deterministic_zip(package, archive)
                    archives.append(archive)

                first = archives[0].read_bytes()
                second = archives[1].read_bytes()
                self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())
                self.assertEqual(first, second)
                with zipfile.ZipFile(archives[0]) as bundle:
                    self.assertIsNone(bundle.testzip())
                    self.assertEqual(
                        bundle.namelist(),
                        [
                            "Muv-Luv test 汉化补丁 Beta0.1/data/nested/payload.bin",
                            "Muv-Luv test 汉化补丁 Beta0.1/使用说明.txt",
                        ],
                    )
                    self.assertEqual(
                        {entry.date_time for entry in bundle.infolist()},
                        {(2023, 11, 14, 22, 13, 20)},
                    )
        finally:
            builder.OUTPUT = old_output
            builder.BUILD_EPOCH = old_epoch


if __name__ == "__main__":
    unittest.main()
