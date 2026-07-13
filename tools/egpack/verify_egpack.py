from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path

try:
    from tools.egpack.egpack_codec import (
        EgpackChange,
        EgpackFormatError,
        apply_changes,
        parse_egpack_bytes,
    )
    from tools.egpack.repack_egpack import _resolve_under, load_changes
except ModuleNotFoundError:  # Direct script execution from tools/egpack.
    from egpack_codec import (  # type: ignore[no-redef]
        EgpackChange,
        EgpackFormatError,
        apply_changes,
        parse_egpack_bytes,
    )
    from repack_egpack import _resolve_under, load_changes  # type: ignore[no-redef]


class EgpackVerificationError(ValueError):
    pass


def _first_difference(expected: bytes, actual: bytes) -> int:
    limit = min(len(expected), len(actual))
    for offset in range(limit):
        if expected[offset] != actual[offset]:
            return offset
    return limit


def verify_patched_bytes(
    original: bytes,
    patched: bytes,
    changes: Sequence[EgpackChange],
    source: str = "<memory>",
) -> None:
    try:
        parse_egpack_bytes(original, source=f"{source} (original)")
        parse_egpack_bytes(patched, source=f"{source} (patched)")
        expected = apply_changes(original, changes, source=source)
    except (EgpackFormatError, ValueError) as exc:
        raise EgpackVerificationError(str(exc)) from exc

    if patched != expected:
        offset = _first_difference(expected, patched)
        expected_byte = f"0x{expected[offset]:02X}" if offset < len(expected) else "<EOF>"
        actual_byte = f"0x{patched[offset]:02X}" if offset < len(patched) else "<EOF>"
        raise EgpackVerificationError(
            f"{source}: patched bytes differ from the authorized result at offset 0x{offset:X}; "
            f"expected {expected_byte}, actual {actual_byte} (unauthorized change)"
        )


def _input_root(path: Path) -> tuple[Path, Path | None]:
    resolved = path.resolve()
    if resolved.is_file():
        return resolved.parent, resolved
    if resolved.is_dir():
        return resolved, None
    raise FileNotFoundError(resolved)


def verify_paths(
    original_input: Path,
    patched_input: Path,
    changes_path: Path,
) -> tuple[int, int]:
    changes = load_changes(changes_path)
    original_root, original_file = _input_root(original_input)

    patched_resolved = patched_input.resolve()
    if patched_resolved.is_file():
        patched_root, patched_file = patched_resolved.parent, patched_resolved
    elif patched_resolved.is_dir():
        patched_root, patched_file = patched_resolved, None
    else:
        patched_root, patched_file = patched_resolved, None

    by_file: dict[str, list[EgpackChange]] = defaultdict(list)
    for change in changes:
        by_file[change.relative_path].append(change)

    verified_slots = 0
    for relative_path, file_changes in sorted(by_file.items()):
        original_path = _resolve_under(original_root, relative_path)
        patched_path = _resolve_under(patched_root, relative_path)
        if original_file is not None and original_path != original_file:
            raise EgpackVerificationError(
                f"change path {relative_path!r} does not match original file {original_file.name!r}"
            )
        if patched_file is not None and patched_path != patched_file:
            raise EgpackVerificationError(
                f"change path {relative_path!r} does not match patched file {patched_file.name!r}"
            )
        if not original_path.is_file():
            raise EgpackVerificationError(f"missing original EGPACK: {original_path}")
        if not patched_path.is_file():
            raise EgpackVerificationError(f"missing patched EGPACK: {patched_path}")

        verify_patched_bytes(
            original_path.read_bytes(),
            patched_path.read_bytes(),
            file_changes,
            source=relative_path,
        )
        verified_slots += len(file_changes)

    return len(by_file), verified_slots


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="验证 EGPACK 只包含变更表授权的字节修改。")
    parser.add_argument("original", type=Path, help="原始 EGPACK 或原始目录")
    parser.add_argument("patched", type=Path, help="修改后 EGPACK 或修改后目录")
    parser.add_argument("--changes", type=Path, required=True, help="精确变更 CSV")
    args = parser.parse_args(argv)

    files, slots = verify_paths(args.original, args.patched, args.changes)
    print(f"verified_files={files} verified_slots={slots}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
