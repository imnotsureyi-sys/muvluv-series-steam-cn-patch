"""Manual, pull-only PF/PM/TDA synchronization. Never upload or execute remote text."""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import unicodedata

from localization.tools.sync_icb_paratranz import canonical_ranks, fetch_snapshot, remote_index, sha, validate_translation
from rUGP.tools.text.chapter_review import decoded, read_chapters

PROFILES = {'pf': (20660, 'photonflowers'), 'pm': (20661, 'photonmelodies'), 'tda': (19505, None)}
SUPPLEMENTS = Path('localization/paratranz/tda/supplements.json')


def folder(slug):
    if slug not in PROFILES:
        raise ValueError('Unknown project')
    return Path('localization/paratranz') / slug


def packed(value):
    # One stable record per line: reviewable and smaller than one large pretty JSON.
    if isinstance(value, list):
        return ('[\n' + ',\n'.join(json.dumps(r, ensure_ascii=False, separators=(',', ':')) for r in value) + '\n]\n').encode('utf8')
    return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf8')


def csv_bytes(table):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, table['fields'], lineterminator='\n')
    writer.writeheader()
    writer.writerows(table['rows'])
    return (b'\xef\xbb\xbf' if table['raw'].startswith(b'\xef\xbb\xbf') else b'') + stream.getvalue().encode('utf8')


def load_tables(repo, slug):
    _, title = PROFILES[slug]
    tables, index = {}, {}
    if title:
        root = Path('rUGP/games') / title / 'translations'
        manifest = json.loads((repo/root/'chapters.json').read_text(encoding='utf8'))
        paths = []
        for entry in manifest['files']:
            relative = Path(entry['file'])
            if relative.is_absolute() or '..' in relative.parts or relative.suffix != '.csv':
                raise ValueError('Unsafe chapter path')
            paths.append(root/relative)
        if len(paths) != len(set(paths)):
            raise ValueError('Duplicate chapter path')
    else:
        paths = [Path(f'AGE2/games/tda0{i}/translations/ja-zh-Hans.csv') for i in range(4)]
    for path in paths:
        raw = (repo/path).read_bytes()
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
        rows = list(reader)
        column = 'translated_text' if title else 'cn_text'
        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError('Invalid CSV columns')
        tables[path] = dict(raw=raw, fields=reader.fieldnames, rows=rows, column=column)
        for row in rows:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('Malformed CSV')
            key = row['binding_id'] if title else f"{path.parts[2].upper()}|{row['egpack']}|{row['id']}"
            source = row['jp_utf8_sha256'] if title else row['source_text_sha256']
            if key in index or not re.fullmatch('[0-9a-fA-F]{64}', source):
                raise ValueError('Duplicate key or malformed source identity')
            index[key] = dict(path=path, row=row, column=column, source=source.lower())
    if slug == 'tda':
        raw = (repo/SUPPLEMENTS).read_bytes()
        rows = json.loads(raw)
        tables[SUPPLEMENTS] = dict(raw=raw, rows=rows, column='translation', fields=None)
        for row in rows:
            key = row['key']
            if key in index or not re.fullmatch('[0-9a-f]{64}', row['source_sha256']):
                raise ValueError('Invalid supplement identity')
            index[key] = dict(path=SUPPLEMENTS, row=row, column='translation', source=row['source_sha256'])
    return tables, index


def source_hash(slug, original):
    return sha(decoded(original) if slug in ('pf', 'pm') else original)


