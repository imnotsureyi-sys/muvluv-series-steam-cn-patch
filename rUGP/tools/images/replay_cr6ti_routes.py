"""Replay detailed Cr6Ti bindings from private archives without starting a game."""
from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path
import re
import subprocess

from rUGP.tools.images.replay_crip008_routes import compile_fixture, runtime_identity, sha
from rUGP.tools.images.verify_pm_production import fnv1a64
from rUGP.formats.images.cr6ti_decode import parse_standard_cr6ti_record

REF = re.compile(r'(pf|pm):rio(\d{3}):0x([0-9a-fA-F]+)(:cbg2d/cr6ti)?\Z')


def read_payload(row: dict, root: Path) -> tuple[bytes, dict]:
    ident, game = row['runtime_identity'], row['game']
    match = next((REF.fullmatch(a) for a in row['aliases'] if REF.fullmatch(a)), None)
    if match is None or match[1].upper() != game:
        raise ValueError('Missing exact archive reference')
    volume = int(match[2])
    base = 'photonflowers11.rio' if game == 'PF' else 'photonmelodies11.rio'
    archive = root / (base + (f'.{volume:03d}' if volume else ''))
    n = ident['payload_bytes']
    inline = ident['codec'] == 'CBg2d/Cr6Ti'
    offset = 40 if inline else ident['payload_offset']
    with archive.open('rb') as stream:
        stream.seek(int(match[3], 16))
        record = stream.read(offset+n+(0 if inline else 2))
    if len(record) != offset+n+(0 if inline else 2):
        raise ValueError('Truncated archive record')
    if inline:
        # This named private profile is not a general CBg2d parser. SHA-256
        # authenticates the exact payload after the observed inline header.
        if (int.from_bytes(record[28:32], 'little') != n or
            int.from_bytes(record[3:5], 'little') != row['geometry']['width'] or
            int.from_bytes(record[5:7], 'little') != row['geometry']['height']):
            raise ValueError('Inline header profile/geometry mismatch')
    elif row.get('record_sha256') and sha(record) != row['record_sha256']:
        raise ValueError('Archive record SHA-256 mismatch')
    elif not row.get('record_sha256'):
        header = parse_standard_cr6ti_record(record)
        if (header.width, header.height, header.payload_length) != (
                row['geometry']['width'], row['geometry']['height'], n):
            raise ValueError('Unhashed record header geometry/extent mismatch')
    payload = record[offset:offset+n]
    if sha(payload) != ident['payload_sha256'] or f'{fnv1a64(payload):016X}' != ident['payload_fnv1a64']:
        raise ValueError('Archive payload identity mismatch')
    return payload, {'record_sha256': sha(record), 'payload_offset': offset,
                     'record_sha_predeclared': bool(row.get('record_sha256'))}


def validate_cases(replay: dict, exit_code: int) -> None:
    expected = set(product((0, 1), (0, 1), (0, 1), (-1, 1), (0, 16)))
    cases = replay['cases']
    keys = [tuple(c[k] for k in ('active', 'alt', 'compose', 'sign', 'slack')) for c in cases]
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError('Incomplete or duplicate Cr6Ti matrix')
    for case in cases:
        fields = ('prepared', 'pixels_ok', 'guards_ok', 'before_clean', 'passed')
        if any(type(case[k]) is not bool for k in fields):
            raise ValueError('Non-boolean Cr6Ti result')
        if case['passed'] and not all(case[k] for k in fields):
            raise ValueError('Contradictory Cr6Ti success')
    failures = sum(not c['passed'] for c in cases)
    if failures != replay['required_failures'] or exit_code != int(bool(failures)):
        raise ValueError('Cr6Ti failure count/exit status mismatch')


def run(manifest: Path, roots: dict[str, Path], zig: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    manifest_bytes = manifest.read_bytes()
    rows = [r for r in json.loads(manifest_bytes)['rows']
            if r.get('runtime_identity', {}).get('codec') in ('Cr6Ti', 'CBg2d/Cr6Ti')]
    if not rows:
        raise ValueError('No detailed Cr6Ti bindings')
    sources = runtime_identity()
    dlls = {g: sha((p/'Ages3ResT.dll').read_bytes()) for g, p in roots.items()}
    exes = {g: compile_fixture(zig, g, output, 'cr6ti_route_replay.c') for g in roots}
    results = []
    for index, row in enumerate(rows):
        game = row['game']
        payload, record = read_payload(row, roots[game])
        ident = row['runtime_identity']
        bundle = roots[game]/'PhotonR2Assets/v6'
        sidecar = bundle / f'sidecars/{game}/{len(payload):010d}_{fnv1a64(payload):016X}.png'
        if sha(sidecar.read_bytes()) != row['sidecar']['png_sha256']:
            raise ValueError('Installed PNG identity mismatch')
        private = output/f'{index:03d}.payload'
        private.write_bytes(payload)
        size = row['geometry']
        completed = subprocess.run([str(exes[game]), str(bundle), str(private), str(len(payload)),
                                    str(size['width']), str(size['height'])],
                                   capture_output=True, text=True, timeout=180)
        if completed.returncode not in (0, 1):
            raise RuntimeError(f'Cr6Ti fixture G{row["selected_group_id"]}: {completed.returncode}: {completed.stderr}')
        replay = json.loads(completed.stdout)
        validate_cases(replay, completed.returncode)
        result = dict(game=game, group_id=row['selected_group_id'], refs=row['aliases'],
                      identity=ident, geometry=size, archive=record,
                      installed_png_sha256=row['sidecar']['png_sha256'], **replay)
        results.append(result)
        (output/'progress.json').write_text(json.dumps(results, indent=2)+'\n', 'utf-8')
        print(f'{index+1}/{len(rows)} {game} G{row["selected_group_id"]}: failures={replay["required_failures"]}', flush=True)
    if runtime_identity() != sources or dlls != {g: sha((p/'Ages3ResT.dll').read_bytes()) for g,p in roots.items()}:
        raise ValueError('Source or installed DLL changed during replay')
    report = dict(schema='photon-cr6ti-route-replay-v1', source_manifest_sha256=sha(manifest_bytes),
                  runtime_sources=sources, installed_dll_sha256=dlls, selected_bindings=len(results),
                  case_count=sum(len(r['cases']) for r in results),
                  required_failures=sum(r['required_failures'] for r in results),
                  compiler_sha256=sha(zig.read_bytes()),
                  fixture_sha256=sha((Path(__file__).resolve().parents[2]/'tests/runtime/cr6ti_route_replay.c').read_bytes()),
                  game_started=False, game_files_modified=False, runtime_initialization_exercised=False,
                  assembly_wrapper_executed=False, proprietary_decoder_executed=False,
                  owner_object_synthetic=True, decoder_writes_simulated=True, rows=results)
    (output/'verification.json').write_text(json.dumps(report, indent=2)+'\n','utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('manifest', 'pf-root', 'pm-root', 'zig', 'output'):
        parser.add_argument('--'+field, required=True, type=Path)
    args = parser.parse_args()
    report = run(args.manifest, {'PF':args.pf_root,'PM':args.pm_root}, args.zig,args.output)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','runtime_sources')},indent=2))
    return int(bool(report['required_failures']))


if __name__ == '__main__':
    raise SystemExit(main())
