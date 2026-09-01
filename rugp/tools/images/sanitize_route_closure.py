#!/usr/bin/env python3
"""Remove non-portable private staging locators from Photon route evidence.

Only locator fields rooted in the known private staging namespaces are
removed.  Namespace matching is case-insensitive and accepts either slash so
that Windows-produced evidence cannot evade the redaction.  Absolute paths,
UNC paths, parent traversal and every other retained backslash fail closed.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


LOCAL_ROOTS = ("outputs", "output", "local-internal")
REMOVABLE_KEYS = {"path", "official_span_path"}
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class SanitizeError(RuntimeError):
    """The route evidence cannot be made portable without guessing."""


def _normalized_locator(value: str) -> str:
    return value.replace("\\", "/")


def _is_local_staging_locator(value: str) -> bool:
    normalized = _normalized_locator(value).casefold()
    return any(
        normalized == root or normalized.startswith(f"{root}/")
        for root in LOCAL_ROOTS
    )


def _unsafe_locator_shape(value: str) -> str | None:
    """Return why a locator cannot be published, or ``None`` when portable."""

    normalized = _normalized_locator(value)
    if WINDOWS_DRIVE_RE.match(value):
        return "Windows drive-qualified path"
    if normalized.startswith("/"):
        return "absolute or UNC path"
    if ".." in normalized.split("/"):
        return "parent-directory traversal"
    return None


def _reject_nonportable_locator(value: str) -> None:
    reason = _unsafe_locator_shape(value)
    if reason is None and "\\" in value:
        reason = "backslash path"
    if reason is None and _is_local_staging_locator(value):
        reason = "private staging path"
    if reason is not None:
        raise SanitizeError(f"non-portable locator remains: {reason}: {value!r}")


def _sanitize(value: Any) -> tuple[Any, int]:
    if isinstance(value, list):
        items: list[Any] = []
        removed = 0
        for item in value:
            clean, count = _sanitize(item)
            items.append(clean)
            removed += count
        return items, removed
    if not isinstance(value, Mapping):
        return value, 0
    result: dict[str, Any] = {}
    removed = 0
    for key, item in value.items():
        if key in REMOVABLE_KEYS and isinstance(item, str) and _is_local_staging_locator(item):
            reason = _unsafe_locator_shape(item)
            if reason is not None:
                raise SanitizeError(
                    f"refusing ambiguous private locator: {reason}: {item!r}"
                )
            removed += 1
            continue
        if isinstance(item, str):
            _reject_nonportable_locator(item)
        clean, count = _sanitize(item)
        result[str(key)] = clean
        removed += count
    return result, removed


def sanitize(document: Mapping[str, Any], *, expected_removed: int | None = None) -> dict[str, Any]:
    clean, removed = _sanitize(document)
    if not isinstance(clean, dict):
        raise SanitizeError("route evidence root must be an object")
    if expected_removed is not None and removed != expected_removed:
        raise SanitizeError(
            f"removed locator count mismatch: expected {expected_removed}, got {removed}"
        )
    clean["artifact_locator_policy"] = {
        "local_staging_paths_published": False,
        "removed_locator_fields": removed,
        "portable_authority": "logical archive range plus byte count and SHA-256",
        "binary_artifacts_in_git": False,
    }
    return clean


def write_new(path: Path, payload: bytes, *, source: Path) -> None:
    if path.resolve(strict=False) == source.resolve(strict=True):
        raise SanitizeError("output must not alias the source evidence")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        descriptor = os.open(path, flags, 0o666)
    except FileExistsError as exc:
        raise SanitizeError(f"refusing to overwrite output: {path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-removed", type=int)
    args = parser.parse_args(argv)
    try:
        document = json.loads(args.source.read_text(encoding="utf-8-sig"))
        clean = sanitize(document, expected_removed=args.expect_removed)
        payload = (
            json.dumps(clean, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
        ).encode("utf-8")
        write_new(args.output, payload, source=args.source)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "output": args.output.name,
                    "removed_locator_fields": clean["artifact_locator_policy"][
                        "removed_locator_fields"
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
