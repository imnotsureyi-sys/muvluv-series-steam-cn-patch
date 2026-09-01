from __future__ import annotations

import struct
import json
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from rUGP.runtime.build import (
    BuildError,
    GENERATED,
    ROOT,
    TARGET,
    _compile_command,
    _manifest_inputs,
    build,
    normalize_pe_reproducibility_fields,
    prepare_generated,
    require_new_artifacts,
    sha256_file,
    write_new_file,
)


def synthetic_pe() -> bytes:
    data = bytearray(0x400)
    data[:2] = b"MZ"
    pe = 0x80
    struct.pack_into("<I", data, 0x3C, pe)
    data[pe : pe + 4] = b"PE\0\0"
    struct.pack_into("<H", data, pe + 4, 0x014C)
    struct.pack_into("<H", data, pe + 6, 1)
    struct.pack_into("<I", data, pe + 8, 0x12345678)
    struct.pack_into("<H", data, pe + 20, 0xE0)

    optional = pe + 24
    struct.pack_into("<H", data, optional, 0x10B)
    struct.pack_into("<II", data, optional + 96 + 6 * 8, 0x1000, 56)

    section = pe + 24 + 0xE0
    data[section : section + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", data, section + 8, 0x200, 0x1000, 0x200, 0x200)

    debug = 0x200
    struct.pack_into("<I", data, debug + 4, 0x87654321)
    struct.pack_into("<IIII", data, debug + 12, 2, 0x30, 0x1060, 0x260)
    reproducible = debug + 28
    struct.pack_into("<I", data, reproducible + 4, 0xAABBCCDD)
    struct.pack_into("<IIII", data, reproducible + 12, 16, 0, 0, 0)
    data[0x260:0x264] = b"RSDS"
    data[0x264:0x274] = bytes(range(16))
    data[0x274:0x278] = (1).to_bytes(4, "little")
    data[0x278:0x286] = b"runtime.pdb\0\0\0"
    return bytes(data)


class RuntimeBuildTests(unittest.TestCase):
    def test_normalization_is_idempotent_and_only_clears_provenance(self) -> None:
        source = synthetic_pe()
        normalized = normalize_pe_reproducibility_fields(source)
        self.assertEqual(normalized[0x88:0x8C], b"\0" * 4)
        self.assertEqual(normalized[0x204:0x208], b"\0" * 4)
        self.assertEqual(normalized[0x220:0x224], b"\0" * 4)
        self.assertEqual(normalized[0x264:0x274], b"\0" * 16)
        self.assertEqual(normalized[0x260:0x264], b"RSDS")
        self.assertEqual(normalized[0x274:0x286], source[0x274:0x286])
        changed = {
            index
            for index, (before, after) in enumerate(zip(source, normalized))
            if before != after
        }
        expected_changed = set(range(0x88, 0x8C))
        expected_changed.update(range(0x204, 0x208))
        expected_changed.update(range(0x220, 0x224))
        expected_changed.update(range(0x265, 0x274))
        self.assertEqual(changed, expected_changed)
        self.assertEqual(normalize_pe_reproducibility_fields(normalized), normalized)

    def test_non_pe_is_rejected(self) -> None:
        with self.assertRaisesRegex(BuildError, "not a DOS/PE image"):
            normalize_pe_reproducibility_fields(b"not a PE file")

    def test_manifest_inputs_cover_sources_headers_def_and_authorized_generated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            generated = Path(temporary) / "generated"
            prepare_generated(generated, authorized=True)
            rows = _manifest_inputs("pm", generated)

            by_path = {str(row["path"]): row for row in rows}
            self.assertIn("src/photon_combined_proxy.c", by_path)
            self.assertIn("src/photon_v6_pm_native_runtime.S", by_path)
            self.assertEqual(
                by_path["src/photon_v6_pf_native_runtime.c"]["kind"],
                "included_source",
            )
            self.assertIn("include/Ages3ResT.def", by_path)
            self.assertIn("include/photon_v6_runtime_api.h", by_path)
            self.assertIn("generated/photon_combined_pm.generated.h", by_path)
            self.assertEqual(
                by_path["generated/photon_combined_pm.generated.h"]["sha256"],
                sha256_file(generated / "photon_combined_pm.generated.h"),
            )
            self.assertNotEqual(
                by_path["generated/photon_combined_pm.generated.h"]["sha256"],
                sha256_file(GENERATED / "photon_combined_pm.generated.h"),
            )
            self.assertEqual(len(by_path), len(rows), "manifest paths must be unique")

    def test_portable_compile_command_has_complete_reproducible_contract(self) -> None:
        command = _compile_command(
            zig="zig",
            game="pf",
            generated="<authorized-generated>",
            output="<output>/Ages3ResT.dll",
            authorized=True,
            portable_paths=True,
        )
        rendered = " ".join(command)
        self.assertEqual(command[:4], ["zig", "cc", "-target", TARGET])
        self.assertIn("-std=c11", command)
        self.assertIn("-O2", command)
        self.assertIn("-DPHOTON_V6_PRODUCTION_AUTHORIZED=1", command)
        self.assertIn("src/photon_v6_pf_native_runtime.S", command)
        self.assertIn("include/Ages3ResT.def", command)
        self.assertIn("-lwindowscodecs", command)
        self.assertNotIn(str(ROOT), rendered)
        self.assertNotIn("\\", rendered)

    def test_build_report_records_compiler_and_complete_portable_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            zig = root / "zig.exe"
            zig.write_bytes(b"synthetic pinned zig executable")
            output = root / "Ages3ResT.dll"

            def fake_compile(**kwargs: object) -> subprocess.CompletedProcess[str]:
                candidate = kwargs["output"]
                assert isinstance(candidate, Path)
                candidate.write_bytes(synthetic_pe())
                return subprocess.CompletedProcess([], 0, stdout="", stderr="")

            version = subprocess.CompletedProcess(
                [str(zig), "version"],
                0,
                stdout="0.16.0\n",
                stderr="",
            )
            with patch("rUGP.runtime.build.compile_once", side_effect=fake_compile), patch(
                "rUGP.runtime.build.subprocess.run", return_value=version
            ):
                report = build(
                    zig=zig,
                    game="pf",
                    output=output,
                    authorized=True,
                    verify_release_code=False,
                )

            compiler = report["compiler"]
            compile_contract = report["compile"]
            inputs = report["inputs"]
            assert isinstance(compiler, dict)
            assert isinstance(compile_contract, dict)
            assert isinstance(inputs, list)
            self.assertEqual(report["schema"], "photon-runtime-build-v2")
            self.assertEqual(compiler["version"], "0.16.0")
            self.assertEqual(compiler["executable_sha256"], sha256_file(zig))
            self.assertEqual(compile_contract["target"], TARGET)
            self.assertIn("-Werror", compile_contract["flags"])
            command = " ".join(compile_contract["portable_command"])
            self.assertNotIn(str(root), command)
            self.assertNotIn(str(ROOT), command)
            kinds = {row["kind"] for row in inputs}
            self.assertTrue(
                {
                    "command_source",
                    "header",
                    "module_definition",
                    "generated_header",
                }.issubset(kinds)
            )
            self.assertTrue(report["sources_complete"])
            self.assertTrue(output.is_file())

    def test_runtime_outputs_are_exclusive_and_cannot_alias(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "Ages3ResT.dll"
            manifest = root / "Ages3ResT.build.json"
            require_new_artifacts((output, manifest))
            with self.assertRaisesRegex(BuildError, "different files"):
                require_new_artifacts((output, root / "." / "Ages3ResT.dll"))
            write_new_file(output, b"dll")
            with self.assertRaisesRegex(BuildError, "refusing to overwrite"):
                require_new_artifacts((output, manifest))
            with self.assertRaisesRegex(BuildError, "refusing to overwrite"):
                write_new_file(output, b"replacement")
            self.assertEqual(output.read_bytes(), b"dll")

    def test_write_new_file_publishes_only_complete_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "Ages3ResT.dll"
            payload = b"complete-runtime-payload"
            real_link = os.link

            def inspect_then_link(source: object, target: object) -> None:
                self.assertFalse(Path(target).exists())
                self.assertEqual(Path(source).read_bytes(), payload)
                real_link(source, target)

            with patch("rUGP.runtime.build.os.link", side_effect=inspect_then_link):
                write_new_file(output, payload)

            self.assertEqual(output.read_bytes(), payload)
            self.assertEqual([], list(output.parent.glob(f".{output.name}.*.tmp")))

    def test_build_rejects_and_removes_a_tampered_published_dll(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            zig = root / "zig.exe"
            zig.write_bytes(b"synthetic pinned zig executable")
            output = root / "Ages3ResT.dll"

            def fake_compile(**kwargs: object) -> subprocess.CompletedProcess[str]:
                candidate = kwargs["output"]
                assert isinstance(candidate, Path)
                candidate.write_bytes(synthetic_pe())
                return subprocess.CompletedProcess([], 0, stdout="", stderr="")

            def corrupt_publish(path: Path, payload: bytes) -> None:
                path.write_bytes(payload + b"tampered")

            version = subprocess.CompletedProcess(
                [str(zig), "version"], 0, stdout="0.16.0\n", stderr=""
            )
            with patch("rUGP.runtime.build.compile_once", side_effect=fake_compile), patch(
                "rUGP.runtime.build.subprocess.run", return_value=version
            ), patch("rUGP.runtime.build.write_new_file", side_effect=corrupt_publish):
                with self.assertRaisesRegex(BuildError, "no longer matches"):
                    build(
                        zig=zig,
                        game="pf",
                        output=output,
                        authorized=True,
                        verify_release_code=False,
                    )

            self.assertFalse(output.exists())

    def test_sealed_generated_configuration_has_exact_public_provenance(self) -> None:
        generated_root = ROOT / "generated"
        document = json.loads(
            (generated_root / "provenance.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            document["schema"], "photon-runtime-sealed-generated-provenance/v1"
        )
        self.assertFalse(document["public_regeneration_available"])
        actual = {
            path.name
            for path in generated_root.glob("*.h")
            if path.is_file()
        }
        self.assertEqual(set(document["headers"]), actual)
        for name, authority in document["headers"].items():
            payload = (generated_root / name).read_bytes()
            self.assertEqual(authority["bytes"], len(payload))
            self.assertEqual(
                authority["sha256"],
                hashlib.sha256(payload).hexdigest().upper(),
            )


if __name__ == "__main__":
    unittest.main()
