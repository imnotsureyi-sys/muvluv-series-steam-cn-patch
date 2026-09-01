"""Fail-closed helpers for deterministic command-line artifacts.

Public authoring tools must never silently replace an input or an earlier
reviewed result. This module validates the complete output set first, then for
each file writes and fsyncs a same-directory temporary inode and publishes that
complete inode with an exclusive hard link. Multiple siblings are not one
crash-atomic transaction; ordinary exceptions remove files created by the
current attempt.
"""

from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile
from typing import Iterable, Mapping


class OutputSafetyError(FileExistsError):
    """An output path is unsafe, ambiguous, or already occupied."""


def _identity(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def validate_new_outputs(
    outputs: Iterable[Path], *, inputs: Iterable[Path] = ()
) -> list[Path]:
    """Return materialized outputs after rejecting aliases and existing files."""

    paths = [Path(path) for path in outputs]
    identities = [_identity(path) for path in paths]
    if len(identities) != len(set(identities)):
        raise OutputSafetyError("two requested outputs resolve to the same file")
    input_identities = {_identity(Path(path)) for path in inputs}
    collisions = [path for path, identity in zip(paths, identities) if identity in input_identities]
    if collisions:
        raise OutputSafetyError(f"output aliases an input: {collisions[0]}")
    existing = [path for path in paths if path.exists()]
    if existing:
        raise OutputSafetyError(f"output already exists: {existing[0]}")
    return paths


def write_new_files(
    files: Mapping[Path, bytes], *, inputs: Iterable[Path] = ()
) -> None:
    """Publish each complete file atomically and roll back ordinary failures."""

    paths = validate_new_outputs(files.keys(), inputs=inputs)
    created: list[Path] = []
    try:
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(files[path])
                    stream.flush()
                    os.fsync(stream.fileno())
                try:
                    # The source and target share a directory/filesystem.  A
                    # hard link publishes only the already-complete inode and
                    # atomically refuses a destination created by a race.
                    os.link(temporary, path)
                except FileExistsError as exc:
                    raise OutputSafetyError(
                        f"output already exists: {path}"
                    ) from exc
                created.append(path)
            finally:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise


def png_bytes(image: object) -> bytes:
    """Encode a Pillow image deterministically without creating a partial file."""

    buffer = BytesIO()
    image.save(buffer, format="PNG")  # type: ignore[attr-defined]
    return buffer.getvalue()
