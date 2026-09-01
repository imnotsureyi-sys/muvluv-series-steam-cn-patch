#!/usr/bin/env python3
"""Build the fail-closed PF/PM x86 rUGP runtime from reviewed sources.

The checked-in configuration is pinned to the exact Steam executables, private
resource DLLs, fonts, and image identity tables used by the Photon Beta0.1
patches.  A normal build leaves runtime authorization disabled.  Passing
``--authorize-pinned-build`` only enables those already-pinned identities; it
does not make an arbitrary game build compatible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from typing import Iterable


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
INCLUDE = ROOT / "include"
GENERATED = ROOT / "generated"
TARGET = "x86-windows-gnu"
COMPILE_FLAGS = ("-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-shared")
LINK_LIBRARIES = ("advapi32", "user32", "gdi32", "windowscodecs", "ole32")

COMMON_SOURCES = (
    "photon_combined_proxy.c",
    "photon_font_policy.c",
    "photon_optional_runtime_bridge.c",
    "photon_v6_runtime_production.c",
    "photon_v6_cpu_surface_rgba.c",
    "photon_v6_exact_rgba_sidecar_loader.c",
    "photon_pf_decoder_surface_view.c",
    "photon_v6_surface_transaction.c",
    "photon_v6_internal_route_gate.c",
    "photon_v6_exact_overlay_core.c",
    "photon_v6_special57_sidecar_loader.c",
)

GAMES = {
    "pf": {
        "defines": (
            "PHOTON_BUILD_PF=1",
            "PHOTON_V6_PRODUCTION_PF=1",
            "PHOTON_V6_PF_SELECTOR_ADAPTER=1",
        ),
        "sources": (
            "photon_v6_pf_native_runtime.c",
            "photon_v6_pf_native_runtime.S",
            "photon_v6_pf_selector_adapter.c",
        ),
        "release_sha256": (
            "E886F746F937B53C712AB931BFB36889FEC5ADE7B426893EFE1E1EF44415C8DD"
        ),
        "release_normalized_sha256": (
            "01399562654A81C0458E269B143A9AB39B5F6892DE5B295DD0854B8A116AB1FA"
        ),
    },
    "pm": {
        "defines": (
            "PHOTON_BUILD_PM=1",
            "PHOTON_V6_PRODUCTION_PM=1",
            "PHOTON_V6_PM_SELECTOR_ADAPTER=1",
        ),
        "sources": (
            "photon_v6_pm_native_runtime.c",
            "photon_v6_pm_native_runtime.S",
            "photon_v6_pm_selector_adapter.c",
        ),
        "release_sha256": (
            "84C20D878CD440950D55585A5B6D9575138CD043F157DC46D7A19F548AAE2C40"
        ),
        "release_normalized_sha256": (
            "73F5EC68A374042096CB4C900210F22537E5706E49B7EA9A8F249C583039E2CD"
        ),
    },
}


class BuildError(RuntimeError):
    """Raised when an input or reproducibility invariant fails."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def require_new_artifacts(paths: Iterable[Path]) -> None:
    materialized = [Path(path) for path in paths]
    identities = [path.resolve(strict=False) for path in materialized]
    if len(identities) != len(set(identities)):
        raise BuildError("runtime output and build manifest must be different files")
    existing = [path for path in materialized if path.exists()]
    if existing:
        raise BuildError(f"refusing to overwrite existing artifact: {existing[0]}")


