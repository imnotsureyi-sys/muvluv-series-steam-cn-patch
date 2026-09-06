"""Migrate one pinned font digest in a known Photon runtime's read-only data.

The runtime's checks remain enabled and exact. No executable byte, DLL identity,
image route, authorization flag or private runtime is changed. This produces a
new candidate; it never installs one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def sha(data):return hashlib.sha256(data).hexdigest().upper()


def rebind(data, expected_runtime_sha256, old_font_sha256, new_font_sha256):
    if sha(data)!=expected_runtime_sha256.upper():raise ValueError('runtime input hash changed')
    if not all(re.fullmatch('[0-9A-Fa-f]{64}',v) for v in (old_font_sha256,new_font_sha256)):
        raise ValueError('font digests must be SHA-256')
    old,new=old_font_sha256.upper().encode(),new_font_sha256.upper().encode()
    if old==new or data.count(old+b'\0')!=1:raise ValueError('expected exactly one old font digest')
    offset=data.index(old+b'\0')
    if len(data)<64 or data[:2]!=b'MZ':raise ValueError('not a PE runtime')
    pe=struct.unpack_from('<I',data,0x3C)[0]
    if data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x14C:
        raise ValueError('not an x86 PE runtime')
    count=struct.unpack_from('<H',data,pe+6)[0];optional=struct.unpack_from('<H',data,pe+20)[0]
    matched=[]
    for i in range(count):
        entry=pe+24+optional+i*40
        name=data[entry:entry+8].rstrip(b'\0')
        size,start=struct.unpack_from('<II',data,entry+16)
        flags=struct.unpack_from('<I',data,entry+36)[0]
        if start<=offset and offset+65<=start+size:
            matched.append((name,flags))
    if matched!=[(b'.rdata',0x40000040)]:
        raise ValueError('font digest is not uniquely inside ordinary read-only data')
    result=data[:offset]+new+data[offset+64:]
    if result[:offset]!=data[:offset] or result[offset+64:]!=data[offset+64:]:
        raise ValueError('non-font-pin byte changed')
    return result,dict(schema='photon-runtime-font-pin-migration/v1',runtime_before_sha256=sha(data),
        runtime_after_sha256=sha(result),font_before_sha256=old.decode(),font_after_sha256=new.decode(),
        file_offset=offset,permitted_byte_span=64,all_other_bytes_identical=True,exact_guard_retained=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--runtime-sha256',required=True)
    parser.add_argument('--old-font-sha256',required=True)
    parser.add_argument('--font',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report_path=args.output.with_suffix(args.output.suffix+'.json')
    if args.output.exists() or report_path.exists():raise ValueError('output and report must be new files')
    result,report=rebind(args.runtime.read_bytes(),args.runtime_sha256,args.old_font_sha256,sha(args.font.read_bytes()))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as f:f.write(result)
    with report_path.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report))


if __name__=='__main__':main()
