"""Rebind reviewed speaker delimiters to current CRsa text after layout edits.

Only differences in U+0003/U+000A are accepted automatically. Current words,
controls and line breaks are preserved; other edits require explicit review.
The returned entries are consumed by the existing native-field writer.
"""
from __future__ import annotations

import re

from rUGP.formats.rio.crsa_vm_edit import text_digest
from rUGP.formats.rio.crsa_vm_fields import inventory_vm_pool
from rUGP.formats.rio.crsa_vm_stream import native_message_commands, parse_crsa_vm_stream

MALFORMED = re.compile(r"^([\x01-\x1f]*)([^【】「」\r\n]+)【(.*)】([\x01-\x1f]*)$", re.S)
NORMAL = re.compile(r"^([\x01-\x1f]*)【([^】]+)】「(.*)」([\x01-\x1f]*)$", re.S)


def without_layout(text: str) -> str:
    return text.replace("\x03", "").replace("\n", "")


def rebase_delimiters(current: str, before: str, target: str) -> str:
    if without_layout(current) == without_layout(target):
        return current
    if without_layout(current) != without_layout(before):
        raise ValueError("wording or non-layout controls changed; review speaker repair again")
    desired = NORMAL.fullmatch(target)
    if desired is None:
        raise ValueError("reviewed target has no native speaker prefix")
    old = MALFORMED.fullmatch(before)
    now = MALFORMED.fullmatch(current)
    if old:
        if now is None or old[2] != desired[2] or before != old[1]+old[2]+'【'+desired[3]+'】'+old[4]:
            raise ValueError("speaker repair changes more than delimiters")
        return now[1]+'【'+now[2]+'】「'+now[3]+'」'+now[4]
    # The separately reviewed PM line lost its complete name and quotation wrapper.
    if before != desired[1]+desired[3]+desired[4]:
        raise ValueError("missing-prefix repair changes the body")
    lead = re.match(r"^[\x01-\x1f]*", current)[0]
    tail = re.search(r"[\x01-\x1f]*$", current)[0]
    body = current[len(lead):len(current)-len(tail) if tail else len(current)]
    return lead+'【'+desired[2]+'】「'+body+'」'+tail


def rebind_entries(payload: bytes, game: str, reviewed: list[dict]) -> list[dict]:
    parsed = parse_crsa_vm_stream(payload, game)
    inventory = inventory_vm_pool(payload, native_message_commands(parsed), parsed["pool_base"])
    refs = {(r.command_order, r.language, r.role): r for r in inventory.references}
    orders = {c["order"]: i+1 for i, c in enumerate(c for c in parsed["commands"] if c["name"] == "CVmMsg3")}
    result = []
    for entry in reviewed:
        command = parsed["commands"][entry["command_order"]-1]
        if command["name"] != "CVmMsg3" or command["target"] != entry["command_target"]:
            raise ValueError("native command identity changed")
        order = orders[entry["command_order"]]
        source, display = refs[order, 0, "message"], refs[order, 1, "message"]
        if text_digest(source.text) != entry["source_message_sha256"]:
            raise ValueError("source identity changed")
        target = rebase_delimiters(display.text, entry["before_text"], entry["target_text"])
        if target != display.text:
            result.append(dict(entry, source_message_index=source.index, display_message_index=display.index,
                               display_message_sha256=text_digest(display.text), target_text=target))
    return result
