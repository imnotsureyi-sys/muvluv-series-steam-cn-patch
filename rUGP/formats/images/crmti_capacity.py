"""Capacity accounting for the observed PF/PM sparse-row CRmti path.

The serialized ``decoded_size_hint`` is mutable allocation metadata, not an
opaque identity field. PF 0x5B0883..0x5B0C21 expands neighbouring row ranges
and rejects the conversion when its cursor exceeds hint + 4*height + 20.
The same 865-byte expansion block occurs at PM 0x5B2513. This module models
that gate and its backing storage, not every runtime/rendering requirement.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CrmtiCapacity:
    height: int
    active_row_count: int
    expanded_pixel_bytes: int
    guard_cursor: int
    physical_storage_bytes: int
    required_hint: int

    def accepts(self, hint: int) -> bool:
        return (
            0 <= hint <= 0x7FFFFFFF - 12*self.height - 16
            and self.guard_cursor <= hint + 4*self.height + 20
            and self.physical_storage_bytes <= hint + 12*self.height + 16
        )

    def replacement_hint(self, original_hint: int) -> int:
        """Grow only when needed; never shrink a valid source reservation."""
        hint = max(original_hint, self.required_hint)
        if original_hint < 0 or not self.accepts(hint):
            raise ValueError("CRmti capacity is outside the native signed allocation range")
        return hint


def capacity_for_ranges(
    width: int,
    height: int,
    active_row_count: int,
    ranges: Sequence[tuple[int, int]],
) -> CrmtiCapacity:
    """Account for decoded, half-open row ranges including empty tail rows.

Each output row uses the union of nonempty ranges in y-1/y/y+1, with two
horizontal edge pixels. Native y=-1 and y=active_row_count sentinel rows
also participate; the bottom sentinel has two additional edge pixels.
The guard starts at four bytes and adds eight bytes plus four per expanded
pixel for each row. Allocation additionally contains the height-sized row
table; its separate bound matters for very short/empty active regions.
"""
    if not (0 < width <= 0x7FFF and 0 < height <= 0x7FFF):
        raise ValueError("CRmti dimensions exceed the native signed-word range")
    if len(ranges) != height or not 0 <= active_row_count <= height:
        raise ValueError("CRmti active row count/height mismatch")
    if any(not 0 <= left <= right <= width for left, right in ranges):
        raise ValueError("CRmti row range is outside the canvas")
    if any(left != right for left, right in ranges[active_row_count:]):
        raise ValueError("CRmti nonempty row after active row count")

    expanded_pixels = 0
    for y in range(-1, active_row_count + 1):
        neighbours = [ranges[k] for k in (y-1, y, y+1)
                      if 0 <= k < active_row_count and ranges[k][0] < ranges[k][1]]
        if neighbours:
            span = max(right for _, right in neighbours) - min(left for left, _ in neighbours)
            expanded_pixels += span + 2 + (2 if y == active_row_count else 0)
    expanded_bytes = expanded_pixels * 4
    cursor = 4 + 8*(active_row_count+2) + expanded_bytes
    storage = 8*height + 20 + expanded_bytes
    required = max(0, cursor - 4*height - 20, storage - 12*height - 16)
    result = CrmtiCapacity(height, active_row_count, expanded_bytes, cursor, storage, required)
    if not result.accepts(required):
        raise ValueError("CRmti capacity exceeds the native allocation range")
    return result
