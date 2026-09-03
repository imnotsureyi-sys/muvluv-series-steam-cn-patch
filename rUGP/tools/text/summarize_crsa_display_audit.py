"""Re-audit cached payloads and retain every rejected/unresolved candidate."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import re

from rUGP.formats.rio.crsa_text import ALLOWED_CONTROL_CODES
from rUGP.tools.text.audit_crsa_display_gaps import inspect_payload, json_default, sha, visible


def inspect(path: Path) -> tuple[str, dict]:
    return path.stem, inspect_payload(path.read_bytes())


def summarize(cache: Path, output: Path) -> None:
    output.mkdir(parents=True,exist_ok=False)
    totals = Counter()
    classes = Counter()
    rows = []
    candidates = []
    unresolved_bytes = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        for block, current in pool.map(inspect, sorted(cache.glob('*.plain'))):
            previous = json.loads((cache/(block+'.json')).read_text(encoding='utf-8'))
            old = {s['payload_offset']:s for s in previous['slots']}
            new = {s['payload_offset']:s for s in current['slots']}
            # JSON canonicalization normalizes dataclass tuple/list fields.
            new = json.loads(json.dumps(new))
            new = {int(k):v for k,v in new.items()}
            diff = dict(block=block,old_slots=len(old),new_slots=len(new),
                added=[new[k] for k in sorted(new.keys()-old.keys())],
                removed=[old[k] for k in sorted(old.keys()-new.keys())],
                changed=[dict(before=old[k],after=new[k]) for k in old.keys() & new.keys() if old[k]!=new[k]],
                old_pool=previous['vm_pool_base'],new_pool=current['vm_pool_base'],warnings=current['warnings'])
            rows.append(diff)
            totals.update(blocks=1,slots=len(new),vm_commands=current['vm_commands'],
                vm_pairs=len(current['refs']),zero_index_commands=current['vm_control_commands'],
                nul_candidates=current['nul_candidates'],marked_byte_candidates=len(current['unowned_marked_strings']),
                counted_records=current['counted_records'],counted_markers=current['counted_markers'],
                malformed_counted_markers=len(current['malformed_counted_markers']),
                cached_command_candidates=len(current['cached_command_candidates']),warnings=len(current['warnings']))
            classes.update((d['name'],d['schema']) for d in current['declarations'] if 'Msg' in d['name'])
            for r in current['refs']:
                if not visible(r['source']['text']):
                    decision = 'confirmed_display' if visible(r['translation']['text']) else 'do_not_translate'
                    candidates.append(dict(block=block,kind='vm_control_source',decision=decision,
                        reason='exact CVMMsg3 source/display reference' if decision=='confirmed_display' else 'both slots contain only control/whitespace',evidence=r))
                    totals['vm_'+decision] += 1
            for r in current['unowned_counted']:
                text = r['text']
                plain = text.strip(''.join(chr(c) for c in range(32)))
                if not visible(text) or plain in ('\\A','\\|'):
                    decision,reason='do_not_translate','empty/control or engine escape token'
                elif any(ord(c)<32 and ord(c) not in ALLOWED_CONTROL_CODES for c in text):
                    decision,reason='do_not_translate','embedded binary control/NUL in a marker-shaped byte slice'
                elif re.fullmatch(r'-?\d+|Arial|muvluv16_steam|[A-Z][A-Za-z0-9_]+',plain):
                    decision,reason='do_not_translate','identifier/font/engine value, not dialogue'
                else:
                    decision,reason='pending','counted field has no proven display owner; no writeback'
                candidates.append(dict(block=block,kind='unowned_counted',decision=decision,reason=reason,evidence=r))
                totals['counted_'+decision] += 1
            for r in current['unowned_pool_strings']:
                if not visible(r['text']):
                    continue
                candidates.append(dict(block=block,kind='unreferenced_pool_string',decision='pending',
                    reason='no exact message reference; may be auxiliary or preserved old pool data',evidence=r))
                totals['unreferenced_pool_strings'] += 1
            # Broad byte probes are separate from established serialized fields.
            # Retain even implausible noise; do not mislabel it as translated text.
            for r in current['unowned_marked_strings']:
                spans = [(s['identity_start'],s['identity_end']) for s in current['slots']]
                spans += [(s['marker_offset'],s['end_offset']) for s in current['unowned_counted']]
                overlap = next(((a,b) for a,b in spans if a<r['end'] and r['start']<b),None)
                unresolved_bytes.append(dict(block=block,decision='do_not_translate' if overlap else 'pending',
                    reason='byte slice overlaps an identified field; not an independent string' if overlap else 'unowned byte-pattern probe, not confirmed text',
                    overlap=overlap,evidence=r))
            (output/(block+'.json')).write_text(json.dumps(current,ensure_ascii=False,default=json_default),encoding='utf-8')
            if len(rows)%40==0:
                print(f'{len(rows)} finalized blocks',flush=True)
    report=dict(summary=dict(totals),message_declarations=[dict(name=k[0],schema=k[1],count=v) for k,v in sorted(classes.items())],
                blocks=rows,limits=['No complete Ocean object-cache replay or path reachability proof.',
                'Raw UTF-16 byte-pattern probes remain separate from proven fields; unresolved probes are not authorized translations.',
                'Unreferenced pool data may contain auxiliary strings or old data; not automatically selected.'])
    for name,data in [('summary.json',report),('candidate-ledger.json',candidates),('byte-probes.json',unresolved_bytes)]:
        (output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=json_default),encoding='utf-8')
    print(json.dumps(report['summary']),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    summarize(args.cache,args.output)
