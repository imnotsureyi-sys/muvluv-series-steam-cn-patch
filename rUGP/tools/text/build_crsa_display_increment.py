"""Build a hash-bound cumulative RUO from reviewed display-slot increments.

Only exact CVMMsg3 translation references are changed. Original pool bytes,
source slots, command metadata, and every unrelated inherited RUO route remain
identical. Outputs are candidates; this command never installs them.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import re
import struct

from rUGP.formats.rio.crsa import decode_crsa_encrypted, encode_crsa_encrypted, read_crsa_record
from rUGP.formats.rio.crsa_vm_pool import find_vm_message_commands, parse_direct_pool
from rUGP.formats.rio.crypto import RIO_KEY, decode_encrypted_block, decode_extent_offset, decode_extent_size
from rUGP.formats.rio.ruo import build_ruo, read_footer
from rUGP.tools.text.audit_crsa_display_gaps import sha


def decode_controls(text: str) -> str:
    return re.sub(r'<([0-1][0-9A-F])>', lambda m: chr(int(m[1], 16)), text)


def append_translations(payload: bytes, pool_base: int, entries: list[dict]) -> bytes:
    commands = find_vm_message_commands(payload)
    layout = parse_direct_pool(payload, commands, pool_base)
    nonzero = [c for c in commands if (c.source_index, c.translation_index) != (0, 0)]
    pairs = {c.object_offset: p for c, p in zip(nonzero, layout.command_slots)}
    prefix = bytearray(payload[:pool_base - 4])
    pool = bytearray(payload[pool_base:layout.end])
    targets = {}
    for entry in entries:
        order = entry['command_order']
        if not 1 <= order <= len(commands):
            raise ValueError('target command order is outside the message stream')
        if order in targets:
            raise ValueError('duplicate target command')
        command = commands[order - 1]
        source, translation = pairs[command.object_offset]
        if (command.command_offset != entry['command_offset']
                or source.offset + source.prefix_size != entry['source_offset']
                or translation.offset + translation.prefix_size != entry['translation_offset']
                or sha(source.raw) != entry['source_slot_sha256']
                or sha(translation.raw) != entry['display_slot_sha256']):
            raise ValueError(f'command {order}: source/display binding changed')
        target = decode_controls(entry['target_text'])
        if '\x00' in target or not any(c.isprintable() and not c.isspace() for c in target):
            raise ValueError('target must contain visible text and no embedded NUL')
        # Preserve every control token, including leading U+0005. Do not append
        # generic terminators: these four messages have no trailing U+0001.
        if [c for c in target if ord(c)<32] != [c for c in translation.text if ord(c)<32]:
            raise ValueError('target changes the display control sequence')
        if command.translation_index_field + 4 > len(prefix):
            raise ValueError('command is not before pool')
        new_index = len(pool)//2
        raw = translation.raw[:translation.prefix_size] + (target+'\x00').encode('utf-16le')
        pool.extend(raw)
        struct.pack_into('<I', prefix, command.translation_index_field, new_index)
        targets[order] = (new_index, raw)
    rebuilt = bytes(prefix) + struct.pack('<I',len(pool)//2) + bytes(pool) + payload[layout.end:]
    after = find_vm_message_commands(rebuilt)
    if len(after) != len(commands):
        raise ValueError('command count changed')
    for order, (before, now) in enumerate(zip(commands, after),1):
        expected = before
        if order in targets:
            records = list(before.first_records)
            records[1] = (targets[order][0], *records[1][1:])
            expected = replace(before, first_records=tuple(records))
        if now != expected:
            raise ValueError(f'command metadata changed at {order}')
    after_layout = parse_direct_pool(rebuilt, after, pool_base)
    for c, pair in zip(nonzero, after_layout.command_slots):
        old_source, old_translation = pairs[c.object_offset]
        order = commands.index(c)+1
        if pair[0] != old_source or pair[1].raw != (targets[order][1] if order in targets else old_translation.raw):
            raise ValueError('source or translation readback mismatch')
    if rebuilt[pool_base:layout.end] != payload[pool_base:layout.end]:
        raise ValueError('original pool changed')
    if rebuilt[after_layout.end:] != payload[layout.end:]:
        raise ValueError('suffix changed')
    return rebuilt


def build(spec: dict, source: Path, base_ruo: Path, output: Path) -> dict:
    source, base_ruo, output = source.resolve(), base_ruo.resolve(), output.resolve()
    if output.exists() or output in (source, base_ruo):
        raise ValueError('output must be a new file distinct from inputs')
    base_bytes = base_ruo.read_bytes()
    if sha(base_bytes) != spec['base_ruo_sha256']:
        raise ValueError('base RUO has changed; reconcile against current routes first')
    _, inherited = read_footer(base_ruo, spec['unit_size'])
    key = int(spec['source_raw_key'],0)
    if ('source_logical_byte_offset' in spec
            and decode_extent_offset(key,spec['unit_size']) != spec['source_logical_byte_offset']):
        raise ValueError('route key does not decode to the declared logical source offset')
    routed = [r for r in inherited if r.source_raw_offset == key]
    if routed:
        original = read_crsa_record(base_ruo, decode_extent_offset(routed[0].ruo_raw_offset,spec['unit_size']))
    else:
        original = read_crsa_record(source, spec['block_offset'])
    if sha(original.record) != spec['effective_record_sha256']:
        raise ValueError('effective CRsa has changed; cannot overwrite a newer translation')
    rebuilt = append_translations(original.plaintext, spec['pool_base'], spec['entries'])
    identity = encode_crsa_encrypted(original.plaintext, template_header=original.encrypted_header)
    if original.header + identity != original.record:
        raise ValueError('identity reencode mismatch')
    encrypted = encode_crsa_encrypted(rebuilt, template_header=original.encrypted_header)
    plain, consumed, _ = decode_crsa_encrypted(encrypted)
    if plain != rebuilt or consumed != len(encrypted):
        raise ValueError('strict encrypted readback mismatch')
    if decode_encrypted_block(encrypted, RIO_KEY).plaintext != rebuilt:
        raise ValueError('independent compatible reader mismatch')
    record = original.header + encrypted
    report = build_ruo(output, spec['unit_size'], [(key,record)], base_ruo=base_ruo)
    report['increment_spec_sha256'] = sha(json.dumps(spec,ensure_ascii=False,sort_keys=True).encode('utf-8'))
    report['target_ids'] = [entry['stable_id'] for entry in spec['entries']]
    _, after = read_footer(output, spec['unit_size'])
    by_key = {r.source_raw_offset:r for r in after}
    built_bytes = output.read_bytes()
    for route in inherited:
        if route.source_raw_offset == key:
            continue
        if by_key[route.source_raw_offset] != route:
            raise ValueError('inherited route metadata changed')
        start = decode_extent_offset(route.ruo_raw_offset,spec['unit_size'])
        end = start + decode_extent_size(route.replacement_raw_size)
        if built_bytes[start:end] != base_bytes[start:end]:
            raise ValueError('inherited route bytes changed')
    target = by_key[key]
    actual = read_crsa_record(output,decode_extent_offset(target.ruo_raw_offset,spec['unit_size']))
    if actual.record != record or decode_extent_size(target.replacement_raw_size) != len(record):
        raise ValueError('RUO CRsa extent/readback mismatch')
    if base_ruo.read_bytes() != base_bytes:
        raise ValueError('base changed during build')
    report['validation'] = dict(identity_reencode=True, strict_all_checksums=True,
        compatible_plaintext_readback=True, all_vm_commands_reparsed=True,
        only_target_translation_indices_changed=True, original_pool_preserved=True,
        all_source_slots_preserved=True, unrelated_display_slots_preserved=True,
        object_suffix_preserved=True, all_inherited_routes_preserved=True,
        inherited_routes=len(inherited), runtime_tested=False, installed=False)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--base-ruo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding='utf-8'))
    report = build(spec,args.source,args.base_ruo,args.output)
    args.output.with_suffix(args.output.suffix+'.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(sha256=report['file_sha256'], routes=report['redirect_count'], validation=report['validation'])))
