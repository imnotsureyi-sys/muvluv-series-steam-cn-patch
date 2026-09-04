"""Read-only all-volume CRsa census and display-gap evidence (no auto-translation).

Raw six-byte signatures supplement the ICI: unnamed scripts and non-default
five-byte header tails must not disappear from the denominator. JSON contains
retail text and belongs in an ignored local output directory.
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from dataclasses import asdict
import hashlib
import json
import mmap
from pathlib import Path
import re
import struct

from rUGP.formats.rio.crsa import CRSA_PREFIX, UNICODE_MARKER, read_crsa_record, parse_unicode_string_at
from rUGP.formats.rio.crsa_text import (
    extract_text_slots, scan_inline_unicode_records, scan_utf16_strings,
)
from rUGP.formats.rio.crsa_vm_pool import find_vm_message_commands, parse_direct_pool
from rUGP.tools.catalog.rio_inventory import build_inventory, decode_class_name


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def visible(text: str) -> bool:
    return any(c.isprintable() and not c.isspace() for c in text)


def declarations(payload: bytes) -> list[dict]:
    rows = []
    for match in re.finditer(b'\xff\xff', payload):
        pos = match.start()
        if pos + 5 > len(payload):
            continue
        size = payload[pos + 4]
        if not 1 <= size <= 64 or pos + 5 + size > len(payload):
            continue
        try:
            name = decode_class_name(payload[pos + 5:pos + 5 + size])
        except (IndexError, ValueError):
            continue
        if re.fullmatch(r'[A-Za-z0-9_&-]{1,64}', name):
            rows.append(dict(offset=pos, end=pos + 5 + size,
                             schema=int.from_bytes(payload[pos+2:pos+4], 'little'), name=name))
    return rows


def inspect_payload(payload: bytes) -> dict:
    extraction = extract_text_slots(payload)
    slots = [asdict(s) for s in extraction.slots]
    intervals = sorted((s.identity_start, s.identity_end) for s in extraction.slots)
    starts = [a for a, _ in intervals]
    maximum_ends = []
    for _, end in intervals:
        maximum_ends.append(max(end, maximum_ends[-1] if maximum_ends else 0))
    def owned(start, end):
        index = bisect_right(starts, start) - 1
        return index >= 0 and maximum_ends[index] >= end
    commands = find_vm_message_commands(payload)
    refs = []
    pool_end = None
    extracted_offsets = {s.payload_offset for s in extraction.slots}
    if extraction.vm_pool_base is not None:
        layout = parse_direct_pool(payload, commands, extraction.vm_pool_base)
        pool_end = layout.end
        pairs = iter(layout.command_slots)
        text_order = 0
        for order, command in enumerate(commands, 1):
            if command.source_index == command.translation_index == 0:
                continue
            text_order += 1
            source, translation = next(pairs)
            source_offset = source.offset + source.prefix_size
            refs.append(dict(command_order=order, text_command_order=text_order,
                             command=asdict(command), source=asdict(source),
                             translation=asdict(translation),
                             extracted=source_offset in extracted_offsets))
    counted = scan_inline_unicode_records(payload)
    strings = scan_utf16_strings(payload)
    malformed_counted = []
    markers = list(re.finditer(re.escape(UNICODE_MARKER), payload))
    for marker in markers:
        try:
            parse_unicode_string_at(payload,marker.start())
        except ValueError as error:
            malformed_counted.append(dict(offset=marker.start(),error=str(error)))
    # Language-independent candidate evidence; these remain unconfirmed until
    # a command/field owner is established. Both byte parities are considered.
    unowned = [dict(start=s.start, end=s.end, parity=s.parity, text=s.text)
               for s in strings if not owned(s.start, s.end) and visible(s.text)
               and (s.text.startswith('\x05') or '\\|' in s.text
                    or (len(s.text) > 2 and s.text[-1] in '\x01\x02'))]
    decls = declarations(payload)
    # Inspect every occurrence of the selected cached class independently of
    # the production parser's group/count/order gates. Never promote these hits.
    cached = []
    selected_objects = {c.object_offset for c in commands}
    for token in sorted({c.class_reference for c in commands if c.class_reference is not None}):
        for match in re.finditer(re.escape(struct.pack('<H', token)), payload):
            pos = match.start()
            if pos in selected_objects or pos + 16 > len(payload):
                continue
            offset, flags, group, index, first, second = struct.unpack_from('<IIHHBB', payload, pos+2)
            if offset % 4 == 0 and offset <= 0x40000000 and 1 <= first <= 16 and second <= 16:
                cached.append(dict(object_offset=pos, command_offset=offset,
                                   flags=flags, group=group, index=index,
                                   first_count=first, second_count=second))
    return dict(slots=slots, warnings=list(extraction.warnings),
                ambiguous_ascii_pairs=extraction.ambiguous_ascii_pairs,
                vm_pool_base=extraction.vm_pool_base, vm_pool_end=pool_end, vm_commands=len(commands),
                vm_control_commands=sum(c.source_index == c.translation_index == 0 for c in commands),
                refs=refs, declarations=decls, cached_command_candidates=cached,
                counted_records=len(counted),
                counted_markers=len(markers), malformed_counted_markers=malformed_counted,
                unowned_counted=[asdict(s) for s in counted if not owned(s.marker_offset, s.end_offset)],
                unowned_pool_strings=[dict(start=s.start,end=s.end,text=s.text) for s in strings
                    if pool_end is not None and s.parity == extraction.vm_pool_base % 2
                    and extraction.vm_pool_base <= s.start < s.end <= pool_end
                    and not owned(s.start,s.end)],
                nul_candidates=len(strings), unowned_marked_strings=unowned)


def json_default(value):
    if isinstance(value, bytes):
        return value.hex()
    raise TypeError(type(value).__name__)


def audit(root: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    ici, = root.glob('*.rio.ici')
    main = root / ici.name[:-4]
    volumes = sorted([main, *root.glob(main.name + '.00[2-9]')])
    inventory = build_inventory(ici=ici, main_rio=main, volumes=volumes[1:])
    (output / 'inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    results = []
    for volume in volumes:
        before = (volume.stat().st_size, volume.stat().st_mtime_ns)
        item = dict(name=volume.name, bytes=before[0], mtime_ns=before[1], signatures=0, failures=[], blocks=[])
        with volume.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            item['sha256'] = sha(data)
            cursor = 0
            while (offset := data.find(CRSA_PREFIX, cursor)) >= 0:
                cursor = offset + 1
                item['signatures'] += 1
                try:
                    record = read_crsa_record(volume, offset)
                except ValueError as error:
                    item['failures'].append(dict(offset=offset, error=str(error)))
                    continue
                name = f'{volume.name}.{offset:010d}'
                # Small decoded script cache only; no archive copy.
                (output / (name + '.plain')).write_bytes(record.plaintext)
                entry = dict(offset=offset, extent=len(record.record),
                             record_sha256=sha(record.record), payload_sha256=sha(record.plaintext),
                             header_hex=record.header.hex(), plaintext_bytes=len(record.plaintext))
                try:
                    evidence = inspect_payload(record.plaintext)
                    (output / (name + '.json')).write_text(
                        json.dumps(evidence, ensure_ascii=False, default=json_default), encoding='utf-8')
                    entry.update(slots=len(evidence['slots']), vm_commands=evidence['vm_commands'],
                                 refs=len(evidence['refs']), omitted_refs=sum(not r['extracted'] for r in evidence['refs']),
                                 warnings=evidence['warnings'], unowned_marked_strings=len(evidence['unowned_marked_strings']),
                                 unowned_counted=len(evidence['unowned_counted']),
                                 cached_candidates=len(evidence['cached_command_candidates']))
                except ValueError as error:
                    entry['parse_failure'] = str(error)
                item['blocks'].append(entry)
                if len(item['blocks']) % 20 == 0:
                    print(f'{volume.name}: {len(item["blocks"])} blocks', flush=True)
        if before != (volume.stat().st_size, volume.stat().st_mtime_ns):
            raise RuntimeError(f'input changed during scan: {volume}')
        results.append(item)
        (output / 'census.json').write_text(json.dumps(dict(root=str(root), volumes=results), indent=2), encoding='utf-8')
        print(f'{volume.name}: {len(item["blocks"])} valid / {item["signatures"]} signatures', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.root.resolve(), args.output.resolve())