def bootstrap(repo, slug, snapshot, commit):
    """Only establish a baseline after independently reconciling both sides."""
    _, local = load_tables(repo, slug)
    remote, files = remote_index(snapshot, PROFILES[slug][0], allow_empty_original=slug=='tda')
    if set(local) != set(remote):
        raise ValueError('Bootstrap coverage mismatch')
    shards = {fid: [] for fid in files}
    for key, item in local.items():
        r = remote[key]
        current = item['row'][item['column']]
        if source_hash(slug, r['original']) != item['source']:
            raise ValueError('Bootstrap original mismatch')
        if not r['original'] and (item['row'].get('record_kind')!='structural_empty' or current):
            raise ValueError('Only verified structural records may have empty originals')
        if current != r['translation']:
            raise ValueError('Reconcile translations before establishing the first baseline')
        shards[r['file_id']].append(dict(key=key, id=r['id'], file_id=r['file_id'], source_sha256=item['source'],
            local_sha256=sha(current), remote_sha256=sha(r['translation']), stage=r['stage']))
    manifest = dict(schema='series-paratranz/v1', project_id=PROFILES[slug][0], slug=slug,
                    bootstrap_git_commit=commit, rows=len(local), files=[])
    outputs = {}
    for fid, name in files.items():
        relative = f'baseline/{fid}.json'
        manifest['files'].append(dict(id=fid, name=name, rows=len(shards[fid]), baseline=relative))
        outputs[folder(slug)/relative] = packed(shards[fid])
    outputs[folder(slug)/'manifest.json'] = packed(manifest)
    return outputs


def validate_candidate(slug, item, original, current, candidate):
    if slug == 'tda':
        validate_translation(original, current, candidate, 'main.csv')
        # Supplements include UI fields; preserve placeholders as well as controls.
        if item['path'] == SUPPLEMENTS:
            validate_translation(original, current, candidate, 'ui-strings.csv')
        return
    before, after = decoded(current), decoded(candidate)
    if not after.strip() or '\x00' in after or ('\x03' in after and item['row']['kind'] != 'cstring'):
        raise ValueError('Empty text or forbidden body control')
    if any(any(unicodedata.category(c) in ('Cc', 'Cf') for c in name) for name in re.findall('【([^】]*)】', after)):
        raise ValueError('Speaker contains hidden controls or line breaks')
    controls = lambda s: [c for c in s if unicodedata.category(c) in ('Cc', 'Cf')]
    if controls(before) != controls(after):
        raise ValueError('Control sequence changed; review layout separately')
    if item['row']['kind'] == 'cstring':
        pattern = r'\\[A-Za-z]|%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[a-zA-Z%]'
        if re.findall(pattern, before) != re.findall(pattern, after):
            raise ValueError('System placeholder changed')


