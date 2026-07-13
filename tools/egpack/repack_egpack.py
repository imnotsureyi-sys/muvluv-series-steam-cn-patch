from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
import sys


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from tools.egpack.egpack_codec import EgpackChange, EgpackChangeError, apply_changes
except ModuleNotFoundError:  # Direct script execution from tools/egpack.
    from egpack_codec import EgpackChange, EgpackChangeError, apply_changes  # type: ignore[no-redef]


CHANGE_COLUMNS = (
    "relative_path",
    "id",
    "slot",
    "expected_text",
    "replacement_text",
)


def _normalize_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized:
        raise EgpackChangeError(f"unsafe relative_path {value!r}")
    if path.suffix.lower() != ".egpack":
        raise EgpackChangeError(f"relative_path is not an .egpack file: {value!r}")
    return path.as_posix()


def load_changes(path: Path) -> list[EgpackChange]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CHANGE_COLUMNS:
            raise EgpackChangeError(
                f"{path}: columns must be exactly {','.join(CHANGE_COLUMNS)}"
            )
        changes = [
            EgpackChange(
                relative_path=_normalize_relative_path(row["relative_path"]),
                text_id=row["id"],
                slot=row["slot"],
                expected_text=row["expected_text"],
                replacement_text=row["replacement_text"],
            )
            for row in reader
        ]
    if not changes:
        raise EgpackChangeError(f"{path}: changes CSV contains no rows")

    seen: set[tuple[str, str, str]] = set()
    for change in changes:
        target = (change.relative_path, change.text_id, change.slot)
        if target in seen:
            raise EgpackChangeError(
                f"{path}: duplicate change target {change.relative_path}/{change.text_id}/{change.slot}"
            )
        seen.add(target)
    return changes


def _resolve_under(root: Path, relative_path: str) -> Path:
    parts = PurePosixPath(relative_path).parts
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise EgpackChangeError(f"path escapes root: {relative_path!r}") from exc
    return candidate


def repack(input_path: Path, changes_path: Path, output_dir: Path) -> tuple[int, int]:
    changes = load_changes(changes_path)
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    if input_path.is_file():
        source_root = input_path.parent
    elif input_path.is_dir():
        source_root = input_path
        try:
            output_dir.relative_to(source_root)
        except ValueError:
            pass
        else:
            raise EgpackChangeError("input and output directories overlap")
    else:
        raise FileNotFoundError(input_path)

    by_file: dict[str, list[EgpackChange]] = defaultdict(list)
    for change in changes:
        by_file[change.relative_path].append(change)

    prepared: list[tuple[Path, bytes, int]] = []
    for relative_path, file_changes in sorted(by_file.items()):
        source = _resolve_under(source_root, relative_path)
        if input_path.is_file() and source != input_path:
            raise EgpackChangeError(
                f"change path {relative_path!r} does not match input file {input_path.name!r}"
            )
        if not source.is_file():
            raise EgpackChangeError(f"source EGPACK does not exist: {source}")

        destination = _resolve_under(output_dir, relative_path)
        if destination == source:
            raise EgpackChangeError(f"input and output paths overlap: {source}")
        if destination.exists():
            raise EgpackChangeError(f"output file already exists: {destination}")

        patched = apply_changes(source.read_bytes(), file_changes, source=str(source))
        prepared.append((destination, patched, len(file_changes)))

    changed_slots = 0
    for destination, patched, slot_count in prepared:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(patched)
        changed_slots += slot_count

    return len(by_file), changed_slots


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按 ID 和语言槽精确写回 EGPACK。")
    parser.add_argument("input", type=Path, help="单个 EGPACK 或作为相对路径根的目录")
    parser.add_argument("--changes", type=Path, required=True, help="精确变更 CSV")
    parser.add_argument("--output-dir", type=Path, required=True, help="新的输出目录")
    args = parser.parse_args(argv)

    files, slots = repack(args.input, args.changes, args.output_dir)
    print(f"repacked_files={files} changed_slots={slots} output={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
