from __future__ import annotations

"""Read-only text discovery inside a decrypted CRsa payload.

The scanner combines three independently useful structures found in current
Steam PF/PM records: adjacent NUL-terminated source/translation strings,
serialized counted Unicode strings, and CVMMsg3 command-indexed pools.  It is
deliberately conservative and reports unresolved VM layouts instead of
guessing a pool base.

This module is descended from the project's historical Photon Melodies
``crsa_payload.py``, ``vm_command_stream.py`` and the stable parser portions of
``extract_native_slots_v3.py``.  Encryption and CVM command parsing are reused
from the maintained ``crsa.py`` and ``crsa_vm_pool.py`` modules.
"""

from dataclasses import dataclass
from typing import Iterable, Literal, Sequence

from .crsa import CrsaRebuildError, UNICODE_MARKER, parse_unicode_string_at
from .crsa_vm_pool import (
    CvmPoolError,
    VmMessageCommand,
    find_vm_message_commands,
    infer_direct_pool_base,
    infer_pool_base,
    parse_direct_pool,
)


SpanKind = Literal["text", "binary"]
ALLOWED_CONTROL_CODES = frozenset((1, 2, 3, 5, 9, 10, 12, 13))
DISPLAY_TERMINATORS = frozenset((1, 2))


@dataclass(frozen=True)
class PayloadSpan:
    start: int
    end: int
    kind: SpanKind
    raw_bytes: bytes
    reason: str


@dataclass(frozen=True)
class TextPairSlot:
    payload_offset: int
    source_end: int
    translation_start: int
    slot_end: int
    source_text: str
    translation_text: str
    control_codes: tuple[int, ...]


@dataclass(frozen=True)
class Utf16Candidate:
    start: int
    end: int
    terminator_end: int
    text: str
    parity: int
    raw_bytes: bytes


@dataclass(frozen=True)
class TerminatedString:
    start: int
    end: int
    terminator_end: int
    text: str


@dataclass(frozen=True)
class StructuralTextPair:
    source_start: int
    source_end: int
    translation_start: int
    pair_end: int
    source_text: str
    translation_text: str
    auxiliary_texts: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class InlineUnicodeRecord:
    marker_offset: int
    text_offset: int
    end_offset: int
    text: str
    source_text: str
    translation_text: str
    source_end: int
    translation_offset: int | None
    control_codes: tuple[int, ...]
    has_translation_delimiter: bool


@dataclass(frozen=True)
class ExtractedTextSlot:
    payload_offset: int
    source_end: int
    translation_offset: int | None
    source_text: str
    existing_translation_text: str
    slot_kind: str
    evidence: str
    control_codes: tuple[int, ...]
    identity_start: int
    identity_end: int


@dataclass(frozen=True)
class TextExtractionReport:
    slots: tuple[ExtractedTextSlot, ...]
    warnings: tuple[str, ...]
    ambiguous_ascii_pairs: tuple[tuple[int, int], ...]
    vm_command_count: int
    vm_pool_base: int | None


def _visible_characters(text: str) -> list[str]:
    return [character for character in text if ord(character) >= 0x20]


def _is_translation_like(text: str) -> bool:
    visible = _visible_characters(text)
    if not visible:
        return False
    if any(
        "\u3040" <= character <= "\u30ff" or "\u3400" <= character <= "\u9fff"
        for character in visible
    ):
        return False
    allowed_ranges = (
        (0x20, 0x024F),
        (0x0370, 0x052F),
        (0x2000, 0x218F),
        (0x2190, 0x26FF),
        (0x3000, 0x303F),
        (0xFF00, 0xFF65),
    )
    if any(
        not any(start <= ord(character) <= end for start, end in allowed_ranges)
        for character in visible
    ):
        return False
    return any(
        character.isalpha() and not ("\u0370" <= character <= "\u03ff")
        for character in visible
    )


def is_source_text_candidate(text: str) -> bool:
    visible = _visible_characters(text)
    if not visible:
        return False
    if any(ord(character) in DISPLAY_TERMINATORS for character in text[:-1]):
        return False
    allowed_ranges = (
        (0x20, 0x024F),
        (0x0370, 0x052F),
        (0x2000, 0x26FF),
        (0x3000, 0x30FF),
        (0x31F0, 0x33FF),
        (0x3400, 0x9FFF),
        (0xFF00, 0xFFEF),
    )
    if any(
        not any(start <= ord(character) <= end for start, end in allowed_ranges)
        for character in visible
    ):
        return False
    lexical_japanese = sum(
        "\u3040" <= character <= "\u30ff" or "\u3400" <= character <= "\u9fff"
        for character in visible
    )
    non_ascii = sum(ord(character) > 0x7E for character in visible)
    if lexical_japanese >= 2:
        return True
    return len(visible) >= 2 and non_ascii == len(visible)


