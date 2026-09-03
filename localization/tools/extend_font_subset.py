"""Append missing TrueType glyphs without replacing existing glyphs or metrics.

Both fonts must have the same units per em and compatible licensed provenance.
This tool records hashes; it does not grant font redistribution rights. A donor
variable font may be instantiated at an explicitly supplied weight.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from io import BytesIO
import hashlib
import json
from pathlib import Path

from fontTools import version as fonttools_version
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def glyph_state(font, name):
    glyph=font['glyf'][name]
    coordinates, endpoints, flags=glyph.getCoordinates(font['glyf'])
    return (list(coordinates), list(endpoints), list(flags),
            bytes(glyph.program.getBytecode()) if hasattr(glyph,'program') else b'',
            font['hmtx'][name], font['vmtx'][name] if 'vmtx' in font else None)


def extend(base_data, donor_data, characters, base_sha256, donor_sha256, weight=None):
    if sha(base_data)!=base_sha256.upper() or sha(donor_data)!=donor_sha256.upper():
        raise ValueError('font input hash changed')
    base=TTFont(BytesIO(base_data),recalcTimestamp=False)
    donor=TTFont(BytesIO(donor_data),recalcTimestamp=False)
    if 'glyf' not in base or 'glyf' not in donor or 'fvar' in base:
        raise ValueError('base must be static TrueType; donor must have TrueType outlines')
    if base['head'].unitsPerEm != donor['head'].unitsPerEm:
        raise ValueError('font units per em differ')
    if 'fvar' in donor:
        if weight is None or {axis.axisTag for axis in donor['fvar'].axes}!={'wght'}:
            raise ValueError('variable donor requires an explicit single-axis weight')
        donor=instantiateVariableFont(donor,{'wght':weight},inplace=True)
        # Instancing can leave fractional coordinates in memory. Canonicalize
        # the fixed TrueType instance before copying and comparing its glyphs.
        fixed=BytesIO();donor.save(fixed)
        donor=TTFont(BytesIO(fixed.getvalue()),recalcTimestamp=False)
    elif weight is not None:
        raise ValueError('weight supplied for a static donor')
    points=sorted(set(map(ord,characters)))
    old_cmap=dict(base.getBestCmap());donor_cmap=donor.getBestCmap()
    if not points or any(p in old_cmap for p in points):
        raise ValueError('only absent codepoints may be added')
    if any(p not in donor_cmap or p>0xFFFF or p<32 for p in points):
        raise ValueError('requested BMP codepoint is missing from donor or invalid')
    original_order=list(base.getGlyphOrder())
    original_states=[glyph_state(base,n) for n in original_order]
    # Existing shaping tables must retain every byte after recompilation.
    stable_tables={tag:base.getTableData(tag) for tag in base.keys()
                   if tag not in {'GlyphOrder','head','hhea','vhea','maxp','hmtx','vmtx','cmap','loca','glyf','post'}}
    added=[]
    for point in points:
        donor_name=donor_cmap[point];glyph=donor['glyf'][donor_name]
        if glyph.isComposite():
            raise ValueError('composite donor needs an explicit dependency/decomposition contract')
        name=f'nativeIncrement{point:04X}'
        if name in base.getGlyphOrder():raise ValueError('new glyph name collision')
        base.setGlyphOrder(base.getGlyphOrder()+[name])
        base['glyf'][name]=deepcopy(glyph)
        base['hmtx'][name]=donor['hmtx'][donor_name]
        if 'vmtx' in base:
            if 'vmtx' not in donor:raise ValueError('donor lacks required vertical metrics')
            base['vmtx'][name]=donor['vmtx'][donor_name]
        for table in base['cmap'].tables:
            if table.isUnicode() and table.format in (4,12):table.cmap[point]=name
        added.append(dict(codepoint=f'U+{point:04X}',horizontal_metrics=list(base['hmtx'][name])))
    out=BytesIO();base.save(out,reorderTables=False);data=out.getvalue()
    after=TTFont(BytesIO(data),recalcTimestamp=False)
    if len(after.getGlyphOrder())!=len(original_order)+len(points):raise ValueError('glyph count changed unexpectedly')
    for index,expected in enumerate(original_states):
        if glyph_state(after,after.getGlyphOrder()[index])!=expected:
            raise ValueError('existing glyph outline, instructions or metrics changed')
    for point,name in old_cmap.items():
        if after.getGlyphID(after.getBestCmap()[point])!=original_order.index(name):
            raise ValueError('existing codepoint changed glyph identity')
    for tag,expected in stable_tables.items():
        if after.getTableData(tag)!=expected:raise ValueError(f'existing table changed: {tag}')
    for point in points:
        if glyph_state(after,after.getBestCmap()[point])!=glyph_state(donor,donor_cmap[point]):
            raise ValueError('new glyph differs from fixed donor instance')
    return data,dict(schema='font-missing-glyph-increment/v1',base_sha256=sha(base_data),
        donor_sha256=sha(donor_data),donor_weight=weight,fonttools_version=fonttools_version,
        output_sha256=sha(data),old_glyph_count=len(original_order),new_glyph_count=len(after.getGlyphOrder()),
        added=added,existing_glyphs_metrics_cmap_and_shaping_preserved=True,
        base_family=base['name'].getDebugName(1),donor_family=donor['name'].getDebugName(1),
        donor_copyright=donor['name'].getDebugName(0),donor_license=donor['name'].getDebugName(13))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,required=True)
    parser.add_argument('--donor',type=Path,required=True)
    parser.add_argument('--base-sha256',required=True)
    parser.add_argument('--donor-sha256',required=True)
    parser.add_argument('--characters',required=True)
    parser.add_argument('--weight',type=float)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report_path=args.output.with_suffix(args.output.suffix+'.json')
    if args.output.exists() or report_path.exists():raise ValueError('output and report must be new files')
    data,report=extend(args.base.read_bytes(),args.donor.read_bytes(),args.characters,args.base_sha256,args.donor_sha256,args.weight)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:stream.write(data)
    with report_path.open('x',encoding='utf-8') as stream:json.dump(report,stream,ensure_ascii=False,indent=2)
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
