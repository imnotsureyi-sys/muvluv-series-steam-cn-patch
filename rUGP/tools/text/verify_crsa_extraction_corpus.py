"""Compare corrected extraction against every cached pre-fix CRsa slot."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import json
from pathlib import Path

from rUGP.formats.rio.crsa_text import extract_text_slots
from rUGP.tools.text.audit_crsa_display_gaps import sha


def verify(path: Path) -> dict:
    previous = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
    payload = path.read_bytes()
    result = extract_text_slots(payload)
    old = {s['payload_offset']: s for s in previous['slots']}
    new = {s.payload_offset: json.loads(json.dumps(asdict(s))) for s in result.slots}
    removed = sorted(old.keys() - new.keys())
    changed = [k for k in old.keys() & new.keys() if old[k] != new[k]]
    added = [new[k] for k in sorted(new.keys() - old.keys())]
    return dict(block=path.stem, payload_sha256=sha(payload), old_slots=len(old),
                new_slots=len(new), removed=removed, changed=changed, added=added,
                warnings=list(result.warnings))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with ProcessPoolExecutor(max_workers=3) as pool:
        for row in pool.map(verify, sorted(args.cache.glob('*.plain'))):
            rows.append(row)
            if len(rows) % 40 == 0:
                print(f'{len(rows)} verified blocks', flush=True)
    report = dict(blocks=rows, summary=dict(
        blocks=len(rows), old_slots=sum(r['old_slots'] for r in rows),
        new_slots=sum(r['new_slots'] for r in rows),
        added=sum(len(r['added']) for r in rows),
        removed=sum(len(r['removed']) for r in rows),
        changed=sum(len(r['changed']) for r in rows),
        warnings=sum(len(r['warnings']) for r in rows)))
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['summary']), flush=True)
    if report['summary']['removed'] or report['summary']['changed'] or report['summary']['warnings']:
        raise SystemExit(1)