def plan(repo, slug, snapshot):
    manifest = json.loads((repo/folder(slug)/'manifest.json').read_text(encoding='utf8'))
    if (manifest.get('schema'),manifest.get('project_id'),manifest.get('slug')) != ('series-paratranz/v1',PROFILES[slug][0],slug):
        raise ValueError('Invalid project baseline')
    tables, local = load_tables(repo, slug)
    remote, files = remote_index(snapshot, PROFILES[slug][0], allow_empty_original=slug=='tda')
    if files != {e['id']:e['name'] for e in manifest['files']} or len(files)!=len(manifest['files']):
        raise ValueError('File inventory changed; explicit mapping update required')
    baseline, shards = {}, {}
    for entry in manifest['files']:
        # Never trust a baseline to select an arbitrary path for writes.
        expected = f"baseline/{entry['id']}.json"
        if entry['baseline'] != expected:
            raise ValueError('Unsafe baseline path')
        path = folder(slug)/expected
        rows = json.loads((repo/path).read_text(encoding='utf8'))
        if len(rows) != entry['rows']:
            raise ValueError('Baseline row count changed')
        shards[path] = rows
        for row in rows:
            if row['key'] in baseline or row['file_id'] != entry['id']:
                raise ValueError('Duplicate or misplaced baseline key')
            baseline[row['key']] = row
    if set(local)!=set(remote) or set(local)!=set(baseline) or len(local)!=manifest['rows']:
        raise ValueError('Missing or unexpected rows')
    changed_paths, changes, held, errors = set(), [], [], []
    for key, item in local.items():
        r, b = remote[key], baseline[key]
        if (r['id'],r['file_id'],source_hash(slug,r['original'])) != (b['id'],b['file_id'],b['source_sha256']) or item['source']!=b['source_sha256']:
            raise ValueError('Source or stable ID changed')
        current = item['row'][item['column']]
        raw = r['translation']
        if not r['original'] and (item['row'].get('record_kind')!='structural_empty' or current or raw):
            raise ValueError('Structural empty record was changed')
        candidate = canonical_ranks(raw)
        remote_changed = sha(raw)!=b['remote_sha256'] or r['stage']!=b['stage']
        if remote_changed and r['stage'] in (-1,0,2):
            held.append(r['id'])
            continue
        if not remote_changed:
            # Keep the last reconciled local identity. A later remote edit must
            # still detect a local-only change observed by an earlier run.
            continue
        if remote_changed:
            if sha(current)!=b['local_sha256'] and current!=candidate:
                errors.append({'id':r['id'],'reason':'both_sides_changed'})
                continue
            if current!=candidate:
                try:
                    validate_candidate(slug,item,r['original'],current,candidate)
                except ValueError as exc:
                    errors.append({'id':r['id'],'reason':str(exc)})
                    continue
                item['row'][item['column']] = candidate
                changed_paths.add(item['path'])
                changes.append(r['id'])
        b.update(local_sha256=sha(item['row'][item['column']]),remote_sha256=sha(raw),stage=r['stage'])
    if errors:
        raise ValueError('No files written: '+json.dumps(errors))
    outputs = {path: csv_bytes(tables[path]) if tables[path]['fields'] else packed(tables[path]['rows']) for path in changed_paths}
    if slug == 'tda':
        ledger_path = Path('AGE2/evidence/translations/review-ledger/manifest.json')
        ledger = json.loads((repo/ledger_path).read_text(encoding='utf8'))
        for i in range(4):
            game = f'tda0{i}'
            path = Path(f'AGE2/games/{game}/translations/ja-zh-Hans.csv')
            if path not in outputs:
                continue
            sidepath = Path(f'AGE2/evidence/translations/snapshots/{game}.json')
            side = json.loads((repo/sidepath).read_text(encoding='utf8'))
            digest = hashlib.sha256(outputs[path]).hexdigest().upper()
            side.update(output_bytes=len(outputs[path]),output_sha256=digest)
            outputs[sidepath] = packed(side)
            # The pending review rows and statuses are unchanged; only their current input identity moves.
            ledger['translation_inputs'][game.upper()].update(bytes=len(outputs[path]), sha256=digest)
        ledger_data = packed(ledger)
        if ledger_data != (repo/ledger_path).read_bytes():
            outputs[ledger_path] = ledger_data
    else:
        root = Path('rUGP/games')/PROFILES[slug][1]/'translations'
        overrides = {path.relative_to(root).as_posix(): outputs.get(path, table['raw']) for path,table in tables.items()}
        read_chapters(repo/root, overrides=overrides)
    for path,rows in shards.items():
        data = packed(rows)
        if data != (repo/path).read_bytes():
            outputs[path] = data
    report = dict(project=slug, files=len(files), verified_rows=len(local), changed_translations=len(changes),
                  held_rows=len(held), output_files=len(outputs), online_writes=0)
    return outputs, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',choices=PROFILES,required=True)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--paths',type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding='utf8')) if args.snapshot else fetch_snapshot(os.environ.get('PARATRANZ_TOKEN'),PROFILES[args.project][0])
    outputs, summary = plan(args.repo,args.project,snapshot)
    if args.apply:
        for path,data in outputs.items():
            (args.repo/path).write_bytes(data)
    if args.paths:
        # NUL-separated literal paths for git add; remote names never become shell arguments.
        args.paths.write_bytes(b''.join(path.as_posix().encode()+b'\0' for path in sorted(outputs)))
    if args.report:
        note = 'TDA 姓名/UI 仅为校对资料，尚未接入资源构建。' if args.project == 'tda' else ''
        args.report.write_text(f"# ParaTranz {args.project.upper()} 校对同步\n\n核对 {summary['files']} 文件、{summary['verified_rows']} 条。\n\n译文变化 {summary['changed_translations']} 条；暂缓 {summary['held_rows']} 条。\n\n仅修改本项目中文目标字段、配套清单和同步基线。不写回 ParaTranz，不自动审核、合并或发版。{note}\n",encoding='utf8')
    print(json.dumps(summary))


if __name__ == '__main__':
    try:
        main()
    except (ValueError,KeyError,TypeError,OSError) as exc:
        print(f'Sync stopped: {exc}',file=sys.stderr)
        sys.exit(1)
