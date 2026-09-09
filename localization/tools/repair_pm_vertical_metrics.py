"""Repair only the pinned PM font's missing trailing PUA vertical metrics.

No existing metric is inferred or replaced. The 227 absent entries receive
explicit new vertical metrics (1000-unit advance, 880-unit vertical origin),
matching the font's prevailing CJK convention. Horizontal layout is unchanged.
"""
from io import BytesIO
import argparse
import hashlib
import json
from pathlib import Path
import struct

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables.DefaultTable import DefaultTable

PM_SHA256 = '7D555D9B2905A56A8E97D0C2CFF4CC12559013DD8BCBFF41DC254D5C74ACE8E2'


def repair(data):
    digest = hashlib.sha256(data).hexdigest().upper()
    if digest != PM_SHA256:
        raise ValueError('repair is restricted to the reviewed PM font hash')
    font = TTFont(BytesIO(data), recalcTimestamp=False)
    order = font.getGlyphOrder()
    raw_vhea = font.getTableData('vhea')
    raw_vmtx = font.getTableData('vmtx')
    if (len(order), font['vhea'].numberOfVMetrics, len(raw_vmtx)) != (4942, 4715, 18860):
        raise ValueError('unexpected vertical metrics structure')
    cmap = font.getBestCmap()
    if [cmap.get(c) for c in range(0xE100, 0xE1E3)] != order[4715:]:
        raise ValueError('missing entries are not exactly the reviewed trailing PUA range')
    added = []
    for index, name in enumerate(order[4715:], 4715):
        glyph = font['glyf'][name]
        if glyph.isComposite() or glyph.numberOfContours <= 0:
            raise ValueError('unexpected PUA glyph structure')
        added.append({'glyph_id': index, 'codepoint': f'U+{0xE100 + index - 4715:04X}',
                      'advance_height': 1000, 'top_side_bearing': 880 - glyph.yMax})
    # Save a fresh lazy reader, leaving all unrelated tables byte-for-byte raw.
    output = TTFont(BytesIO(data), recalcBBoxes=False, recalcTimestamp=False)
    for tag, payload in {
        'vhea': raw_vhea[:-2] + struct.pack('>H', 4942),
        'vmtx': raw_vmtx + b''.join(struct.pack('>Hh', r['advance_height'], r['top_side_bearing']) for r in added),
    }.items():
        table = DefaultTable(tag)
        table.data = payload
        output[tag] = table
    stream = BytesIO()
    output.save(stream, reorderTables=False)
    result = stream.getvalue()
    checked = TTFont(BytesIO(result), recalcTimestamp=False)
    if len(checked['vmtx'].metrics) != 4942:
        raise ValueError('repaired vertical metrics did not decode completely')
    before = TTFont(BytesIO(data), lazy=True)
    for tag in before.reader.keys():
        a, b = before.reader[tag], checked.reader[tag]
        if tag in {'vhea', 'vmtx'}:
            continue
        if tag == 'head':
            a, b = a[:8] + a[12:], b[:8] + b[12:]
        if a != b:
            raise ValueError(f'unrelated table changed during repair: {tag}')
    if checked.reader['vmtx'][:18860] != raw_vmtx:
        raise ValueError('existing vertical metrics changed')
    return result, {
        'schema': 'photon-pm-vertical-metrics-repair/v1',
        'base_sha256': digest, 'output_sha256': hashlib.sha256(result).hexdigest().upper(),
        'glyph_count': 4942, 'existing_vertical_metrics': 4715, 'added_vertical_metrics': added,
        'policy': 'New PUA vertical metrics only: advance 1000, origin 880. Not recovered historical values.',
        'all_other_tables_identical_except_head_checksum': True,
        'original_vertical_metrics_bytes_preserved': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report_path = args.output.with_suffix('.repair.json')
    if args.output.exists() or report_path.exists():
        raise ValueError('refusing to overwrite an existing artifact')
    data, report = repair(args.input.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(data)
    with report_path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    print(json.dumps({k:v for k,v in report.items() if k != 'added_vertical_metrics'}))


if __name__ == '__main__':
    main()
