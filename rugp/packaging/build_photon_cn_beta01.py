#!/usr/bin/env python3
"""Build PF/PM Beta0.1 full Chinese patches installable on exact clean Steam copies.

The package contains byte-exact block deltas from the sealed clean RIO/ICI cache
to the currently approved live game state, plus the complete font/image runtime.
PF and PM are emitted as separate, deliberately simple test packages.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath, PureWindowsPath
import platform
import shutil
from typing import Any, BinaryIO
import zipfile
import zlib

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path()
CLEAN = Path()
SEALED = Path()
STOCK_FIXED = Path()
INSTALLER_TEMPLATE = ROOT / "rugp/packaging/windows/Install-PhotonCN-Full-Beta01.ps1"
BUILD_TIME = dt.datetime.fromtimestamp(0, tz=dt.timezone.utc)
BUILD_EPOCH = 315532800  # 1980-01-01, the earliest ZIP timestamp.

CLEAN_MANIFEST_SHA256 = "A032C40B48550E8235A78A1D6A3EC007F72F78A704E9B9BF11AA8091936744EF"
CLEAN_SEAL_SHA256 = "B1D43BF17900411DE029F8A8AF234D959096F819FE1750022896BC68219847A4"
SEALED_MANIFEST_SHA256 = "62A6D142C08342165FA9B5B206A9313E2E7FE95E05AACEE1DE108FCEA38A5C9F"
RESOURCE_INDEX_SHA256 = "A020B6F4CB5B1D58D3BAB058850ADB175AADB28279CEE5A818E0C03EA250E1AF"

BLOCK_SIZE = 64 * 1024
OUTER_SIZE = 64 * 1024 * 1024
MERGE_GAP = BLOCK_SIZE
COPY_SIZE = 8 * 1024 * 1024

RUNTIME_DLL_TARGET = "Ages3ResT.dll"
RUNTIME_DLL_IDENTITY_POLICY = "photon-runtime-dll-controlled-identity/v1"
# Applying rugp/runtime/build.py's declared PE/PDB normalization to each
# historical raw DLL produces the corresponding normalized identity exactly.
RUNTIME_DLL_IDENTITIES: dict[str, dict[str, dict[str, int | str]]] = {
    "PF": {
        "historical_raw_beta01": {
            "bytes": 617472,
            "sha256": "E886F746F937B53C712AB931BFB36889FEC5ADE7B426893EFE1E1EF44415C8DD",
        },
        "clean_clone_normalized": {
            "bytes": 617472,
            "sha256": "01399562654A81C0458E269B143A9AB39B5F6892DE5B295DD0854B8A116AB1FA",
        },
    },
    "PM": {
        "historical_raw_beta01": {
            "bytes": 582144,
            "sha256": "84C20D878CD440950D55585A5B6D9575138CD043F157DC46D7A19F548AAE2C40",
        },
        "clean_clone_normalized": {
            "bytes": 582144,
            "sha256": "73F5EC68A374042096CB4C900210F22537E5706E49B7EA9A8F249C583039E2CD",
        },
    },
}


GAMES: dict[str, dict[str, Any]] = {
    "PF": {
        "slug": "photonflowers",
        "title": "Muv-Luv photonflowers",
        "process": "Muv-Luv_PF",
        "exe": "Muv-Luv_PF.exe",
        "live": None,
        "clean_dir": "pf",
        "stock_dir": "pf",
        "sidecars": 1082,
        "archives": [
            ("photonflowers11.rio", 2147465920, "277D2956EA7075AC0EF069E7201B30F77FCFAD66BA33BB53DCD282412E0407CA", 2147465920, "78C8621AD61BDCC939EC1C404DBA6B3BCE7D3411F89A0A1EC4A7FBECBB863A0F"),
            ("photonflowers11.rio.002", 1661470956, "6EB65A055CC880374F7EFD549A70439F957F3A75E283E0B06E86B39601227AC3", 1684696824, "C6C005A9CB8F3A03886CE1E86840FBC62539ADE0C6589AB43341E70F5202FE22"),
            ("photonflowers11.rio.ici", 10888, "EB234685AAA065288BE98BE65867C032D6384306EB3B1228707A2EAB24A8E3CE", 10888, "BB2C69AAFD4FAB3105FEAA6A76913208B87284CCD531578D11C1E2ABDA164A94"),
        ],
        "fixed": [
            ("Muv-Luv_PF.exe", True, 3172352, "6A9D1879DD64B5CF569C2767C72AD9F2E700415FEDF496E50B4CF6256B759242", 3172352, "7AD7399624AA9C35CED57B39D68A02F8BD20B188BA4649F43FF9419845DA5B08"),
            ("ages_screenSv.dll", True, 137216, "B5F1CAC0FD925A302AFE93D76DAA271A47D3BB467F73B649D8BCEFD5BB54E15C", 137216, "6BF8300B5EAC07B39F67BF5C1F32D337935E5606CE2EAD3BF1C2B001929DF0C6"),
            ("Ages3ResT.dll", True, 15360, "46CAD3A7CD9A25F9E7F8F15548C7D1431C2538E23C70CF57BA5EB3877CFA3A36", 617472, RUNTIME_DLL_IDENTITIES["PF"]["historical_raw_beta01"]["sha256"]),
            ("Ages3ResT.PhotonR2.private.dll", False, 0, None, 15360, "022079515CB9856B8A2ED452535C939EE410DABF805A5B505D18A0E711AEFB7D"),
            ("PhotonR2-Regular.ttf", False, 0, None, 1406624, "AADF895003AE6452E1FBDCA1B64206B77D6F9A6EEBE226C31D46D1247AD4830B"),
            ("PhotonR2-OFL.txt", False, 0, None, 4538, "064FC5AC196B84AAC8DB9F9AA37C370660A07231F6B2D112E8B37AFDD8256DDC"),
            ("photonflowers11.rio.ruo1", False, 0, None, 1896084, "A8E33D4F6F9C31A4295DC0FE20923ED4397E251DB1FB70C390095E0C965C7ED3"),
        ],
        "asset_counts": {"context": 14, "owner-records": 17, "payload": 17},
    },
    "PM": {
        "slug": "photonmelodies",
        "title": "Muv-Luv photonmelodies",
        "process": "Muv-Luv_PM",
        "exe": "Muv-Luv_PM.exe",
        "live": None,
        "clean_dir": "pm",
        "stock_dir": "pm",
        "sidecars": 1475,
        "archives": [
            ("photonmelodies11.rio", 1913545000, "1EC6D01E0393D72BB5E36D5246B282C2280CDA122F90AE7627DE51D3C556694E", 1913545000, "23367361DA990FF951DC165B6693C13A888A7209B4672187AD8E66DAFBFF69F3"),
            ("photonmelodies11.rio.002", 1903007556, "284B9DF442735BD1EEB0BC37C9FFFDE17E8C447E1252B46EBB7CAF63D021EDA7", 1903007556, "8A995CAB6A8075A291BB2340E9772FA219A41643635527B2EDEFC6FDA5639EAF"),
            ("photonmelodies11.rio.003", 2121421700, "4FC4A5699D3A0D44863D7D001EF1B9420DD9C19D89CC6896F922F2B735587D64", 2121421700, "D75F15E0AE1ECF310AE42E1D8D6E48BCDA15E2D440C923A7F19622E52A394B78"),
            ("photonmelodies11.rio.004", 1848048356, "94CBE4F5BDF1CE22E83CC194F5CB0C644EAA2D2E91B68BC4C7BC00B69CB6A2B6", 1883168284, "4C58442241705492F8B4F12BD188708AC7A3FE9E6C767B21AAE6BC276EA37E74"),
            ("photonmelodies11.rio.ici", 19592, "B8E12995826857DC124290D8335134095F5FA6D0486C18AFEA62BC28EC7EEBFE", 19592, "6EC04A1DD6C493A0C14985722241A17DFE876D957C75B31986ECA5E5EE4DF2A6"),
        ],
        "fixed": [
            ("Muv-Luv_PM.exe", True, 3198464, "718279989451307CF01010CE14C49F3AC9B330EA38BEBEA6C5ACCA839438AD30", 3198464, "8E442F263FEED7B79E5CCB83C3F26B12CC12E1953FB4A262B4BB74017D6E26B8"),
            ("ages_screenSv.dll", True, 137216, "B5F1CAC0FD925A302AFE93D76DAA271A47D3BB467F73B649D8BCEFD5BB54E15C", 137216, "6BF8300B5EAC07B39F67BF5C1F32D337935E5606CE2EAD3BF1C2B001929DF0C6"),
            ("Ages3ResT.dll", True, 15360, "46CAD3A7CD9A25F9E7F8F15548C7D1431C2538E23C70CF57BA5EB3877CFA3A36", 582144, RUNTIME_DLL_IDENTITIES["PM"]["historical_raw_beta01"]["sha256"]),
            ("Ages3ResT.PhotonR2.private.dll", False, 0, None, 244224, "5991C0170B7AB71CFB661D53D15CD5A1CB616BB62695DBC02E97756BB961A4AE"),
            ("Ages3ResT.PhotonR2.official.dll", False, 0, None, 15360, "022079515CB9856B8A2ED452535C939EE410DABF805A5B505D18A0E711AEFB7D"),
            ("PhotonR2-Regular.ttf", False, 0, None, 1459472, "7D555D9B2905A56A8E97D0C2CFF4CC12559013DD8BCBFF41DC254D5C74ACE8E2"),
            ("PhotonR2-OFL.txt", False, 0, None, 4538, "064FC5AC196B84AAC8DB9F9AA37C370660A07231F6B2D112E8B37AFDD8256DDC"),
        ],
        "asset_counts": {"context": 33, "owner-records": 37, "payload": 40},
    },
}


class BuildError(RuntimeError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise BuildError(message)


def parse_source_date_epoch(value: str) -> int:
    """Parse an explicit reproducible-build epoch accepted by ZIP tooling."""

    try:
        epoch = int(value, 10)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("SOURCE_DATE_EPOCH must be an integer") from exc
    if not 0 <= epoch <= 4_354_819_198:
        raise argparse.ArgumentTypeError(
            "SOURCE_DATE_EPOCH must be between 0 and 4354819198"
        )
    return epoch


def build_toolchain_identity() -> dict[str, str]:
    """Record versions that can affect manifests, deltas or ZIP bytes."""

    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy": np.__version__,
        "zlib_compile": zlib.ZLIB_VERSION,
        "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
    }


def sha256(path: Path, chunk_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_range(path: Path, offset: int, length: int) -> str:
    digest = hashlib.sha256()
    remaining = length
    with path.open("rb") as stream:
        stream.seek(offset)
        while remaining:
            block = stream.read(min(COPY_SIZE, remaining))
            need(bool(block), f"unexpected EOF while hashing range: {path}")
            digest.update(block)
            remaining -= len(block)
    return digest.hexdigest().upper()


def verify_file(path: Path, size: int, digest: str, label: str) -> None:
    need(path.is_file(), f"missing {label}: {path}")
    need(path.stat().st_size == size, f"size drift for {label}: {path}")
    need(sha256(path) == digest, f"hash drift for {label}: {path}")


def select_runtime_dll_identity(path: Path, game: str) -> dict[str, Any]:
    """Select one exact, reviewed identity for the game's runtime proxy DLL.

    This is deliberately narrower than the normal fixed-file verifier.  Only
    ``Ages3ResT.dll`` has two accepted representations: the historical Beta0.1
    binary and the byte-reproducible clean-clone output whose PE/PDB provenance
    fields were normalized by ``rugp/runtime/build.py``.
    """

    need(game in RUNTIME_DLL_IDENTITIES, f"no runtime DLL identity policy for {game}")
    need(path.is_file(), f"final runtime DLL missing: {path}")
    actual_size = path.stat().st_size
    actual_hash = sha256(path)
    matches = [
        name
        for name, identity in RUNTIME_DLL_IDENTITIES[game].items()
        if actual_size == int(identity["bytes"])
        and actual_hash == str(identity["sha256"])
    ]
    need(
        len(matches) == 1,
        f"unapproved runtime DLL identity for {game}: {path}",
    )
    return {
        "policy": RUNTIME_DLL_IDENTITY_POLICY,
        "selected": matches[0],
        "bytes": actual_size,
        "sha256": actual_hash,
    }


def write_json(path: Path, value: Any) -> None:
    assert_no_absolute_paths(value, path.name)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def assert_no_absolute_paths(value: Any, label: str = "manifest") -> None:
    """Reject workstation paths before they can leak into public artifacts."""

    if isinstance(value, dict):
        for key, child in value.items():
            assert_no_absolute_paths(child, f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_absolute_paths(child, f"{label}[{index}]")
    elif isinstance(value, str):
        need(
            not PureWindowsPath(value).is_absolute()
            and not PurePosixPath(value).is_absolute(),
            f"absolute workstation path in {label}: {value}",
        )


def build_deterministic_zip(package: Path, archive: Path) -> None:
    """Write a path-sorted ZIP with one SOURCE_DATE_EPOCH timestamp."""

    timestamp = dt.datetime.fromtimestamp(max(BUILD_EPOCH, 315532800), tz=dt.timezone.utc)
    date_time = (
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second - timestamp.second % 2,
    )
    files = sorted(
        (path for path in package.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(OUTPUT).as_posix().casefold(),
    )
    with zipfile.ZipFile(
        archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=5
    ) as bundle:
        for source in files:
            relative = source.relative_to(OUTPUT).as_posix()
            info = zipfile.ZipInfo(relative, date_time=date_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with source.open("rb") as reader, bundle.open(info, "w") as writer:
                shutil.copyfileobj(reader, writer, length=COPY_SIZE)
    with zipfile.ZipFile(archive, "r") as bundle:
        bad = bundle.testzip()
    need(bad is None, f"ZIP CRC failed: {bad}")


def artifact(path: Path, relative_to: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(relative_to).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def merge_range(ranges: list[list[int]], start: int, end: int) -> None:
    if ranges and start - ranges[-1][1] <= MERGE_GAP:
        ranges[-1][1] = end
    else:
        ranges.append([start, end])


def scan_changed_ranges(before: Path, after: Path, label: str) -> list[list[int]]:
    before_size = before.stat().st_size
    after_size = after.stat().st_size
    common = min(before_size, after_size)
    ranges: list[list[int]] = []
    position = 0
    next_report = 512 * 1024 * 1024
    with before.open("rb") as left, after.open("rb") as right:
        while position < common:
            wanted = min(OUTER_SIZE, common - position)
            a = left.read(wanted)
            b = right.read(wanted)
            need(len(a) == wanted and len(b) == wanted, f"short read while scanning {label}")
            full = (wanted // BLOCK_SIZE) * BLOCK_SIZE
            if full:
                av = np.frombuffer(a, dtype=np.uint8, count=full).reshape(-1, BLOCK_SIZE)
                bv = np.frombuffer(b, dtype=np.uint8, count=full).reshape(-1, BLOCK_SIZE)
                changed = np.flatnonzero(np.any(av != bv, axis=1))
                for index in changed.tolist():
                    start = position + index * BLOCK_SIZE
                    merge_range(ranges, start, start + BLOCK_SIZE)
            if full < wanted and a[full:] != b[full:]:
                merge_range(ranges, position + full, position + wanted)
            position += wanted
            if position >= next_report:
                print(f"  {label}: scanned {position / (1024**3):.2f} / {common / (1024**3):.2f} GiB", flush=True)
                next_report += 512 * 1024 * 1024
    if after_size > common:
        merge_range(ranges, common, after_size)
    need(after_size >= before_size, f"unsupported shrink for {label}")
    need(ranges, f"no differences found for {label}")
    return ranges


def copy_range(source: BinaryIO, destination: BinaryIO, length: int, digest: hashlib._Hash | None = None) -> None:
    remaining = length
    while remaining:
        block = source.read(min(COPY_SIZE, remaining))
        need(bool(block), "unexpected EOF while copying range")
        destination.write(block)
        if digest is not None:
            digest.update(block)
        remaining -= len(block)


def make_patch(before: Path, after: Path, patch_path: Path, label: str) -> dict[str, Any]:
    print(f"Scanning clean -> final delta: {label}", flush=True)
    ranges = scan_changed_ranges(before, after, label)
    patch_path.parent.mkdir(parents=True, exist_ok=True)
    segments: list[dict[str, Any]] = []
    patch_digest = hashlib.sha256()
    patch_offset = 0
    with after.open("rb") as source, patch_path.open("xb") as output:
        for start, end in ranges:
            length = end - start
            source.seek(start)
            segment_digest = hashlib.sha256()
            remaining = length
            while remaining:
                block = source.read(min(COPY_SIZE, remaining))
                need(bool(block), f"unexpected final EOF for {label}")
                output.write(block)
                patch_digest.update(block)
                segment_digest.update(block)
                remaining -= len(block)
            segments.append(
                {
                    "offset": start,
                    "length": length,
                    "patch_offset": patch_offset,
                    "sha256": segment_digest.hexdigest().upper(),
                }
            )
            patch_offset += length
    before_size = before.stat().st_size
    for segment in segments:
        offset = int(segment["offset"])
        length = int(segment["length"])
        before_length = min(length, max(0, before_size - offset))
        segment["before_length"] = before_length
        segment["before_sha256"] = sha256_range(before, offset, before_length)
    need(patch_path.stat().st_size == patch_offset, f"patch size drift for {label}")
    need(sha256(patch_path) == patch_digest.hexdigest().upper(), f"patch hash drift for {label}")
    print(f"  {label}: {len(segments)} segments, {patch_offset / (1024**2):.2f} MiB", flush=True)
    return {
        "segments": segments,
        "patch": {
            "path": patch_path.as_posix(),
            "bytes": patch_offset,
            "sha256": patch_digest.hexdigest().upper(),
        },
    }


def hash_virtual_apply(before: Path, patch: Path, segments: list[dict[str, Any]], after_size: int) -> str:
    digest = hashlib.sha256()
    cursor = 0
    with before.open("rb") as clean, patch.open("rb") as delta:
        for segment in segments:
            offset = int(segment["offset"])
            length = int(segment["length"])
            need(offset >= cursor, "overlapping patch segments")
            unchanged = offset - cursor
            if unchanged:
                clean.seek(cursor)
                copy_range(clean, _HashWriter(digest), unchanged)
            delta.seek(int(segment["patch_offset"]))
            copy_range(delta, _HashWriter(digest), length)
            cursor = offset + length
        if cursor < after_size:
            need(after_size <= before.stat().st_size, "unpatched appended tail")
            clean.seek(cursor)
            copy_range(clean, _HashWriter(digest), after_size - cursor)
    return digest.hexdigest().upper()


class _HashWriter:
    def __init__(self, digest: Any) -> None:
        self.digest = digest

    def write(self, value: bytes) -> int:
        self.digest.update(value)
        return len(value)


def load_and_verify_authorities() -> dict[str, Any]:
    need(INSTALLER_TEMPLATE.is_file(), "full installer template missing")
    need(sha256(CLEAN / "manifest.v1.json") == CLEAN_MANIFEST_SHA256, "clean cache manifest drift")
    need(sha256(CLEAN / "seal.v1.json") == CLEAN_SEAL_SHA256, "clean cache seal drift")
    need(sha256(SEALED / "package_manifest.v9.json") == SEALED_MANIFEST_SHA256, "sealed latest runtime drift")
    source = json.loads((SEALED / "package_manifest.v9.json").read_text(encoding="utf-8"))
    need(source["status"] == "PASS_LATEST_V9_GROUP_TEST_PACKAGE_SEALED", "latest runtime source is not sealed")
    need(int(source["counts"]["runtime_identities"]) == 2557, "latest sidecar census drift")
    for row in source["payload_files"]:
        path = SEALED / row["path"]
        verify_file(path, int(row["bytes"]), str(row["sha256"]).upper(), f"sealed payload {row['path']}")
    return source


def copy_final_file(
    source: Path,
    target: str,
    data: Path,
    category: str,
    before: dict[str, Any],
    expected_after_size: int | None = None,
    expected_after_hash: str | None = None,
) -> dict[str, Any]:
    need(source.is_file(), f"final source missing: {source}")
    if expected_after_size is not None:
        verify_file(source, expected_after_size, str(expected_after_hash), f"approved final {target}")
    normalized = target.replace("\\", "/")
    destination = data / "files" / Path(normalized)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    payload = artifact(destination, data)
    if expected_after_hash is not None:
        need(payload["sha256"] == expected_after_hash, f"copied final hash drift: {target}")
    return {"target": normalized, "category": category, "before": before, "payload": payload}


def copy_controlled_runtime_dll(
    source: Path,
    target: str,
    data: Path,
    category: str,
    before: dict[str, Any],
    game: str,
) -> dict[str, Any]:
    """Copy the one fixed file governed by the dual runtime identity policy."""

    need(target == RUNTIME_DLL_TARGET, f"runtime DLL policy cannot cover {target}")
    identity = select_runtime_dll_identity(source, game)
    row = copy_final_file(
        source,
        target,
        data,
        category,
        before,
        int(identity["bytes"]),
        str(identity["sha256"]),
    )
    row["runtime_identity"] = identity
    return row


def make_launcher() -> str:
    return r'''[CmdletBinding()]
param([ValidateSet('Install', 'Rollback')][string]$Action = 'Install')
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'Install-PhotonCN-Full-Beta01.ps1'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    try {
        $line = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -Action {1}' -f $PSCommandPath.Replace('"', '""'), $Action
        $process = Start-Process powershell.exe -Verb RunAs -Wait -PassThru -ArgumentList $line
        exit $process.ExitCode
    } catch {
        Write-Error '未获得管理员权限，补丁没有写入。'
        exit 1
    }
}
& $installer -Action $Action -Apply
$code = $LASTEXITCODE
Write-Host ''
if ($code -eq 0) { Write-Host '操作完成。' -ForegroundColor Green } else { Write-Host '操作失败，请截图保留这个窗口。' -ForegroundColor Red }
[void](Read-Host '按回车键关闭')
exit $code
'''


def make_readme(meta: dict[str, Any]) -> str:
    return f"""{meta['title']} 完整汉化补丁 Beta0.1（群测版）