def _is_text_code_unit(code_unit: int) -> bool:
    if code_unit in ALLOWED_CONTROL_CODES:
        return True
    if code_unit < 0x20 or 0xD800 <= code_unit <= 0xDFFF:
        return False
    return code_unit not in (0xFFFE, 0xFFFF)


def scan_utf16_strings(payload: bytes) -> list[Utf16Candidate]:
    """Return maximal NUL-terminated UTF-16LE candidates at both parities."""

    candidates: list[Utf16Candidate] = []
    for parity in (0, 1):
        start: int | None = None
        position = parity
        while position + 1 < len(payload):
            code_unit = int.from_bytes(payload[position : position + 2], "little")
            if code_unit == 0:
                if start is not None and position > start:
                    raw = payload[start:position]
                    candidates.append(
                        Utf16Candidate(
                            start=start,
                            end=position,
                            terminator_end=position + 2,
                            text=raw.decode("utf-16le", errors="strict"),
                            parity=parity,
                            raw_bytes=raw,
                        )
                    )
                start = None
            elif _is_text_code_unit(code_unit):
                if start is None:
                    start = position
            else:
                start = None
            position += 2
    candidates.sort(key=lambda item: (item.start, item.end, item.parity))
    return candidates


def find_owning_candidate(
    candidates: Iterable[Utf16Candidate],
    offset: int,
    byte_length: int,
) -> Utf16Candidate:
    end = offset + byte_length
    owners = [
        candidate
        for candidate in candidates
        if candidate.start <= offset
        and end <= candidate.end
        and (offset - candidate.start) % 2 == 0
    ]
    if not owners:
        raise KeyError(f"no UTF-16 candidate owns {offset}:{end}")
    owners.sort(key=lambda item: (item.end - item.start, item.start))
    if len(owners) > 1 and (owners[0].start, owners[0].end) != (
        owners[1].start,
        owners[1].end,
    ):
        raise ValueError(f"ambiguous UTF-16 candidate ownership for {offset}:{end}")
    return owners[0]


def find_structural_source_pairs(
    payload: bytes,
    *,
    allow_empty_translation: bool = False,
) -> list[StructuralTextPair]:
    candidates = scan_utf16_strings(payload)
    by_start = {(item.start, item.parity): item for item in candidates}
    pairs: list[StructuralTextPair] = []
    seen_sources: set[int] = set()

    for source in candidates:
        if source.start in seen_sources or not source.text:
            continue
        if (
            ord(source.text[-1]) not in DISPLAY_TERMINATORS
            or not is_source_text_candidate(source.text)
        ):
            continue
        cursor = source.terminator_end
        auxiliary: list[str] = []
        accepted: StructuralTextPair | None = None
        for _ in range(5):
            if allow_empty_translation and payload[cursor : cursor + 2] == b"\x00\x00":
                lexical = sum(
                    "\u3040" <= character <= "\u30ff"
                    or "\u4e00" <= character <= "\u9fff"
                    for character in _visible_characters(source.text)
                )
                if lexical >= 2:
                    accepted = StructuralTextPair(
                        source.start,
                        source.end,
                        cursor,
                        cursor + 2,
                        source.text,
                        "",
                        tuple(auxiliary),
                        "source_with_empty_translation",
                    )
                break
            item = by_start.get((cursor, source.parity))
            if item is None:
                break
            if item.text and ord(item.text[-1]) in DISPLAY_TERMINATORS:
                if _is_translation_like(item.text):
                    accepted = StructuralTextPair(
                        source.start,
                        source.end,
                        item.start,
                        item.terminator_end,
                        source.text,
                        item.text,
                        tuple(auxiliary),
                        "adjacent_source_translation",
                    )
                break
            if not item.text or len(item.text) > 200:
                break
            auxiliary.append(item.text)
            cursor = item.terminator_end
        if accepted is not None:
            pairs.append(accepted)
            seen_sources.add(source.start)
    return sorted(pairs, key=lambda item: item.source_start)