def write_new_file(path: Path, payload: bytes) -> None:
    """Publish a complete new file without ever replacing an existing path."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            # A same-filesystem hard link atomically exposes the already-fsynced
            # bytes and fails if another process created the destination first.
            os.link(temporary, path)
        except FileExistsError as exc:
            raise BuildError(f"refusing to overwrite existing artifact: {path}") from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _rva_to_file_offset(data: bytes, pe_offset: int, rva: int) -> int:
    section_count = struct.unpack_from("<H", data, pe_offset + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe_offset + 20)[0]
    section_table = pe_offset + 24 + optional_size
    for index in range(section_count):
        section = section_table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, section + 8
        )
        extent = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + extent:
            offset = raw_offset + (rva - virtual_address)
            if offset >= len(data):
                break
            return offset
    raise BuildError(f"PE RVA 0x{rva:08X} is not backed by a file section")


def normalize_pe_reproducibility_fields(data: bytes) -> bytes:
    """Clear linker provenance that varies with the temporary build path.

    The historical Zig/LLD command produces identical code and data but puts a
    path-dependent timestamp/build ID in the PE header, debug directory, and
    RSDS GUID.  These fields do not participate in runtime behaviour and the
    release does not ship a matching PDB.  Clearing them gives clean clones a
    byte-reproducible DLL and lets us compare its normalized hash with the
    shipped Beta0.1 binary.
    """

    result = bytearray(data)
    if len(result) < 0x40 or result[:2] != b"MZ":
        raise BuildError("runtime output is not a DOS/PE image")
    pe_offset = struct.unpack_from("<I", result, 0x3C)[0]
    if pe_offset + 24 > len(result) or result[pe_offset : pe_offset + 4] != b"PE\0\0":
        raise BuildError("runtime output has no valid PE signature")
    # IMAGE_FILE_HEADER.TimeDateStamp.
    result[pe_offset + 8 : pe_offset + 12] = b"\0" * 4

    optional = pe_offset + 24
    magic = struct.unpack_from("<H", result, optional)[0]
    if magic != 0x10B:
        raise BuildError(f"runtime output is not PE32: magic=0x{magic:04X}")
    debug_rva, debug_size = struct.unpack_from("<II", result, optional + 96 + 6 * 8)
    if not debug_rva or not debug_size or debug_size % 28:
        raise BuildError("runtime output has no canonical PE debug directory")
    debug_offset = _rva_to_file_offset(result, pe_offset, debug_rva)
    if debug_offset + debug_size > len(result):
        raise BuildError("PE debug directory is truncated")
    codeview_count = 0
    for entry in range(debug_offset, debug_offset + debug_size, 28):
        result[entry + 4 : entry + 8] = b"\0" * 4
        kind, size, _address, pointer = struct.unpack_from("<IIII", result, entry + 12)
        if kind != 2:
            continue
        if pointer + size > len(result) or result[pointer : pointer + 4] != b"RSDS":
            raise BuildError("PE CodeView record is missing or truncated")
        result[pointer + 4 : pointer + 20] = b"\0" * 16
        codeview_count += 1
    if codeview_count != 1:
        raise BuildError(f"expected one CodeView record, found {codeview_count}")
    return bytes(result)


def require_files(paths: Iterable[Path]) -> None:
    missing = [path.relative_to(ROOT).as_posix() for path in paths if not path.is_file()]
    if missing:
        raise BuildError(f"missing runtime sources: {', '.join(missing)}")


def prepare_generated(destination: Path, authorized: bool) -> None:
    shutil.copytree(GENERATED, destination)
    for game in ("pf", "pm"):
        path = destination / f"photon_combined_{game}.generated.h"
        data = path.read_bytes()
        disabled = b"#define PHOTON_V6_RUNTIME_AUTHORIZED 0u"
        enabled = b"#define PHOTON_V6_RUNTIME_AUTHORIZED 1u"
        if data.count(disabled) != 1 or enabled in data:
            raise BuildError(f"authorization precondition drift: {path.name}")
        if authorized:
            path.write_bytes(data.replace(disabled, enabled))


def _command_sources(game: str) -> list[Path]:
    """Return the source files passed to Zig, in command-line order."""

    return [SRC / str(name) for name in (*COMMON_SOURCES, *GAMES[game]["sources"])]


def _manifest_inputs(game: str, generated: Path) -> list[dict[str, object]]:
    """Describe every repository-controlled input to the selected build.

    Headers are deliberately recorded as a complete include-root snapshot.  A
    number of the runtime's includes are selected by preprocessor branches, so
    recording only lexically visible includes would make the manifest depend on
    an incomplete home-grown preprocessor.  The command-line sources and module
    definition are marked separately from that conservative header closure.
    Generated headers are hashed from the temporary, authorization-adjusted
    copy that the compiler actually sees.
    """

    command_sources = _command_sources(game)
    rows: list[tuple[str, Path, str]] = []
    rows.extend(
        (path.relative_to(ROOT).as_posix(), path, "command_source")
        for path in command_sources
    )

    # PM compiles this file through a source-level include in
    # photon_v6_pm_native_runtime.c, rather than as a separate command token.
    if game == "pm":
        indirect = SRC / "photon_v6_pf_native_runtime.c"
        rows.append((indirect.relative_to(ROOT).as_posix(), indirect, "included_source"))

    definition = INCLUDE / "Ages3ResT.def"
    rows.append((definition.relative_to(ROOT).as_posix(), definition, "module_definition"))
    rows.extend(
        (path.relative_to(ROOT).as_posix(), path, "header")
        for path in sorted(INCLUDE.rglob("*.h"))
    )
    rows.extend(
        (f"generated/{path.name}", path, "generated_header")
        for path in sorted(generated.rglob("*.h"))
    )
    require_files(path for _logical, path, _role in rows)
    return [
        {
            "path": logical,
            "kind": role,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for logical, path, role in rows
    ]


def _compile_command(
    *,
    zig: str,
    game: str,
    generated: str,
    output: str,
    authorized: bool,
    portable_paths: bool,
) -> list[str]:
    config = GAMES[game]
    if portable_paths:
        sources = [path.relative_to(ROOT).as_posix() for path in _command_sources(game)]
        include = "include"
        definition = "include/Ages3ResT.def"
    else:
        sources = [str(path) for path in _command_sources(game)]
        include = str(INCLUDE)
        definition = str(INCLUDE / "Ages3ResT.def")
    return [
        zig,
        "cc",
        "-target",
        TARGET,
        *COMPILE_FLAGS[:-1],
        "-I",
        generated,
        "-I",
        include,
        *(f"-D{name}" for name in config["defines"]),
        f"-DPHOTON_V6_PRODUCTION_AUTHORIZED={int(authorized)}",
        COMPILE_FLAGS[-1],
        "-o",
        output,
        *sources,
        definition,
        *(f"-l{name}" for name in LINK_LIBRARIES),
    ]


def compile_once(
    *, zig: Path, game: str, generated: Path, output: Path, authorized: bool
) -> subprocess.CompletedProcess[str]:
    sources = _command_sources(game)
    require_files((*sources, INCLUDE / "Ages3ResT.def"))
    command = _compile_command(
        zig=str(zig),
        game=game,
        generated=str(generated),
        output=str(output),
        authorized=authorized,
        portable_paths=False,
    )
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


def build(
    *, zig: Path, game: str, output: Path, authorized: bool, verify_release_code: bool
) -> dict[str, object]:
    zig = zig.resolve(strict=True)
    compiler_bytes = zig.stat().st_size
    compiler_sha256 = sha256_file(zig)
    version = subprocess.run(
        [str(zig), "version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    if zig.stat().st_size != compiler_bytes or sha256_file(zig) != compiler_sha256:
        raise BuildError("Zig executable changed while its identity was recorded")
    output = output.resolve(strict=False)
    require_new_artifacts((output,))
    manifest_inputs: list[dict[str, object]]
    with tempfile.TemporaryDirectory(prefix="photon-runtime-") as temporary:
        temp = Path(temporary)
        generated = temp / "generated"
        prepare_generated(generated, authorized)
        manifest_inputs = _manifest_inputs(game, generated)
        candidate = temp / "Ages3ResT.dll"

        first = compile_once(
            zig=zig, game=game, generated=generated, output=candidate,
            authorized=authorized,
        )
        if first.returncode != 0:
            raise BuildError(first.stderr or first.stdout or "first compile failed")
        first_raw = candidate.read_bytes()
        first_bytes = normalize_pe_reproducibility_fields(first_raw)
        candidate.unlink()

        second = compile_once(
            zig=zig, game=game, generated=generated, output=candidate,
            authorized=authorized,
        )
        if second.returncode != 0:
            raise BuildError(second.stderr or second.stdout or "second compile failed")
        second_raw = candidate.read_bytes()
        second_bytes = normalize_pe_reproducibility_fields(second_raw)
        if first_bytes != second_bytes:
            raise BuildError("two normalized clean compiles produced different DLL bytes")
        if _manifest_inputs(game, generated) != manifest_inputs:
            raise BuildError("runtime source inputs changed during compilation")
        if zig.stat().st_size != compiler_bytes or sha256_file(zig) != compiler_sha256:
            raise BuildError("Zig executable changed during compilation")

        digest = sha256_bytes(second_bytes)
        expected = str(GAMES[game]["release_normalized_sha256"])
        if verify_release_code and (not authorized or digest != expected):
            raise BuildError(
                "historical release-code verification requires an authorized build; "
                f"expected {expected}, got {digest}"
            )
        published_by_this_build = False
        try:
            write_new_file(output, second_bytes)
            published_by_this_build = True
            final_bytes = output.read_bytes()
            if (
                final_bytes != second_bytes
                or len(final_bytes) != len(second_bytes)
                or sha256_bytes(final_bytes) != digest
            ):
                raise BuildError(
                    "published runtime DLL no longer matches the verified build candidate"
                )
        except Exception:
            if published_by_this_build:
                try:
                    output.unlink()
                except FileNotFoundError:
                    pass
            raise

    portable_command = _compile_command(
        zig="zig",
        game=game,
        generated="<authorized-generated>",
        output="<output>/Ages3ResT.dll",
        authorized=authorized,
        portable_paths=True,
    )
    return {
        "schema": "photon-runtime-build-v2",
        "game": game,
        "target": TARGET,
        "zig_version": version,
        "compiler": {
            "name": "zig",
            "version": version,
            "executable_bytes": compiler_bytes,
            "executable_sha256": compiler_sha256,
        },
        "compile": {
            "working_directory": "rUGP/runtime",
            "target": TARGET,
            "flags": list(COMPILE_FLAGS),
            "defines": [
                *GAMES[game]["defines"],
                f"PHOTON_V6_PRODUCTION_AUTHORIZED={int(authorized)}",
            ],
            "include_roots": ["<authorized-generated>", "include"],
            "link_libraries": list(LINK_LIBRARIES),
            "portable_command": portable_command,
        },
        "authorization_compiled": authorized,
        "deterministic_double_compile_after_pe_normalization": True,
        "historical_release": {
            "raw_sha256": GAMES[game]["release_sha256"],
            "normalized_sha256": GAMES[game]["release_normalized_sha256"],
            "normalized_code_verified": verify_release_code,
        },
        "inputs": manifest_inputs,
        "sources_complete": True,
        "output": {
            "path": output.name,
            "bytes": len(second_bytes),
            "sha256": digest,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", choices=sorted(GAMES), required=True)
    parser.add_argument("--zig", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--authorize-pinned-build", action="store_true")
    parser.add_argument(
        "--verify-release-code",
        action="store_true",
        help=(
            "require the normalized Beta0.1 DLL hash; the historical raw hash "
            "contains path-dependent PE/PDB provenance"
        ),
    )
    args = parser.parse_args()
    output = args.output.resolve(strict=False)
    manifest = (
        args.manifest.resolve(strict=False)
        if args.manifest is not None
        else output.with_suffix(".build.json")
    )
    require_new_artifacts((output, manifest))
    report = build(
        zig=args.zig,
        game=args.game,
        output=output,
        authorized=args.authorize_pinned_build,
        verify_release_code=args.verify_release_code,
    )
    try:
        write_new_file(
            manifest,
            (
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8"),
        )
    except Exception:
        # build() proved the DLL did not exist before this invocation, so only
        # the artifact created by this attempt is removed here.
        try:
            output.unlink()
        except FileNotFoundError:
            pass
        raise
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
