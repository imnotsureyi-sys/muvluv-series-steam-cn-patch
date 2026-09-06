"""Hash-bound edits to native PF/PM CRsa message and annotation fields.

Reviewed text is written into its native slot or unused fixed-size pool space
whenever possible. Reusing a non-empty orphan or extending a pool requires an
explicit, hash-bound storage contract in the reviewed entry. Native command
targets, resource keys, CStrings and voice references must remain unchanged.
This module does not install or execute game files.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct

from .crsa_vm_fields import inventory_vm_pool, parse_annotation
from .crsa_vm_stream import parse_crsa_vm_stream, native_message_commands


SUPPORTED_GAMES = {"pf", "pm"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def text_digest(text: str) -> str:
    return digest(text.encode("utf-16le", errors="strict"))


def require_hash(actual: str, expected: str, label: str) -> None:
    if actual != expected.upper():
        raise ValueError(f"{label}: source hash changed")


def visible_target(text: str) -> bytes:
    if "\0" in text or "\u2060" in text or not any(c.isprintable() and not c.isspace() for c in text):
        raise ValueError("target requires visible text and no embedded NUL")
    return text.encode("utf-16le", errors="strict")


@dataclass(frozen=True)
class EditResult:
    payload: bytes
    report: dict


def _splice(data: bytes, edits: list[tuple[int, int, bytes]]) -> bytes:
    pieces = []
    cursor = 0
    for start, end, replacement in sorted(edits):
        if not cursor <= start <= end <= len(data):
            raise ValueError("overlapping or out-of-range native edits")
        pieces.extend((data[cursor:start], replacement))
        cursor = end
    pieces.append(data[cursor:])
    return b"".join(pieces)


def _semantic(value, string_changes=None):
    """Remove serialized positions, retaining native member/branch offsets."""
    if isinstance(value, dict):
        position_keys = {"start", "end", "body", "reference_offset"}
        is_string = "text" in value and "width" in value and "role" in value
        if (is_string or value.get("kind") == "object"
                or ("order" in value and "body" in value)
                or set(value) == {"offset", "size"}):
            position_keys.add("offset")
        result = {key: _semantic(item, string_changes) for key, item in value.items()
                  if key not in position_keys}
        if is_string and string_changes and value["start"] in string_changes:
            result["text"] = string_changes[value["start"]]
        return result
    if isinstance(value, (list, tuple)):
        return [_semantic(item, string_changes) for item in value]
    return value


def edit_native_fields(payload: bytes, game: str, entries: list[dict],
                       expected_payload_sha256: str) -> EditResult:
    require_hash(digest(payload), expected_payload_sha256, "CRsa payload")
    if game not in SUPPORTED_GAMES:
        raise ValueError("unsupported native game")
    if not entries:
        raise ValueError("no reviewed native edits")
    parsed = parse_crsa_vm_stream(payload, game)
    commands = native_message_commands(parsed)
    inventory = inventory_vm_pool(payload, commands, parsed["pool_base"])
    if any(r.error for r in inventory.references if r.role == "message"):
        raise ValueError("invalid primary reference in input")
    if any(len(c.first_records) != 2 for c in commands):
        raise ValueError("writer requires exactly two message languages")
    refs = {(r.command_order, r.language, r.role): r for r in inventory.references}
    annotations = {(a.command_order, a.language): a for a in inventory.annotations}
    message_orders = {c["order"]: i + 1 for i, c in enumerate(
        c for c in parsed["commands"] if c["name"] == "CVmMsg3")}
    prefix_edits = []
    original_pool = payload[inventory.base:inventory.end]
    pool = bytearray(original_pool)
    index_changes = {}
    target_ref_text = {}
    pool_writes = []
    actions = []
    seen = set()
    ids = set()
    cells_by_offset = {cell.offset: cell for cell in inventory.cells}
    unclaimed_by_index = {cell.index: cell for cell in inventory.unclaimed_cells}
    claimed_offsets = {
        ref.cell_offset for ref in inventory.references if ref.cell_offset is not None
    }
    claimed_offsets.update(annotation.cell.offset for annotation in inventory.annotations)
    zero_spans = []
    for cell in inventory.cells:
        available = not cell.text and cell.offset not in claimed_offsets and cell.index != 0
        if available and zero_spans and zero_spans[-1]["index"] + zero_spans[-1]["units"] == cell.index:
            zero_spans[-1]["units"] += 1
        elif available:
            zero_spans.append({"index": cell.index, "units": 1})

    def index_edit(message_order, language, field, new_index):
        identity = (message_order, language, field)
        if identity in index_changes:
            raise ValueError("duplicate native field target")
        command = commands[message_order - 1]
        offset = command.body_offset + 14 + language * 12 + field * 4
        prefix_edits.append((offset, offset + 4, struct.pack("<I", new_index)))
        index_changes[identity] = new_index

    def write_fixed(index, capacity_units, text, placement):
        raw = visible_target(text)
        target_units = len(raw) // 2
        if target_units > capacity_units:
            raise ValueError("target exceeds native pool slot capacity")
        start = index * 2
        end = start + (capacity_units + 1) * 2
        if not 0 <= start < end <= len(original_pool):
            raise ValueError("fixed pool storage is outside the original pool")
        if any(not (end <= old_start or start >= old_end)
               for old_start, old_end, _ in pool_writes):
            raise ValueError("overlapping reviewed pool storage")
        replacement = raw + b"\0\0" + bytes(end - start - len(raw) - 2)
        pool[start:end] = replacement
        pool_writes.append((start, end, placement))
        return dict(kind=placement, index=index, capacity_units=capacity_units,
                    target_units=target_units)

    def clear_fixed(index, capacity_units, placement):
        start = index * 2
        end = start + (capacity_units + 1) * 2
        if not 0 <= start < end <= len(original_pool):
            raise ValueError("cleared pool storage is outside the original pool")
        if any(not (end <= old_start or start >= old_end)
               for old_start, old_end, _ in pool_writes):
            raise ValueError("overlapping reviewed pool storage")
        pool[start:end] = bytes(end - start)
        pool_writes.append((start, end, placement))

    def write_append(text):
        raw = visible_target(text)
        index = len(pool) // 2
        start = len(pool)
        pool.extend(raw + b"\0\0")
        pool_writes.append((start, len(pool), "explicit_append"))
        return dict(kind="explicit_append", index=index,
                    capacity_units=len(raw)//2, target_units=len(raw)//2)

    def allocate_zero_run(text):
        raw = visible_target(text)
        required = len(raw) // 2 + 1
        candidates = [span for span in zero_spans if span["units"] >= required]
        if not candidates:
            return None
        span = min(candidates, key=lambda item: (item["units"], item["index"]))
        index = span["index"]
        span["index"] += required
        span["units"] -= required
        return write_fixed(index, required - 1, text, "unused_zero_run")

    def explicit_storage(entry, text):
        storage = entry.get("storage")
        if not storage:
            raise ValueError("target has no native pool storage; explicit storage contract required")
        kind = storage.get("kind")
        if kind == "append":
            if set(storage) != {"kind"}:
                raise ValueError("unexpected append storage fields")
            return write_append(text)
        if kind != "reuse_unclaimed_cell":
            raise ValueError("unsupported native pool storage contract")
        if set(storage) != {"kind", "index", "sha256", "capacity_units"}:
            raise ValueError("incomplete unclaimed-cell storage contract")
        cell = unclaimed_by_index.get(storage["index"])
        if cell is None or cell.offset in claimed_offsets:
            raise ValueError("reviewed orphan cell is no longer unclaimed")
        capacity = len(cell.raw) // 2 - 1
        if capacity != storage["capacity_units"]:
            raise ValueError("reviewed orphan cell capacity changed")
        require_hash(text_digest(cell.text), storage["sha256"], "reviewed orphan cell")
        claimed_offsets.add(cell.offset)
        return write_fixed(cell.index, capacity, text, "reviewed_unclaimed_cell")

    def bind_message(order, entry):
        source, display = refs[order, 0, "message"], refs[order, 1, "message"]
        require_hash(text_digest(source.text), entry["source_message_sha256"], "source message")
        require_hash(text_digest(display.text), entry["display_message_sha256"], "display message")
        if (source.index != entry["source_message_index"]
                or display.index != entry["display_message_index"]):
            raise ValueError("message index binding changed")
        return source, display

    def bind_annotation(order, expected):
        language = expected["language"]
        annotation = annotations.get((order, language))
        if annotation is None:
            raise ValueError("annotation has no structurally recovered owner")
        require_hash(text_digest(annotation.cell.text), expected["sha256"], "annotation")
        if (annotation.native_index != expected["native_index"]
                or annotation.cell.offset != expected["cell_offset"]
                or annotation.index_field_offset != expected["index_field_offset"]
                or annotation.binding != expected["binding"]):
            raise ValueError("annotation ownership binding changed")
        if any("conflicts" in issue for issue in inventory.issues
               if issue.startswith(f"command_{order}:language_{language}:annotation:")):
            raise ValueError("conflicting annotation ownership")
        return annotation

    for entry in entries:
        if entry.get("status") != "reviewed" or entry.get("review_status") not in ("keep", "revise"):
            raise ValueError("native writer requires resolved, reviewed entries")
        stable_id = entry["stable_id"]
        if stable_id in ids:
            raise ValueError("duplicate stable ID")
        ids.add(stable_id)
        action, order = entry["action"], entry["command_order"]
        if not 1 <= order <= len(parsed["commands"]):
            raise ValueError("command order outside stream")
        command = parsed["commands"][order - 1]
        if command["target"] != entry["command_target"]:
            raise ValueError("native command target changed")
        identity = (action, order)
        if identity in seen:
            raise ValueError("duplicate action on native command")
        seen.add(identity)

        if action in ("replace_display_message", "set_display_annotation", "repair_source_annotation"):
            if command["name"] != "CVmMsg3":
                raise ValueError("not a message command")
            message_order = message_orders[order]
            source, display = bind_message(message_order, entry)
            if action == "replace_display_message":
                target = entry["target_text"]
                raw = visible_target(target)
                if [c for c in target if ord(c) < 32] != [c for c in display.text if ord(c) < 32]:
                    raise ValueError("display control sequence changed")
                if command["fields"]["first_records"][1][1:] != (0, 0):
                    raise ValueError("message replacement with auxiliaries needs an explicit combined contract")
                cell = cells_by_offset.get(display.cell_offset)
                if cell is None or display.error or not display.at_cell_start:
                    raise ValueError("display message has no complete native slot")
                placement = write_fixed(
                    cell.index, len(cell.raw)//2 - 1, target, "native_display_message_slot")
                target_ref_text[message_order, 1, "message"] = target
            elif action == "repair_source_annotation":
                annotation = bind_annotation(message_order, entry["annotation_source"])
                if annotation.language != 0 or not all(annotation.keys_in_message):
                    raise ValueError("source annotation keys do not bind to the source message")
                index_edit(message_order, 0, 1, annotation.cell.index)
                target_ref_text[message_order, 0, "annotation"] = annotation.cell.text
                placement = None
            else:
                if not entry["annotation_sources"]:
                    raise ValueError("display annotation needs a source provenance binding")
                for expected in entry["annotation_sources"]:
                    bind_annotation(message_order, expected)
                current_aux = command["fields"]["first_records"][1][1]
                if current_aux != entry["display_annotation_index"]:
                    raise ValueError("display annotation index changed")
                if current_aux and not any(e["language"] == 1 for e in entry["annotation_sources"]):
                    raise ValueError("existing display annotation must be explicitly reviewed")
                target = entry["target_text"]
                visible_target(target)
                pairs = parse_annotation(target)
                if not pairs or not all(key in display.text for key, _ in pairs):
                    raise ValueError("annotation key absent from current display message")
                if len({key for key, _ in pairs}) != len(pairs):
                    raise ValueError("duplicate annotation keys")
                destination = annotations.get((message_order, 1))
                destination_cell = destination.cell if destination is not None else None
                if destination_cell is None:
                    display_cell = cells_by_offset.get(display.cell_offset)
                    neighbor = cells_by_offset.get(display_cell.end) if display_cell else None
                    neighbor_pairs = parse_annotation(neighbor.text) if neighbor else None
                    if (neighbor_pairs and neighbor.offset not in claimed_offsets
                            and all(key in display.text for key, _ in neighbor_pairs)):
                        destination_cell = neighbor
                placement = None
                if destination_cell is not None:
                    capacity = len(destination_cell.raw) // 2 - 1
                    if len(visible_target(target)) // 2 <= capacity:
                        claimed_offsets.add(destination_cell.offset)
                        placement = write_fixed(
                            destination_cell.index, capacity, target,
                            "native_display_annotation_slot")
                    else:
                        claimed_offsets.add(destination_cell.offset)
                        clear_fixed(destination_cell.index, capacity,
                                    "retired_small_annotation_slot")
                if placement is None:
                    placement = allocate_zero_run(target)
                if placement is None:
                    placement = explicit_storage(entry, target)
                index_edit(message_order, 1, 1, placement["index"])
                target_ref_text[message_order, 1, "annotation"] = target
        else:
            raise ValueError(f"unsupported native edit action: {action}")
        action_report = dict(stable_id=stable_id, action=action, command_order=order)
        if placement is not None:
            action_report["storage"] = placement
        actions.append(action_report)

    if len(pool) // 2 > 0xFFFFFFFF:
        raise ValueError("native pool exceeds 32-bit code-unit length")
    prefix = _splice(payload[:inventory.base - 4], prefix_edits)
    result = prefix + struct.pack("<I", len(pool)//2) + bytes(pool) + payload[inventory.end:]
    after = parse_crsa_vm_stream(result, game)
    for key in ("version", "allocation", "metadata", "command_count", "classes", "cache_entries", "suffix_refs", "zero_padding"):
        if parsed[key] != after[key]:
            raise ValueError(f"native metadata changed: {key}")
    expected_commands = _semantic(parsed["commands"])
    for (message_order, language, field), index in index_changes.items():
        native_order = next(order for order, value in message_orders.items() if value == message_order)
        expected_commands[native_order-1]["fields"]["first_records"][language][field] = index
    if expected_commands != _semantic(after["commands"]):
        raise ValueError("non-target native command semantics changed")
    if _semantic(parsed["strings"]) != _semantic(after["strings"]):
        raise ValueError("non-target CString changed")
    if result[after["pool_end"]:] != payload[inventory.end:]:
        raise ValueError("native suffix changed")
    actual_original_pool = result[after["pool_base"]:after["pool_base"]+len(original_pool)]
    allowed = bytearray(len(original_pool))
    for start, end, _ in pool_writes:
        if start < len(original_pool):
            allowed[start:min(end, len(original_pool))] = b"\1" * (min(end, len(original_pool))-start)
    if any(before != now and not permitted
           for before, now, permitted in zip(original_pool, actual_original_pool, allowed)):
        raise ValueError("unreviewed original pool byte changed")
    new_inventory = inventory_vm_pool(result, native_message_commands(after), after["pool_base"])
    new_refs = {(r.command_order, r.language, r.role): r for r in new_inventory.references}
    for identity, before in refs.items():
        now = new_refs.get(identity)
        field_number = ("message", "annotation", "directive").index(before.role)
        field_identity = (identity[0], identity[1], field_number)
        if identity in target_ref_text:
            expected_index = index_changes.get(field_identity, before.index)
            if now is None or (now.index, now.text) != (expected_index, target_ref_text[identity]):
                raise ValueError("reviewed pool reference did not receive its target")
        elif field_identity not in index_changes:
            if now is None or (now.index, now.text) != (before.index, before.text):
                raise ValueError("unrelated pool reference changed")
    if set(new_refs) != set(refs) | set(target_ref_text):
        raise ValueError("unexpected pool reference identity changed")
    for (message_order, language, field), _ in index_changes.items():
        role = ("message", "annotation", "directive")[field]
        ref = new_refs[message_order, language, role]
        if ref.error or not ref.at_cell_start:
            raise ValueError("edited reference does not point to a complete pool cell")
        if role == "annotation":
            ann = next(a for a in new_inventory.annotations if a.command_order == message_order and a.language == language)
            if ann.binding != "exact_native_reference" or not all(ann.keys_in_message):
                raise ValueError("edited annotation did not bind exactly")
    for identity, target in target_ref_text.items():
        if new_refs[identity].text != target:
            raise ValueError("reviewed target text changed during native readback")
    changed_indices = 0
    for (message_order, language, field), new_index in index_changes.items():
        if commands[message_order-1].first_records[language][field] != new_index:
            changed_indices += 1
    placements = {}
    for action in actions:
        if "storage" in action:
            placements[action["storage"]["kind"]] = placements.get(action["storage"]["kind"], 0) + 1
    return EditResult(result, dict(
        before_sha256=digest(payload), after_sha256=digest(result),
        commands=parsed["command_count"], actions=actions,
        changed_indices=changed_indices, changed_cstrings=0,
        old_pool_units=inventory.declared_units, new_pool_units=len(pool)//2,
        appended_pool_units=len(pool)//2-inventory.declared_units,
        storage_placements=placements,
        serialized_prefix_delta=len(prefix)-(inventory.base-4),
        validation=dict(full_native_readback=True, non_target_command_semantics_preserved=True,
                        only_reviewed_pool_storage_changed=True,
                        pool_size_preserved=len(pool) == len(original_pool),
                        all_source_messages_preserved=True,
                        suffix_and_voices_preserved=True, edited_annotation_keys_bound=True),
    ))
