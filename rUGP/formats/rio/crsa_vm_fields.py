"""Inventory every UTF-16 cell and all three CVmMsg3 fields per language.

Ordinary dialogue extraction is intentionally a separate API: an annotation
has its own identity and must not replace an already reviewed dialogue row.
An index into the middle of another string remains an issue, not an inferred
translation. Physical adjacency can recover an annotation's likely owner,
but that evidence is explicitly distinct from a valid native reference.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import struct

from .crsa_vm_pool import CvmPoolError, VmMessageCommand


FIELD_ROLES = ("message", "annotation", "directive")


@dataclass(frozen=True)
class VmFieldReference:
    command_order: int
    command_object_offset: int
    command_offset: int
    language: int
    role: str
    index: int
    index_field_offset: int
    offset: int
    cell_offset: int | None
    at_cell_start: bool
    text: str | None
    error: str | None


@dataclass(frozen=True)
class VmPoolCell:
    index: int
    offset: int
    end: int
    raw: bytes
    text: str


@dataclass(frozen=True)
class VmAnnotationCell:
    cell: VmPoolCell
    command_order: int
    language: int
    native_index: int
    native_offset: int
    index_field_offset: int
    binding: str
    entries: tuple[tuple[str, str], ...]
    keys_in_message: tuple[bool, ...]


@dataclass(frozen=True)
class VmFieldInventory:
    base: int
    end: int
    declared_units: int
    cells: tuple[VmPoolCell, ...]
    references: tuple[VmFieldReference, ...]
    annotations: tuple[VmAnnotationCell, ...]
    unclaimed_cells: tuple[VmPoolCell, ...]
    issues: tuple[str, ...]


def parse_annotation(text: str) -> tuple[tuple[str, str], ...] | None:
    """Parse the native semicolon-separated key:value annotation notation."""
    if not text or any(ord(c) < 32 for c in text):
        return None
    result = []
    for item in text.split(";"):
        if not item:
            continue
        if ":" not in item:
            return None
        key, value = item.split(":", 1)
        if not key or not value:
            return None
        result.append((key, value))
    return tuple(result) or None


def inventory_vm_pool(
    payload: bytes,
    commands: tuple[VmMessageCommand, ...],
    base: int,
) -> VmFieldInventory:
    if not 4 <= base <= len(payload):
        raise CvmPoolError("invalid pool base")
    if commands and max(c.end_offset for c in commands) > base - 4:
        raise CvmPoolError("pool overlaps the message stream")
    units = struct.unpack_from("<I", payload, base - 4)[0]
    end = base + units * 2
    if end > len(payload):
        raise CvmPoolError("declared pool exceeds the payload")

    cells = []
    cursor = base
    while cursor < end:
        start = cursor
        while cursor + 2 <= end and payload[cursor:cursor + 2] != b"\0\0":
            cursor += 2
        if cursor + 2 > end:
            raise CvmPoolError(f"pool cell at {start} lacks a NUL terminator")
        raw = payload[start:cursor + 2]
        try:
            text = raw[:-2].decode("utf-16le", errors="strict")
        except UnicodeDecodeError as error:
            raise CvmPoolError(f"pool cell at {start} is invalid UTF-16LE") from error
        cells.append(VmPoolCell((start - base) // 2, start, cursor + 2, raw, text))
        cursor += 2
    by_offset = {cell.offset: cell for cell in cells}
    starts = [cell.offset for cell in cells]
    refs = []
    issues = []
    for order, command in enumerate(commands, 1):
        for language, record in enumerate(command.first_records):
            for field, index in enumerate(record):
                if field and index == 0:
                    continue  # Auxiliary index zero is the empty sentinel.
                offset = base + 2 * index
                field_offset = command.body_offset + 14 + language * 12 + field * 4
                owner = None
                text = None
                error = None
                if not base <= offset < end:
                    error = "outside_declared_pool"
                else:
                    owner = cells[bisect_right(starts, offset) - 1]
                    try:
                        text = payload[offset:owner.end - 2].decode("utf-16le", errors="strict")
                    except UnicodeDecodeError:
                        error = "invalid_utf16_reference"
                    if offset != owner.offset:
                        error = error or "interior_string_reference"
                if error:
                    issues.append(f"command_{order}:language_{language}:{FIELD_ROLES[field]}:{error}")
                refs.append(VmFieldReference(
                    order, command.object_offset, command.command_offset,
                    language, FIELD_ROLES[field], index, field_offset,
                    offset, owner.offset if owner else None,
                    owner is not None and owner.offset == offset, text, error,
                ))

    # Native serialization places an optional annotation after its own
    # language's message. This relationship is retained when older writers
    # resize dialogue but forget the secondary index. Do not silently repair
    # that index here; publish both locations and the different evidence.
    annotations = []
    claimed = {r.offset for r in refs if r.role in ("message", "directive") and r.at_cell_start}
    primary = {(r.command_order, r.language): r for r in refs if r.role == "message"}
    for ref in refs:
        if ref.role != "annotation":
            continue
        message_ref = primary[(ref.command_order, ref.language)]
        message = by_offset.get(message_ref.offset)
        direct = by_offset.get(ref.offset)
        neighbor = by_offset.get(message.end) if message else None
        direct_entries = parse_annotation(direct.text) if direct else None
        neighbor_entries = parse_annotation(neighbor.text) if neighbor else None
        if direct_entries:
            if neighbor_entries and direct.offset != neighbor.offset:
                issues.append(
                    f"command_{ref.command_order}:language_{ref.language}:annotation:"
                    "native_reference_conflicts_with_adjacent_annotation"
                )
            selected, entries, binding = direct, direct_entries, "exact_native_reference"
        elif neighbor_entries and neighbor.offset not in claimed:
            selected, entries, binding = neighbor, neighbor_entries, "adjacent_to_owned_message_stale_index"
        else:
            issues.append(f"command_{ref.command_order}:language_{ref.language}:annotation:unresolved_cell")
            continue
        annotations.append(VmAnnotationCell(
            selected, ref.command_order, ref.language, ref.index,
            ref.offset, ref.index_field_offset, binding, entries,
            tuple(key in (message_ref.text or "") for key, _ in entries),
        ))
        claimed.add(selected.offset)
    return VmFieldInventory(base, end, units, tuple(cells), tuple(refs),
                            tuple(annotations),
                            tuple(c for c in cells if c.text and c.offset not in claimed),
                            tuple(issues))