安装：
1. 先关闭游戏。
2. 双击“安装补丁.cmd”，允许管理员权限。
3. 等待窗口显示“操作完成”。大型数据校验需要一些时间，请不要中途关闭。

卸载：
双击“卸载补丁.cmd”，会按安装记录精确恢复 Steam 纯净版。

说明：
- 这是从 Steam 纯净版直接安装的完整汉化包，不依赖任何旧补丁。
- 安装器会自动寻找 {meta['title']}，并在写入前核对纯净版哈希。
- “校验补丁包完整性”阶段会显示文件数量和百分比，较慢电脑可能需要几分钟。
- PF 与 PM 请一次只安装一个；新版会阻止两个安装器同时争用硬盘。
- 大型 RIO 只核对实际会改动的区段，不再把数 GB 文件在安装前后各完整读取一遍。
- 卸载只使用已封存的安装记录和备份，不再重复校验整份补丁包。
- 已装好同一 Beta0.1 时可重复运行，不会重复修改。
- 文件版本不符时会在写入前停止；请把完整报错窗口截图发给制作者。
- 请勿混用 photonflowers 与 photonmelodies 的补丁包。

本次真正完成纯净版安装、卸载还原和重新解包校验后，才正式命名为 Beta0.1。
"""


def build_game(source_manifest: dict[str, Any], game: str) -> dict[str, Any]:
    meta = GAMES[game]
    live = meta.get("live")
    need(isinstance(live, Path), f"final {game} root was not configured")
    folder_name = f"Muv-Luv {meta['slug']} 汉化补丁 Beta0.1"
    package = OUTPUT / folder_name
    data = package / "data"
    package.mkdir(parents=True)
    data.mkdir()

    archive_rows: list[dict[str, Any]] = []
    for name, before_size, before_hash, after_size, after_hash in meta["archives"]:
        clean = CLEAN / meta["clean_dir"] / name
        final = live / name
        verify_file(clean, before_size, before_hash, f"clean {game} {name}")
        verify_file(final, after_size, after_hash, f"final {game} {name}")
        patch_path = data / "patches" / f"{name}.blockdelta.bin"
        generated = make_patch(clean, final, patch_path, f"{game}/{name}")
        generated["patch"]["path"] = patch_path.relative_to(data).as_posix()
        virtual = hash_virtual_apply(clean, patch_path, generated["segments"], after_size)
        need(virtual == after_hash, f"virtual apply hash mismatch: {game}/{name}")
        archive_rows.append(
            {
                "target": name,
                "before": {"bytes": before_size, "sha256": before_hash},
                "after": {"bytes": after_size, "sha256": after_hash},
                "patch": generated["patch"],
                "segments": generated["segments"],
                "virtual_apply_sha256": virtual,
            }
        )

    files: list[dict[str, Any]] = []
    targets: set[str] = set()
    stock = STOCK_FIXED / meta["stock_dir"]
    for target, before_exists, before_size, before_hash, after_size, after_hash in meta["fixed"]:
        if before_exists:
            verify_file(stock / target, before_size, str(before_hash), f"stock fixed {game}/{target}")
            before = {"exists": True, "bytes": before_size, "sha256": before_hash}
        else:
            before = {"exists": False}
        if target == RUNTIME_DLL_TARGET:
            historical = RUNTIME_DLL_IDENTITIES[game]["historical_raw_beta01"]
            need(
                after_size == int(historical["bytes"])
                and after_hash == str(historical["sha256"]),
                f"historical runtime DLL authority drift for {game}",
            )
            row = copy_controlled_runtime_dll(
                live / target, target, data, "fixed", before, game
            )
        else:
            row = copy_final_file(
                live / target,
                target,
                data,
                "fixed",
                before,
                after_size,
                after_hash,
            )
        need(row["target"].casefold() not in targets, f"duplicate target: {target}")
        targets.add(row["target"].casefold())
        files.append(row)

    live_v6 = live / "PhotonR2Assets" / "v6"
    index = live_v6 / "runtime_resource_index.v1.json"
    verify_file(index, 1311011, RESOURCE_INDEX_SHA256, f"runtime index {game}")
    asset_sources: list[tuple[Path, str]] = [(index, "PhotonR2Assets/v6/runtime_resource_index.v1.json")]
    for directory, expected_count in meta["asset_counts"].items():
        leaf = live_v6 / directory
        if directory == "payload":
            leaf = leaf / game
            target_prefix = f"PhotonR2Assets/v6/payload/{game}"
        else:
            target_prefix = f"PhotonR2Assets/v6/{directory}"
        found = sorted((path for path in leaf.rglob("*") if path.is_file()), key=lambda path: path.as_posix().casefold())
        need(len(found) == expected_count, f"{game} {directory} asset count drift: {len(found)}")
        for path in found:
            asset_sources.append((path, f"{target_prefix}/{path.relative_to(leaf).as_posix()}"))

    sealed_sidecars = [
        row for row in source_manifest["payload_files"]
        if row["game"] == game and row["role"] == "sidecar"
    ]
    need(len(sealed_sidecars) == meta["sidecars"], f"sealed sidecar count drift for {game}")
    for row in sorted(sealed_sidecars, key=lambda value: value["target"].casefold()):
        asset_sources.append((SEALED / row["path"], row["target"]))

    for source, target in asset_sources:
        row = copy_final_file(source, target, data, "asset", {"exists": False})
        need(row["target"].casefold() not in targets, f"duplicate target: {target}")
        targets.add(row["target"].casefold())
        files.append(row)

    asset_count = sum(row["category"] == "asset" for row in files)
    expected_assets = 1 + sum(meta["asset_counts"].values()) + meta["sidecars"]
    need(asset_count == expected_assets, f"final asset count drift for {game}")
    fixed_count = sum(row["category"] == "fixed" for row in files)
    runtime_rows = [row for row in files if row["target"] == RUNTIME_DLL_TARGET]
    need(len(runtime_rows) == 1, f"expected one controlled runtime DLL for {game}")
    runtime_identity = runtime_rows[0].get("runtime_identity")
    need(
        isinstance(runtime_identity, dict),
        f"runtime DLL identity was not recorded for {game}",
    )
    patch_bytes = sum(int(row["patch"]["bytes"]) for row in archive_rows)
    package_id = f"MuvLuv-{meta['slug']}-CN-Full-Beta0.1"
    manifest = {
        "schema": "muvluv-photon-cn-full-clean-beta01-package/v1",
        "package_id": package_id,
        "version": "Beta0.1",
        "status": "PASS_FULL_CLEAN_BETA01_PACKAGE_SEALED",
        "created_utc": BUILD_TIME.isoformat(),
        "source_date_epoch": BUILD_EPOCH,
        "build_toolchain": build_toolchain_identity(),
        "game": game,
        "game_title": meta["title"],
        "process_name": meta["process"],
        "install_directory": meta["title"],
        "exe": meta["exe"],
        "asset_root": "PhotonR2Assets",
        "archives": archive_rows,
        "files": sorted(files, key=lambda row: row["target"].casefold()),
        "counts": {
            "archive_files": len(archive_rows),
            "patch_files": len(archive_rows),
            "patch_bytes": patch_bytes,
            "fixed_files": fixed_count,
            "asset_files": asset_count,
            "sidecar_files": meta["sidecars"],
            "final_files": len(files),
            "package_payload_files": len(files) + len(archive_rows),
        },
        "authorities": {
            "clean_cache_manifest_sha256": CLEAN_MANIFEST_SHA256,
            "clean_cache_seal_sha256": CLEAN_SEAL_SHA256,
            "latest_runtime_manifest_sha256": SEALED_MANIFEST_SHA256,
            "approved_final_logical_id": f"{meta['slug']}-beta0.1-approved-final",
            "runtime_dll_identity": {
                "target": RUNTIME_DLL_TARGET,
                **runtime_identity,
            },
        },
        "acceptance": {
            "installs_from_exact_clean_steam": True,
            "contains_complete_current_text_font_and_image_runtime": True,
            "does_not_require_old_group_test_patch": True,
            "all_archive_deltas_virtual_apply_to_exact_final_hash": True,
            "installer_backs_up_changed_archive_ranges": True,
            "installer_rolls_back_to_exact_clean_hashes": True,
            "installer_refuses_unknown_or_partial_base_before_write": True,
            "installer_verifies_every_overwritten_preimage_range": True,
            "installer_verifies_every_written_range_after_apply": True,
            "installer_avoids_rehashing_entire_multi_gigabyte_archives": True,
            "installer_prevents_parallel_pf_pm_disk_contention": True,
            "other_game_payload_included": False,
        },
    }
    manifest_path = data / "package_manifest.beta01.json"
    write_json(manifest_path, manifest)

    installer_path = data / "Install-PhotonCN-Full-Beta01.ps1"
    installer_path.write_text(INSTALLER_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8-sig")
    launcher_path = data / "Launch-PhotonCN-Beta01.ps1"
    launcher_path.write_text(make_launcher(), encoding="utf-8-sig")
    seal = {
        "schema": "muvluv-photon-cn-full-clean-beta01-seal/v1",
        "package_id": package_id,
        "status": "PASS",
        "manifest": artifact(manifest_path, data),
        "installer": artifact(installer_path, data),
        "launcher": artifact(launcher_path, data),
    }
    write_json(data / "package_seal.beta01.json", seal)

    install_cmd = b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0data\\Launch-PhotonCN-Beta01.ps1" -Action Install\r\nif errorlevel 1 pause\r\n'
    rollback_cmd = b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0data\\Launch-PhotonCN-Beta01.ps1" -Action Rollback\r\nif errorlevel 1 pause\r\n'
    (package / "安装补丁.cmd").write_bytes(install_cmd)
    (package / "卸载补丁.cmd").write_bytes(rollback_cmd)
    (package / "使用说明.txt").write_text(make_readme(meta), encoding="utf-8-sig")
    need(not (package / "安装补丁.cmd").read_bytes().startswith(b"\xef\xbb\xbf"), "install CMD contains BOM")
    need(not (package / "卸载补丁.cmd").read_bytes().startswith(b"\xef\xbb\xbf"), "rollback CMD contains BOM")

    archive = OUTPUT / f"Muv-Luv_{meta['slug']}_CN_Beta0.1.zip"
    build_deterministic_zip(package, archive)
    archive_hash = sha256(archive)
    (OUTPUT / f"{archive.name}.sha256.txt").write_text(f"{archive_hash}  {archive.name}\n", encoding="ascii")
    print(f"Built {archive.name}: {archive.stat().st_size / (1024**2):.2f} MiB {archive_hash}", flush=True)
    return {
        "game": game,
        "package": package.relative_to(OUTPUT).as_posix(),
        "archive": archive.relative_to(OUTPUT).as_posix(),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": archive_hash,
        "patch_bytes": patch_bytes,
        "asset_files": asset_count,
        "sidecar_files": meta["sidecars"],
        "status": "PASS_BUILT_AND_ZIP_CRC_TESTED",
    }


def main() -> int:
    global OUTPUT, CLEAN, SEALED, STOCK_FIXED, INSTALLER_TEMPLATE, BUILD_TIME, BUILD_EPOCH

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-root", type=Path, required=True)
    parser.add_argument("--sealed-runtime-root", type=Path, required=True)
    parser.add_argument("--stock-fixed-root", type=Path, required=True)
    parser.add_argument("--final-pf-root", type=Path, required=True)
    parser.add_argument("--final-pm-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--installer-template", type=Path, default=INSTALLER_TEMPLATE)
    parser.add_argument(
        "--source-date-epoch",
        type=parse_source_date_epoch,
        default=os.environ.get("SOURCE_DATE_EPOCH"),
        help=(
            "required fixed Unix timestamp for reproducible manifests and ZIP metadata; "
            "may also be supplied through SOURCE_DATE_EPOCH"
        ),
    )
    args = parser.parse_args()

    if args.source_date_epoch is None:
        parser.error("--source-date-epoch or SOURCE_DATE_EPOCH is required")

    OUTPUT = args.output.resolve(strict=False)
    CLEAN = args.clean_root.resolve(strict=True)
    SEALED = args.sealed_runtime_root.resolve(strict=True)
    STOCK_FIXED = args.stock_fixed_root.resolve(strict=True)
    INSTALLER_TEMPLATE = args.installer_template.resolve(strict=True)
    GAMES["PF"]["live"] = args.final_pf_root.resolve(strict=True)
    GAMES["PM"]["live"] = args.final_pm_root.resolve(strict=True)
    BUILD_EPOCH = args.source_date_epoch
    BUILD_TIME = dt.datetime.fromtimestamp(BUILD_EPOCH, tz=dt.timezone.utc)

    need(not OUTPUT.exists(), f"refusing to overwrite candidate output: {OUTPUT}")
    source_manifest = load_and_verify_authorities()
    OUTPUT.mkdir(parents=True)
    results = [build_game(source_manifest, game) for game in ("PF", "PM")]
    report = {
        "schema": "muvluv-photon-cn-full-beta01-build-verification/v1",
        "status": "PASS_BOTH_FULL_CLEAN_PACKAGES_BUILT_AND_ZIP_CRC_TESTED",
        "created_utc": BUILD_TIME.isoformat(),
        "source_date_epoch": BUILD_EPOCH,
        "deterministic_zip_metadata": True,
        "build_toolchain": build_toolchain_identity(),
        "packages": results,
    }
    write_json(OUTPUT / "build_verification.full_beta01.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