def _require_valid_offset(offset: int, payload_length: int) -> None:
    if offset < 0 or offset > payload_length:
        raise ValueError(f"invalid UTF-16LE payload offset: {offset}")


def _find_previous_nul(payload: bytes, offset: int) -> int:
    _require_valid_offset(offset, len(payload))
    position = offset - 2
    while position >= 0:
        if payload[position : position + 2] == b"\x00\x00":
            return position
        position -= 2
    return -2


def _find_next_nul(payload: bytes, offset: int) -> int:
    _require_valid_offset(offset, len(payload))
    position = offset
    while position + 1 < len(payload):
        if payload[position : position + 2] == b"\x00\x00":
            return position
        position += 2
    raise ValueError(f"unterminated UTF-16LE string at {offset}")


def _decode_utf16(payload: bytes, start: int, end: int) -> str:
    try:
        return payload[start:end].decode("utf-16le", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError(f"invalid UTF-16LE string at {start}:{end}") from error


def parse_text_pair_at(payload: bytes, start: int) -> TextPairSlot:
    _require_valid_offset(start, len(payload))
    source_end = _find_next_nul(payload, start)
    translation_start = source_end + 2
    translation_end = _find_next_nul(payload, translation_start)
    source_text = _decode_utf16(payload, start, source_end)
    translation_text = _decode_utf16(payload, translation_start, translation_end)
    return TextPairSlot(
        payload_offset=start,
        source_end=source_end,
        translation_start=translation_start,
        slot_end=translation_end + 2,
        source_text=source_text,
        translation_text=translation_text,
        control_codes=tuple(
            ord(character) for character in source_text if ord(character) < 0x20
        ),
    )


def _slot_for_offset(payload: bytes, offset: int) -> TextPairSlot:
    start = _find_previous_nul(payload, offset) + 2
    slot = parse_text_pair_at(payload, start)
    if not start <= offset <= slot.source_end:
        raise ValueError(f"offset {offset} is outside source string {start}:{slot.source_end}")
    return slot


def _valid_structural_neighbor(slot: TextPairSlot) -> bool:
    if not slot.source_text or len(slot.source_text) > 2000 or len(slot.translation_text) > 4000:
        return False
    if ord(slot.source_text[-1]) not in DISPLAY_TERMINATORS:
        return False
    return all(
        all(
            ord(character) >= 0x20 or ord(character) in ALLOWED_CONTROL_CODES
            for character in text
        )
        and "\ufffd" not in text
        for text in (slot.source_text, slot.translation_text)
    )


def _previous_pair_start(payload: bytes, current_start: int) -> int:
    if current_start < 4 or payload[current_start - 2 : current_start] != b"\x00\x00":
        raise ValueError(f"no previous UTF-16LE terminator before {current_start}")
    position = current_start - 4
    while position >= 0 and payload[position : position + 2] != b"\x00\x00":
        position -= 2
    if position < 0:
        raise ValueError(f"no previous source terminator before {current_start}")
    position -= 2
    while position >= 0 and payload[position : position + 2] != b"\x00\x00":
        position -= 2
    if position < 0:
        raise ValueError(f"no previous pair boundary before {current_start}")
    return position + 2


def _try_structural_neighbor(payload: bytes, start: int) -> TextPairSlot | None:
    try:
        slot = parse_text_pair_at(payload, start)
    except ValueError:
        return None
    return slot if _valid_structural_neighbor(slot) else None


def parse_text_slots(
    payload: bytes,
    *,
    known_text_offsets: Iterable[int] = (),
) -> list[TextPairSlot]:
    slots_by_start: dict[int, TextPairSlot] = {}
    for offset in sorted(set(known_text_offsets)):
        slot = _slot_for_offset(payload, offset)
        previous = slots_by_start.get(slot.payload_offset)
        if previous is not None and previous != slot:
            raise ValueError(f"conflicting slot boundaries at {slot.payload_offset}")
        slots_by_start[slot.payload_offset] = slot
    slots = sorted(slots_by_start.values(), key=lambda item: item.payload_offset)
    for first, second in zip(slots, slots[1:]):
        if second.payload_offset < first.slot_end:
            raise ValueError(
                f"overlapping text slots at {first.payload_offset} and {second.payload_offset}"
            )
    return slots


def expand_seeded_text_slots(
    payload: bytes,
    known_text_offsets: Iterable[int],
) -> list[TextPairSlot]:
    slots_by_start = {
        slot.payload_offset: slot
        for slot in parse_text_slots(payload, known_text_offsets=known_text_offsets)
    }
    seeds = tuple(slots_by_start.values())
    for seed in seeds:
        cursor = seed.slot_end
        while cursor < len(payload):
            slot = _try_structural_neighbor(payload, cursor)
            if slot is None:
                break
            slots_by_start.setdefault(slot.payload_offset, slot)
            cursor = slot.slot_end
        cursor = seed.payload_offset
        while cursor > 0:
            try:
                previous_start = _previous_pair_start(payload, cursor)
            except ValueError:
                break
            slot = _try_structural_neighbor(payload, previous_start)
            if slot is None or slot.slot_end != cursor:
                break
            slots_by_start.setdefault(slot.payload_offset, slot)
            cursor = slot.payload_offset
    return sorted(slots_by_start.values(), key=lambda item: item.payload_offset)


def _read_terminated_string_at(
    payload: bytes,
    start: int,
    *,
    max_code_units: int = 4000,
) -> TerminatedString:
    _require_valid_offset(start, len(payload))
    position = start
    units = 0
    while position + 1 < len(payload):
        code_unit = int.from_bytes(payload[position : position + 2], "little")
        if code_unit == 0:
            raw = payload[start:position]
            text = raw.decode("utf-16le", errors="strict")
            if any(not _is_text_code_unit(ord(character)) for character in text):
                raise ValueError(f"invalid control code in UTF-16LE string at {start}")
            return TerminatedString(start, position, position + 2, text)
        if not _is_text_code_unit(code_unit):
            raise ValueError(f"invalid UTF-16LE code unit {code_unit:04x} at {position}")
        units += 1
        if units > max_code_units:
            raise ValueError(f"UTF-16LE string exceeds {max_code_units} units at {start}")
        position += 2
    raise ValueError(f"unterminated UTF-16LE string at {start}")


def recover_seeded_source_strings(
    payload: bytes,
    known_source_offsets: Iterable[int],
) -> list[TerminatedString]:
    known_order = sorted(set(known_source_offsets))
    known = set(known_order)
    recovered: dict[int, TerminatedString] = {}
    for seed_index, seed_offset in enumerate(known_order):
        try:
            seed = _read_terminated_string_at(payload, seed_offset)
        except (UnicodeDecodeError, ValueError):
            continue
        recovered[seed.start] = seed
        next_known = known_order[seed_index + 1] if seed_index + 1 < len(known_order) else None
        local_sources: dict[int, TerminatedString] = {}
        cursor = seed.terminator_end
        expect_translation = True
        interval_valid = False
        for _ in range(10000):
            if next_known is not None and cursor == next_known:
                interval_valid = not expect_translation
                break
            if next_known is not None and cursor > next_known:
                break
            try:
                item = _read_terminated_string_at(payload, cursor)
            except (UnicodeDecodeError, ValueError):
                interval_valid = next_known is None and not expect_translation
                break
            if item.start in known:
                interval_valid = not expect_translation
                break
            if not item.text:
                if expect_translation:
                    expect_translation = False
                else:
                    break
            elif ord(item.text[-1]) in DISPLAY_TERMINATORS:
                if expect_translation:
                    expect_translation = False
                else:
                    local_sources[item.start] = item
                    expect_translation = True
            if item.terminator_end <= cursor:
                raise AssertionError("UTF-16LE scanner did not advance")
            cursor = item.terminator_end
            if cursor >= len(payload):
                interval_valid = next_known is None and not expect_translation
                break
        if interval_valid:
            recovered.update(local_sources)
    return sorted(recovered.values(), key=lambda item: item.start)


def parse_payload_spans(
    payload: bytes,
    *,
    known_text_offsets: Iterable[int] = (),
) -> list[PayloadSpan]:
    slots = parse_text_slots(payload, known_text_offsets=known_text_offsets)
    spans: list[PayloadSpan] = []
    cursor = 0
    for slot in slots:
        if cursor < slot.payload_offset:
            spans.append(
                PayloadSpan(cursor, slot.payload_offset, "binary", payload[cursor:slot.payload_offset], "not anchored as text")
            )
        spans.append(
            PayloadSpan(slot.payload_offset, slot.slot_end, "text", payload[slot.payload_offset:slot.slot_end], "source and adjacent translation UTF-16LE slot")
        )
        cursor = slot.slot_end
    if cursor < len(payload):
        spans.append(PayloadSpan(cursor, len(payload), "binary", payload[cursor:], "not anchored as text"))
    return spans


def _strip_trailing_controls(text: str) -> str:
    return text.rstrip("".join(chr(code) for code in range(0x20)))


def scan_inline_unicode_records(payload: bytes) -> list[InlineUnicodeRecord]:
    """Read serialized counted Unicode strings using the maintained CRsa parser."""

    records: list[InlineUnicodeRecord] = []
    search_from = 0
    while True:
        marker_offset = payload.find(UNICODE_MARKER, search_from)
        if marker_offset < 0:
            break
        try:
            counted = parse_unicode_string_at(payload, marker_offset)
        except CrsaRebuildError:
            search_from = marker_offset + 1
            continue
        text_end = counted.end_offset
        while text_end + 1 < len(payload):
            code_unit = int.from_bytes(payload[text_end : text_end + 2], "little")
            if code_unit not in ALLOWED_CONTROL_CODES:
                break
            text_end += 2
        try:
            trailing = payload[counted.end_offset:text_end].decode("utf-16le", errors="strict")
        except UnicodeDecodeError:
            search_from = marker_offset + 1
            continue
        text = counted.text + trailing
        record_end = text_end
        if payload[text_end : text_end + 2] == b"\x00\x00":
            record_end += 2
        has_delimiter = "\\|" in text
        if has_delimiter:
            raw_source, raw_translation = text.split("\\|", 1)
            source_text = _strip_trailing_controls(raw_source)
            translation_text = _strip_trailing_controls(raw_translation)
            source_end = counted.text_offset + len(source_text.encode("utf-16le"))
            translation_offset = counted.text_offset + len((raw_source + "\\|").encode("utf-16le"))
        else:
            source_text = _strip_trailing_controls(text)
            translation_text = ""
            source_end = counted.text_offset + len(source_text.encode("utf-16le"))
            translation_offset = None
        records.append(
            InlineUnicodeRecord(
                marker_offset=marker_offset,
                text_offset=counted.text_offset,
                end_offset=record_end,
                text=text,
                source_text=source_text,
                translation_text=translation_text,
                source_end=source_end,
                translation_offset=translation_offset,
                control_codes=tuple(
                    ord(character) for character in text if ord(character) < 0x20
                ),
                has_translation_delimiter=has_delimiter,
            )
        )
        search_from = marker_offset + 1
    return records


def _canonical_native_offset(payload: bytes, reference_offset: int) -> int:
    if payload[reference_offset : reference_offset + 2] == b"\x10\x00":
        return reference_offset + 2
    return reference_offset


def derive_pool_base_from_source_offsets(
    payload: bytes,
    commands: Sequence[VmMessageCommand],
    source_offsets: Iterable[int],
    *,
    include_translation_anchors: bool = False,
) -> int:
    """Fallback pool inference anchored by independently discovered sources."""

    native = set(source_offsets)
    referenced = [
        command for command in commands if command.source_index < command.translation_index
    ]
    if not referenced or not native:
        raise CvmPoolError("pool inference needs text commands and source offsets")
    candidates: set[int] = set()
    for command in referenced[:32]:
        for native_offset in sorted(native)[:64]:
            indices = (command.source_index, command.translation_index) if include_translation_anchors else (command.source_index,)
            for index in indices:
                for prefix_size in (0, 2, 8):
                    base = native_offset - index * 2 - prefix_size
                    if 4 <= base < len(payload):
                        candidates.add(base)
    scored: list[tuple[int, int]] = []
    for base in candidates:
        try:
            layout = parse_direct_pool(payload, tuple(commands), base)
        except CvmPoolError:
            continue
        matched = sum(
            (_canonical_native_offset(payload, source.offset) in native
             or (include_translation_anchors
                 and _canonical_native_offset(payload, translation.offset) in native))
            for source, translation in layout.command_slots
        )
        scored.append((matched, base))
    if not scored:
        raise CvmPoolError("no source-anchored pool base candidate")
    scored.sort(reverse=True)
    best_score = scored[0][0]
    tied = [base for score, base in scored if score == best_score]
    minimum = min(2, len(referenced), len(native))
    if best_score < minimum or len(tied) != 1:
        raise CvmPoolError(
            f"ambiguous source-anchored pool base: score={best_score} bases={tied[:20]}"
        )
    return tied[0]


def _ascii_translation_like(text: str) -> bool:
    visible = _visible_characters(text)
    return bool(visible) and sum(0x20 <= ord(char) <= 0x7E for char in visible) / len(visible) >= 0.95


def find_ambiguous_ascii_display_pairs(payload: bytes) -> list[tuple[int, int]]:
    display = [
        item
        for item in scan_utf16_strings(payload)
        if item.text
        and ord(item.text[-1]) in DISPLAY_TERMINATORS
        and _ascii_translation_like(item.text)
    ]
    by_start = {(item.start, item.parity): item for item in display}
    return [
        (item.start, following.start)
        for item in display
        if (following := by_start.get((item.terminator_end, item.parity))) is not None
    ]


_EVIDENCE_PRIORITY = {
    "adjacent_source_translation": 10,
    "source_with_empty_translation": 10,
    "recovered_between_source_anchors": 20,
    "seeded_adjacent_pair": 25,
    "inline_length_record": 30,
    "cvmmsg3_exact_reference": 40,
}


def extract_text_slots(
    payload: bytes,
    *,
    known_text_offsets: Iterable[int] = (),
) -> TextExtractionReport:
    """Discover conservative source slots without modifying ``payload``."""

    warnings: list[str] = []
    candidates: dict[int, ExtractedTextSlot] = {}

    def add(slot: ExtractedTextSlot) -> None:
        previous = candidates.get(slot.payload_offset)
        if previous is None:
            candidates[slot.payload_offset] = slot
            return
        if previous.source_text != slot.source_text:
            old_priority = _EVIDENCE_PRIORITY.get(previous.evidence, 0)
            new_priority = _EVIDENCE_PRIORITY.get(slot.evidence, 0)
            warnings.append(
                f"conflicting_source_at_0x{slot.payload_offset:X}:"
                f"{previous.evidence}:{slot.evidence}"
            )
            if new_priority > old_priority:
                candidates[slot.payload_offset] = slot
            return
        if _EVIDENCE_PRIORITY.get(slot.evidence, 0) > _EVIDENCE_PRIORITY.get(previous.evidence, 0):
            candidates[slot.payload_offset] = slot

    structural = find_structural_source_pairs(payload, allow_empty_translation=True)
    for pair in structural:
        add(
            ExtractedTextSlot(
                payload_offset=pair.source_start,
                source_end=pair.source_end,
                translation_offset=pair.translation_start,
                source_text=pair.source_text,
                existing_translation_text=pair.translation_text,
                slot_kind="adjacent_utf16_pair",
                evidence=pair.evidence,
                control_codes=tuple(
                    ord(character)
                    for character in pair.source_text
                    if ord(character) < 0x20
                ),
                identity_start=pair.source_start,
                identity_end=pair.pair_end,
            )
        )

    seeds = tuple(sorted(set(known_text_offsets)))
    if seeds:
        for pair in expand_seeded_text_slots(payload, seeds):
            add(
                ExtractedTextSlot(
                    payload_offset=pair.payload_offset,
                    source_end=pair.source_end,
                    translation_offset=pair.translation_start,
                    source_text=pair.source_text,
                    existing_translation_text=pair.translation_text,
                    slot_kind="seeded_adjacent_utf16_pair",
                    evidence="seeded_adjacent_pair",
                    control_codes=pair.control_codes,
                    identity_start=pair.payload_offset,
                    identity_end=pair.slot_end,
                )
            )
        for item in recover_seeded_source_strings(payload, seeds):
            add(
                ExtractedTextSlot(
                    payload_offset=item.start,
                    source_end=item.end,
                    translation_offset=None,
                    source_text=item.text,
                    existing_translation_text="",
                    slot_kind="seeded_source_chain",
                    evidence="recovered_between_source_anchors",
                    control_codes=tuple(
                        ord(character) for character in item.text if ord(character) < 0x20
                    ),
                    identity_start=item.start,
                    identity_end=item.terminator_end,
                )
            )

    for record in scan_inline_unicode_records(payload):
        if not record.source_text and not (
            record.has_translation_delimiter
            and any(c.isprintable() and not c.isspace() for c in record.translation_text)
        ):
            continue
        if not (
            record.has_translation_delimiter
            or is_source_text_candidate(record.source_text)
        ):
            continue
        add(
            ExtractedTextSlot(
                payload_offset=record.text_offset,
                source_end=record.source_end,
                translation_offset=record.translation_offset,
                source_text=record.source_text,
                existing_translation_text=record.translation_text,
                slot_kind="counted_unicode_string",
                evidence="inline_length_record",
                control_codes=record.control_codes,
                identity_start=record.marker_offset,
                identity_end=record.end_offset,
            )
        )

    vm_commands: tuple[VmMessageCommand, ...] = ()
    vm_pool_base: int | None = None
    try:
        vm_commands = find_vm_message_commands(payload)
    except CvmPoolError as error:
        warnings.append(f"cvmmsg3_command_stream_unresolved:{error}")
    if vm_commands:
        anchored_error: CvmPoolError | None = None
        structural_error: CvmPoolError | None = None
        if candidates:
            try:
                vm_pool_base = derive_pool_base_from_source_offsets(
                    payload,
                    vm_commands,
                    candidates,
                )
            except CvmPoolError as error:
                anchored_error = error
        if vm_pool_base is None:
            try:
                vm_pool_base = infer_pool_base(payload, vm_commands)
            except CvmPoolError as error:
                structural_error = error
                try:
                    vm_pool_base = infer_direct_pool_base(payload, vm_commands)
                except CvmPoolError as direct_error:
                    structural_error = CvmPoolError(f"{error}; direct={direct_error}")
                    if candidates:
                        # In a localized archive the independent readable
                        # anchor can be the Chinese display, not the source.
                        try:
                            vm_pool_base = derive_pool_base_from_source_offsets(
                                payload, vm_commands, candidates,
                                include_translation_anchors=True,
                            )
                        except CvmPoolError as display_error:
                            structural_error = CvmPoolError(
                                f"{structural_error}; display_anchors={display_error}"
                            )
        if vm_pool_base is None:
            warnings.append(
                "cvmmsg3_pool_unresolved:"
                f"anchored={anchored_error or 'no independent source anchors'};"
                f"structural={structural_error}"
            )
        if vm_pool_base is not None:
            try:
                layout = parse_direct_pool(payload, vm_commands, vm_pool_base)
            except CvmPoolError as error:
                warnings.append(f"cvmmsg3_pool_parse_failed:{error}")
            else:
                for source, translation in layout.command_slots:
                    # The VM can render the translation even when the source
                    # is empty or only U+0005 (PF's training-scene opening).
                    # Keep the source anchor/identity; never promote loose
                    # display-looking bytes without this exact reference.
                    if not (_visible_characters(source.text)
                            or any(c.isprintable() and not c.isspace() for c in translation.text)):
                        continue
                    source_start = source.offset + source.prefix_size
                    translation_start = translation.offset + translation.prefix_size
                    add(
                        ExtractedTextSlot(
                            payload_offset=source_start,
                            source_end=source_start + len(source.text.encode("utf-16le")),
                            translation_offset=translation_start,
                            source_text=source.text,
                            existing_translation_text=translation.text,
                            slot_kind="cvmmsg3_indexed_pool",
                            evidence="cvmmsg3_exact_reference",
                            control_codes=tuple(
                                ord(character)
                                for character in source.text
                                if ord(character) < 0x20
                            ),
                            identity_start=source.offset,
                            identity_end=translation.offset + len(translation.raw),
                        )
                    )

    exact = [
        slot
        for slot in candidates.values()
        if slot.evidence in {"cvmmsg3_exact_reference", "inline_length_record"}
    ]
    for offset, slot in tuple(candidates.items()):
        if slot in exact:
            continue
        owner = next(
            (
                item
                for item in exact
                if item.payload_offset < slot.payload_offset
                and slot.source_end <= item.source_end
            ),
            None,
        )
        if owner is not None:
            warnings.append(
                f"contained_suffix_removed:0x{slot.payload_offset:X}->0x{owner.payload_offset:X}"
            )
            del candidates[offset]

    slots = tuple(sorted(candidates.values(), key=lambda item: item.payload_offset))
    return TextExtractionReport(
        slots=slots,
        warnings=tuple(warnings),
        ambiguous_ascii_pairs=tuple(find_ambiguous_ascii_display_pairs(payload)),
        vm_command_count=len(vm_commands),
        vm_pool_base=vm_pool_base,
    )
