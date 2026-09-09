"""Replay private CRip008 bindings through real C prepare/commit code.

No game is started or modified. The executable's initial runtime gate and caller
arguments are supplied by the fixture, not captured from a running game. Padding
variants are exploration, not evidence that retail callers use those extents.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path
import re
import subprocess

from rUGP.tools.images.verify_pm_production import fnv1a64

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / 'rUGP/runtime'
REF = re.compile(r'(pf|pm):rio(\d{3}):0x([0-9a-fA-F]+)\Z')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def runtime_identity() -> dict[str, str]:
    return {p.relative_to(RUNTIME).as_posix(): sha(p.read_bytes())
            for folder in ('src', 'include', 'generated')
            for p in sorted((RUNTIME / folder).iterdir()) if p.is_file()}


def validate_replay(replay: dict, returncode: int) -> None:
    """Reject incomplete results before calculating any all-cases-pass status."""
    expected = set(product((0, 1), (-1, 1), (0, 16), range(6)))
    cases = replay['cases']
    actual = [(c['direct'], c['stride_sign'], c['row_slack'], c['variant']) for c in cases]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('Incomplete or duplicate replay case matrix')
    for case in cases:
        for field in ('prepared', 'before_clean', 'pixels_ok', 'guards_ok', 'passed'):
            if type(case[field]) is not bool:
                raise ValueError(f'Non-boolean replay result: {field}')
    failures = sum(not c['passed'] for c in cases)
    if replay['required_failures'] != failures or returncode != int(bool(failures)):
        raise ValueError('Replay failure count/exit status mismatch')
    for field in ('runtime_initialization_exercised', 'assembly_wrapper_executed',
                  'proprietary_decoder_executed'):
        if replay[field] is not False:
            raise ValueError(f'Unsupported replay coverage claim: {field}')


def compile_fixture(zig: Path, game: str, output: Path) -> Path:
    selector = f'PHOTON_V6_{game}_SELECTOR'
    names = [f'photon_v6_{game.lower()}_native_runtime.S',
             f'photon_v6_{game.lower()}_selector_adapter.c',
             'photon_v6_cpu_surface_rgba.c', 'photon_v6_exact_rgba_sidecar_loader.c',
             'photon_pf_decoder_surface_view.c', 'photon_v6_surface_transaction.c',
             'photon_v6_internal_route_gate.c', 'photon_v6_exact_overlay_core.c',
             'photon_v6_special57_sidecar_loader.c']
    exe = output / f'replay-{game.lower()}.exe'
    command = [str(zig), 'cc', '-target', 'x86-windows-gnu', '-std=c11', '-O2',
               '-Wall', '-Wextra', '-Werror', '-municode', f'-DPHOTON_BUILD_{game}=1',
               '-DPHOTON_V6_NATIVE_TEST_HOOKS=1', f'-DPHOTON_V6_PRODUCTION_{game}=1',
               f'-D{selector}_ADAPTER=1', f'-D{selector}_TEST_HOOKS=1',
               '-I', str(RUNTIME / 'generated'), '-I', str(RUNTIME / 'include'),
               str(ROOT / 'rUGP/tests/runtime/crip008_route_replay.c'),
               *[str(RUNTIME / 'src' / name) for name in names],
               '-o', str(exe), '-ladvapi32', '-luser32', '-lgdi32', '-lwindowscodecs', '-lole32']
    compiled = subprocess.run(command, capture_output=True, text=True, timeout=180)
    (output / f'compile-{game.lower()}.log').write_text(compiled.stdout + compiled.stderr, 'utf-8')
    if compiled.returncode:
        raise RuntimeError(compiled.stderr[-3000:])
    return exe


def run(manifest: Path, roots: dict[str, Path], zig: Path, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    manifest_bytes = manifest.read_bytes()
    manifest_data = json.loads(manifest_bytes)
    rows = [r for r in manifest_data['rows'] if r.get('runtime_identity', {}).get('codec') == 'CRip008']
    if not rows:
        raise ValueError('No detailed CRip008 bindings found')
    sources_before = runtime_identity()
    installed_before = {game: sha((roots[game] / 'Ages3ResT.dll').read_bytes()) for game in roots}
    compiler = {'sha256': sha(zig.read_bytes()),
                'version': subprocess.check_output([str(zig), 'version'], text=True).strip()}
    basenames = {'PF': 'photonflowers11.rio', 'PM': 'photonmelodies11.rio'}
    for game in {r['game'] for r in rows}:
        if not (roots[game] / basenames[game]).is_file():
            raise ValueError(f'Missing {game} archive: {basenames[game]}')
    executables = {game: compile_fixture(zig, game, output) for game in sorted({r['game'] for r in rows})}
    results = []
    for index, row in enumerate(rows):
        ident = row['runtime_identity']
        game = row['game']
        target = next((REF.fullmatch(a) for a in row['aliases']
                       if REF.fullmatch(a) and a.startswith(game.lower() + ':')), None)
        if target is None:
            raise ValueError(f'No archive reference for row {index}')
        volume = int(target[2])
        basename = basenames[game]
        archive = roots[game] / (basename + (f'.{volume:03d}' if volume else ''))
        with archive.open('rb') as stream:
            stream.seek(int(target[3], 16))
            record = stream.read(ident['payload_offset'] + ident['payload_bytes'])
        if sha(record) != row['record_sha256']:
            raise ValueError(f'Archive record mismatch: {target[0]}')
        payload = record[ident['payload_offset']:]
        if sha(payload) != ident['payload_sha256'] or f'{fnv1a64(payload):016X}' != ident['payload_fnv1a64']:
            raise ValueError(f'Archive payload mismatch: {target[0]}')
        bundle = roots[game] / 'PhotonR2Assets/v6'
        sidecar = bundle / f'sidecars/{game}/{len(payload):010d}_{fnv1a64(payload):016X}.png'
        if sha(sidecar.read_bytes()) != row['sidecar']['png_sha256']:
            raise ValueError(f'Installed sidecar mismatch: {target[0]}')
        private_payload = output / f'{index:03d}.payload'
        private_payload.write_bytes(payload)
        command = [str(executables[game]), str(bundle), str(private_payload), str(len(payload)),
                   *[str(ident[key]) for key in ('width', 'height', 'x_offset', 'y_offset', 'draw_width', 'draw_height')]]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=90)
        if completed.returncode not in (0, 1):
            raise RuntimeError(f'Fixture failed for {target[0]}: {completed.returncode} {completed.stderr}')
        replay = json.loads(completed.stdout)
        validate_replay(replay, completed.returncode)
        result = {'game': game, 'group_id': row.get('selected_group_id'),
                  'refs': row['aliases'], 'identity': ident,
                  'installed_png_sha256': row['sidecar']['png_sha256'],
                  'record_sha256': row['record_sha256'],
                  'exact_extent_passed': all(c['passed'] and c['prepared'] for c in replay['cases'] if c['variant'] == 0),
                  'padding_2_supported': all(c['prepared'] and c['passed'] for c in replay['cases'] if c['variant'] == 1),
                  'padding_3_supported': all(c['prepared'] and c['passed'] for c in replay['cases'] if c['variant'] == 2),
                  **replay}
        results.append(result)
        print(f'{index+1}/{len(rows)} {game} G{result["group_id"]}: exact={result["exact_extent_passed"]}, padding={result["padding_2_supported"]}/{result["padding_3_supported"]}', flush=True)
        (output / 'progress.json').write_text(json.dumps(results, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    if runtime_identity() != sources_before:
        raise RuntimeError('Runtime source changed during replay')
    if {game: sha((roots[game] / 'Ages3ResT.dll').read_bytes()) for game in roots} != installed_before:
        raise RuntimeError('Installed DLL changed during replay')
    report = {'schema': 'photon-crip008-route-replay-v1', 'source_manifest_sha256': sha(manifest_bytes),
              'runtime_sources': sources_before, 'installed_dll_sha256': installed_before, 'compiler': compiler,
              'selected_bindings': len(results), 'case_count': sum(len(r['cases']) for r in results),
              'exact_extent_passed': sum(r['exact_extent_passed'] for r in results),
              'required_failures': sum(r['required_failures'] for r in results),
              'padding_boundary_gaps': sum(not (r['padding_2_supported'] and r['padding_3_supported']) for r in results),
              'caller_extents_captured_by_this_run': False, 'runtime_initialization_exercised': False,
              'assembly_wrapper_executed': False, 'proprietary_decoder_executed': False,
              'game_started': False, 'game_files_modified': False, 'rows': results}
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('manifest', 'pf-root', 'pm-root', 'zig', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    report = run(args.manifest, {'PF': args.pf_root, 'PM': args.pm_root}, args.zig, args.output)
    print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'runtime_sources')}, indent=2))
    return int(bool(report['required_failures']))


if __name__ == '__main__':
    raise SystemExit(main())
