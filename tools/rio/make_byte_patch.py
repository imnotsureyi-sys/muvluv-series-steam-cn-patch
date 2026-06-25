from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 64 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_bytes_chunked(path: Path, chunk_size: int = 64 * 1024 * 1024) -> bytes:
    data = bytearray()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            data.extend(chunk)
    return bytes(data)


def diff_ranges(base_bytes: bytes, out_bytes: bytes) -> list[dict[str, object]]:
    if len(base_bytes) != len(out_bytes):
        raise ValueError(f"size mismatch: {len(base_bytes)} != {len(out_bytes)}")
    ranges: list[dict[str, object]] = []
    size = len(base_bytes)

    current_start: int | None = None
    current = bytearray()

    def flush_current() -> None:
        nonlocal current_start, current
        if current_start is None:
            return
        ranges.append(
            {
                "offset": current_start,
                "data_b64": base64.b64encode(bytes(current)).decode("ascii"),
            }
        )
        current_start = None
        current = bytearray()

    chunk_size = 1024 * 1024
    for chunk_start in range(0, size, chunk_size):
        chunk_end = min(chunk_start + chunk_size, size)
        base_chunk = base_bytes[chunk_start:chunk_end]
        out_chunk = out_bytes[chunk_start:chunk_end]
        if base_chunk == out_chunk:
            flush_current()
            continue

        for idx, (before, after) in enumerate(zip(base_chunk, out_chunk), start=chunk_start):
            if before == after:
                flush_current()
                continue
            if current_start is None:
                current_start = idx
            current.append(after)

    flush_current()
    return ranges


def write_apply_script(path: Path, patch_filename: str, tag: str) -> None:
    backup_suffix = f".before_{tag}_cn.bak"
    text = f"""param(
  [string]$GameDir = "D:\\Steam\\steamapps\\common\\Muv-Luv photonmelodies"
)
$ErrorActionPreference = 'Stop'
$PatchPath = Join-Path $PSScriptRoot '{patch_filename}'
$Patch = Get-Content -LiteralPath $PatchPath -Encoding UTF8 -Raw | ConvertFrom-Json
$Target = Join-Path $GameDir $Patch.target_file
if (!(Test-Path -LiteralPath $Target)) {{ throw "Target file not found: $Target" }}
$Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash.ToLowerInvariant()
if ($Sha -ne $Patch.base_sha256) {{ throw "Base SHA256 mismatch. Expected $($Patch.base_sha256), got $Sha. Refusing to patch." }}
$Backup = "$Target{backup_suffix}"
if (!(Test-Path -LiteralPath $Backup)) {{ Copy-Item -LiteralPath $Target -Destination $Backup }}
$Stream = [System.IO.File]::Open($Target, [System.IO.FileMode]::Open, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
try {{
  if ($Stream.Length -ne [int64]$Patch.file_size) {{ throw "File size mismatch." }}
  foreach ($Range in $Patch.ranges) {{
    $Offset = [int64]$Range.offset
    $Data = [System.Convert]::FromBase64String([string]$Range.data_b64)
    [void]$Stream.Seek($Offset, [System.IO.SeekOrigin]::Begin)
    $Stream.Write($Data, 0, $Data.Length)
  }}
}} finally {{
  $Stream.Close()
}}
$NewSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $Target).Hash.ToLowerInvariant()
if ($NewSha -ne $Patch.output_sha256) {{ throw "Patched SHA256 mismatch. Expected $($Patch.output_sha256), got $NewSha." }}
Write-Output "Patched: $Target"
Write-Output "Backup:  $Backup"
Write-Output "SHA256:  $NewSha"
"""
    path.write_text(text, encoding="utf-8")


def write_restore_script(path: Path, tag: str, target_file: str) -> None:
    backup_suffix = f".before_{tag}_cn.bak"
    text = f"""param(
  [string]$GameDir = "D:\\Steam\\steamapps\\common\\Muv-Luv photonmelodies"
)
$ErrorActionPreference = 'Stop'
$Target = Join-Path $GameDir '{target_file}'
$Backup = "$Target{backup_suffix}"
if (!(Test-Path -LiteralPath $Backup)) {{ throw "Backup not found: $Backup" }}
Copy-Item -LiteralPath $Backup -Destination $Target -Force
Write-Output "Restored: $Target"
"""
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-rio", required=True, type=Path)
    parser.add_argument("--output-rio", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--scope", required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    base_bytes = read_bytes_chunked(args.base_rio)
    out_bytes = read_bytes_chunked(args.output_rio)
    ranges = diff_ranges(base_bytes, out_bytes)
    changed_bytes = sum(len(base64.b64decode(item["data_b64"])) for item in ranges)

    target_file = args.base_rio.name
    if args.output_rio.name != target_file:
        raise ValueError(f"output RIO name mismatch: {args.output_rio.name} != {target_file}")

    patch_filename = f"{target_file}.{args.tag}.patch.json"
    patch_path = args.out_dir / patch_filename
    patch = {
        "format": "muvluv-rio-byte-patch-v1",
        "target_file": target_file,
        "scope": args.scope,
        "file_size": len(base_bytes),
        "base_sha256": sha256_file(args.base_rio),
        "output_sha256": sha256_file(args.output_rio),
        "range_count": len(ranges),
        "changed_bytes": changed_bytes,
        "ranges": ranges,
    }
    patch_path.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding="utf-8")

    apply_path = args.out_dir / f"apply_{args.tag}_patch.ps1"
    restore_path = args.out_dir / f"restore_{args.tag}_backup.ps1"
    write_apply_script(apply_path, patch_filename, args.tag)
    write_restore_script(restore_path, args.tag, target_file)

    print(json.dumps({key: patch[key] for key in ["file_size", "base_sha256", "output_sha256", "range_count", "changed_bytes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
