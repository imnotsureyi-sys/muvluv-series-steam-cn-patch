"""Reconcile one explicitly identified diagnostic capture with exact bindings.

No capture is taken, game launched, or installation changed. A historical DLL's
events remain historical; this does not declare the current DLL runtime-tested.
"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from rUGP.tools.images.replay_crip008_routes import sha

COMMIT_EVENTS = {'decode_ordinary_composited_commit', 'crip008_ordinary_commit'}
FAIL_WORDS = ('failed', 'fatal', 'rejected', 'denied', 'not_targeted', 'conflict')


def zero_extended_hash(value: str, count: int) -> str:
    number = int(value, 16)
    for _ in range(count):
        number = number * 1099511628211 & ((1 << 64)-1)
    return f'{number:016X}'


def reconcile(manifest: dict, events: list[dict], game: str) -> dict:
    withheld = {tuple(k) for k in manifest.get('withheld_keys', [])}
    rows = [r for r in manifest['rows'] if r['game'] == game and
            (game, r['runtime_identity']['payload_bytes'],
             r['runtime_identity']['payload_fnv1a64']) not in withheld]
    exact, padded = defaultdict(set), defaultdict(set)
    for i, row in enumerate(rows):
        ident = row['runtime_identity']
        n, h = ident['payload_bytes'], ident['payload_fnv1a64'].upper()
        exact[n, h].add(i)
        if ident.get('codec') == 'CRip008':
            for delta in (2, 3):
                padded[n+delta, zero_extended_hash(h, delta)].add(i)
    found = [dict(events=Counter(), observed_extents=set(), commits=0,
                  failures=0, zero_padding_matches=0) for _ in rows]
    seen, duplicates, unmatched, ambiguous, capped = {}, 0, 0, 0, False
    for event in events:
        token = (event['pid'], event['ordinal'])
        if token in seen:
            if event != seen[token]:
                raise ValueError('Conflicting PID/ordinal: captures must be separated by session')
            duplicates += 1
            continue
        seen[token] = event
        if event['ordinal'] >= 8192:
            capped = True
        key = (event['payload_bytes'], event['payload_fnv1a64'].upper())
        candidates = exact.get(key, set())
        extension = False
        if not candidates:
            candidates = padded.get(key, set())
            extension = bool(candidates)
        if not candidates:
            unmatched += 1
            continue
        if len(candidates) != 1:
            ambiguous += 1
            continue
        record = found[next(iter(candidates))]
        name = event['event']
        record['events'][name] += 1
        record['observed_extents'].add(event['payload_bytes'])
        record['zero_padding_matches'] += int(extension)
        if name in COMMIT_EVENTS:
            # A commit label alone is insufficient: require the actual write
            # flag, successful status and nonzero equal requested/readback.
            requested = event.get('requested_rgba_fnv1a64', '').upper()
            good = (event.get('overlay_status') == 0 and
                    event.get('transaction_status') == 0 and
                    event.get('destination_committed') == 1 and
                    bool(re.fullmatch('[0-9A-F]{16}', requested)) and
                    requested != '0000000000000000' and
                    requested == event.get('readback_rgba_fnv1a64', '').upper())
            record['commits'] += int(good)
            record['failures'] += int(not good)
        elif any(word in name for word in FAIL_WORDS):
            record['failures'] += 1
    results = []
    for row, record in zip(rows, found):
        status = ('observed_failure' if record['failures'] else
                  'commit_readback_observed' if record['commits'] else
                  'seen_without_commit' if record['events'] else 'not_observed')
        results.append(dict(group_id=row.get('selected_group_id'), refs=row['aliases'],
                            payload_bytes=row['runtime_identity']['payload_bytes'],
                            payload_fnv1a64=row['runtime_identity']['payload_fnv1a64'],
                            status=status, **{**record, 'events':dict(record['events']),
                                             'observed_extents':sorted(record['observed_extents'])}))
    return dict(expected_bindings=len(rows), statuses=dict(Counter(r['status'] for r in results)),
                unique_events=len(seen), duplicate_events_ignored=duplicates,
                unmatched_events=unmatched, ambiguous_events=ambiguous,
                capture_cap_reached=capped, successful_prepare_inferred_only_from_commit=True,
                capture_exhaustive=False, current_build_runtime_verified=False, rows=results)


def run(manifest: Path, trace: Path, game: str, build_sha: str, output: Path) -> dict:
    if not re.fullmatch('[0-9A-Fa-f]{64}', build_sha):
        raise ValueError('Capture DLL SHA-256 is required')
    output.mkdir(parents=True, exist_ok=False)
    manifest_bytes, trace_bytes = manifest.read_bytes(), trace.read_bytes()
    events = []
    for number, line in enumerate(trace_bytes.decode('utf-8-sig').splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            for field in ('pid','ordinal','payload_bytes'):
                if type(event[field]) is not int or event[field] < 0:
                    raise ValueError('Bad integer')
            if not re.fullmatch('[0-9a-fA-F]{16}', event['payload_fnv1a64']):
                raise ValueError('Bad identity hash')
            if not isinstance(event['event'], str):
                raise ValueError('Bad event name')
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f'Malformed diagnostic event at line {number}') from exc
        events.append(event)
    report = dict(schema='photon-native-trace-reconciliation-v1', game=game,
                  capture_dll_sha256=build_sha.upper(), trace_sha256=sha(trace_bytes),
                  source_manifest_sha256=sha(manifest_bytes),
                  game_started=False, game_files_modified=False,
                  **reconcile(json.loads(manifest_bytes),events,game))
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n','utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for field in ('manifest','trace','output'):
        parser.add_argument('--'+field,required=True,type=Path)
    parser.add_argument('--game',choices=['PF','PM'],required=True)
    parser.add_argument('--capture-build-sha256',required=True)
    args=parser.parse_args()
    report=run(args.manifest,args.trace,args.game,args.capture_build_sha256,args.output)
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))


if __name__ == '__main__':
    main()
