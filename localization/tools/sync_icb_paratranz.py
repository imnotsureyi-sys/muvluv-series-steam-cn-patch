"""ICB-only, read-only ParaTranz pull with stable identities and a two-sided baseline.

Raw exports remain in memory (or an explicitly supplied private test fixture).
Only Chinese destination cells, export checksums and the sync baseline may be updated.
This module never uploads, changes review stages, merges PRs or builds releases.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from AGE2.tools.egpack.egpack_codec import extract_control_codes, has_manual_newline

PROJECT = 20659
FOLDER = Path('AGE2/games/imperial-capital-burns/translations')
BASELINE = Path('localization/paratranz/imperial-capital-burns/baseline.json')
SIDECAR = Path('AGE2/evidence/translations/snapshots/imperial-capital-burns.json')
TABLES = {
    'main.ja-zh-Hans.csv': ('cn_text', ','),
    'speakers.ja-zh-Hans.csv': ('replacement_text', ','),
    'choices.ja-zh-Hans.csv': ('replacement_text', ','),
    'ui-strings.ja-zh-Hans.tsv': ('zh_cn', '\t'),
}
RANKS = {'少佐': '少校', '中佐': '中校', '大佐': '上校', '大尉': '上尉',
         '曹長': '上士', '曹长': '上士', '軍曹': '中士', '军曹': '中士', '伍長': '下士', '伍长': '下士'}


def sha(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()


def canonical_ranks(text):
    for old, new in RANKS.items():
        text = text.replace(old, new)
    return text


def table_key(name, row):
    if name.startswith('main.'):
        return f"ICB|{row['egpack']}|{row['id']}"
    if name.startswith('ui-strings.'):
        return f"ICB|ui|{row['id']}"
    kind = name.split('.')[0]
    return f"ICB|{kind}|{row['relative_path']}|{row['id']}"


def load_tables(repo):
    tables, index = {}, {}
    for name, (column, delimiter) in TABLES.items():
        raw = (repo / FOLDER / name).read_bytes()
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), delimiter=delimiter)
        rows = list(reader)
        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError('Unexpected authority columns')
        tables[name] = {'raw': raw, 'fields': reader.fieldnames, 'rows': rows,
                        'column': column, 'delimiter': delimiter}
        for row in rows:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Malformed authority row')
            key = table_key(name, row)
            if key in index:
                raise ValueError('Duplicate authority key')
            source_hash = (row['source_text_sha256'].lower() if name.startswith('main.')
                           else sha(row['jp'] if name.startswith('ui-strings.') else row['expected_text']))
            index[key] = {'name': name, 'row': row, 'column': column, 'source_sha256': source_hash}
    return tables, index


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('ParaTranz redirect refused; token was not forwarded')


def fetch_snapshot(token, project=PROJECT):
    if not token or not token.strip():
        raise ValueError('PARATRANZ_ICB_TOKEN is not configured')
    opener = urllib.request.build_opener(NoRedirect)

    def get(path):
        for attempt in range(3):
            request = urllib.request.Request(f'https://paratranz.cn/api/projects/{project}{path}',
                headers={'Authorization': f'Bearer {token.strip()}', 'Accept': 'application/json'})
            try:
                with opener.open(request, timeout=40) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code in (429, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** (attempt + 1))
                    continue
                raise ValueError(f'ParaTranz HTTP {exc.code}; response body suppressed') from None
        raise ValueError('ParaTranz retry limit reached')

    files = get('/files')
    if not isinstance(files, list):
        raise ValueError('Unexpected file-list response')
    result = [{'file': f, 'rows': get(f"/files/{int(f['id'])}/translation")} for f in files]
    # Catch an edit/upload during a multi-file download, rather than mixing versions.
    if files != get('/files'):
        raise ValueError('Project changed during download; retry from a fresh snapshot')
    return result


def remote_index(snapshot, project=PROJECT, allow_empty_original=False):
    result, files, ids = {}, {}, set()
    for entry in snapshot:
        file = entry['file']
        if file['project'] != project or file['id'] in files:
            raise ValueError('Wrong project or duplicate file')
        files[file['id']] = file['name']
        if not isinstance(entry['rows'], list) or file['total'] != len(entry['rows']):
            raise ValueError('Incomplete file export')
        for row in entry['rows']:
            if row['key'] in result or row['id'] in ids:
                raise ValueError('Duplicate remote key/ID')
            if not isinstance(row['original'], str) or (not row['original'] and not allow_empty_original):
                raise ValueError('Missing original')
            if not isinstance(row['translation'], str) or type(row['stage']) is not int:
                raise ValueError('Invalid translation or stage')
            if row['stage'] not in (-1, 0, 1, 2, 3, 5, 9):
                raise ValueError('Unknown review stage')
            if row.get('fileId', file['id']) != file['id']:
                raise ValueError('Mismatched file identity')
            result[row['key']] = dict(row, file_id=file['id'])
            ids.add(row['id'])
    return result, files


def bootstrap(repo, snapshot, commit):
    """Explicit first-pull baseline: Git text is the initial comparison anchor."""
    _, local = load_tables(repo)
    remote, files = remote_index(snapshot)
    if set(local) != set(remote):
        raise ValueError('Authority/remote coverage differs')
    rows = []
    for key, item in local.items():
        online = remote[key]
        if sha(online['original']) != item['source_sha256']:
            raise ValueError('Original does not match source hash')
        text_hash = sha(item['row'][item['column']])
        rows.append({'key': key, 'id': online['id'], 'file_id': online['file_id'],
            'source_sha256': item['source_sha256'], 'local_sha256': text_hash,
            'remote_sha256': text_hash, 'stage': online['stage']})
    return {'schema': 'icb-paratranz-baseline/v1', 'project_id': PROJECT,
        'bootstrap_git_commit': commit, 'bootstrap_policy': 'First pull compares online text against this Git snapshot; no online writes.',
        'files': [{'id': k, 'name': v} for k, v in files.items()], 'rows': rows}


def validate_translation(original, current, candidate, name):
    if not candidate.strip() or '\x00' in candidate or '\u2060' in candidate or '<03>' in candidate:
        raise ValueError('Empty translation or forbidden control character')
    # Existing AGE2 layout policy, not the rUGP <0A> policy.
    if has_manual_newline(candidate):
        raise ValueError('AGE2 manual newline is forbidden')
    # Existing Chinese intentionally does not copy every Japanese pacing \w.
    # Preserve the current shipping Chinese control sequence; synchronization
    # must not silently become a control-code/layout migration.
    required = extract_control_codes(current)
    if extract_control_codes(candidate) != required:
        raise ValueError('Control codes differ from current Chinese authority')
    if name.startswith('ui-strings.'):
        pattern = r'%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[a-zA-Z%]|\{\d+\}'
        if re.findall(pattern, original) != re.findall(pattern, candidate):
            raise ValueError('UI placeholders differ from original')


def plan(repo, snapshot, baseline):
    tables, local = load_tables(repo)
    remote, files = remote_index(snapshot)
    if baseline.get('schema') != 'icb-paratranz-baseline/v1' or baseline.get('project_id') != PROJECT:
        raise ValueError('Invalid baseline')
    bases = {r['key']: r for r in baseline['rows']}
    if len(bases) != len(baseline['rows']) or set(local) != set(remote) or set(local) != set(bases):
        raise ValueError('Missing, duplicate or unexpected keys; no writes made')
    if files != {f['id']: f['name'] for f in baseline['files']}:
        raise ValueError('File inventory changed; manual baseline update required')
    next_baseline = copy.deepcopy(baseline)
    next_bases = {r['key']: r for r in next_baseline['rows']}
    changed, held, normalized, errors = [], [], 0, []
    for key, item in local.items():
        r, b = remote[key], bases[key]
        if (r['id'], r['file_id'], sha(r['original'])) != (b['id'], b['file_id'], b['source_sha256']) or item['source_sha256'] != b['source_sha256']:
            raise ValueError('Source/ID changed; no writes made')
        current = item['row'][item['column']]
        raw = r['translation']
        candidate = canonical_ranks(raw)
        remote_changed = sha(raw) != b['remote_sha256'] or r['stage'] != b['stage']
        if remote_changed and r['stage'] in (0, 2, -1):
            held.append({'id': r['id'], 'stage': r['stage']})
        elif remote_changed:
            if sha(current) != b['local_sha256'] and current != candidate:
                errors.append({'id': r['id'], 'reason': 'both_sides_changed'})
                continue
            if current != candidate:
                try:
                    validate_translation(r['original'], current, candidate, item['name'])
                except ValueError as exc:
                    errors.append({'id': r['id'], 'reason': str(exc)})
                    continue
                item['row'][item['column']] = candidate
                changed.append({'id': r['id'], 'table': item['name']})
                normalized += raw != candidate
        next_bases[key].update(local_sha256=sha(item['row'][item['column']]),
                              remote_sha256=sha(raw), stage=r['stage'])
    # This runs before writing any table. Conflicts cannot produce partial imports.
    if errors:
        raise ValueError('Sync refused: ' + json.dumps(errors, ensure_ascii=True))
    outputs = {}
    for name, table in tables.items():
        if not any(r['table'] == name for r in changed):
            continue
        stream = io.StringIO(newline='')
        writer = csv.DictWriter(stream, table['fields'], delimiter=table['delimiter'], lineterminator='\n')
        writer.writeheader()
        writer.writerows(table['rows'])
        data = stream.getvalue().encode('utf8')
        if table['raw'].startswith(b'\xef\xbb\xbf'):
            data = b'\xef\xbb\xbf' + data
        outputs[FOLDER / name] = data
    # Public export metadata describes the resulting CSV, not the old export.
    # Preserve source provenance and every other field; only output identity changes.
    main_path = FOLDER / 'main.ja-zh-Hans.csv'
    payload = outputs.get(main_path, tables['main.ja-zh-Hans.csv']['raw'])
    sidecar = json.loads((repo / SIDECAR).read_text(encoding='utf8'))
    if not isinstance(sidecar, dict) or not {'output_bytes', 'output_sha256'} <= sidecar.keys():
        raise ValueError('Missing public export checksum metadata')
    sidecar.update(output_bytes=len(payload), output_sha256=hashlib.sha256(payload).hexdigest().upper())
    sidecar_data = (json.dumps(sidecar, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if sidecar_data != (repo / SIDECAR).read_bytes():
        outputs[SIDECAR] = sidecar_data
    baseline_data = (json.dumps(next_baseline, ensure_ascii=False, indent=2) + '\n').encode('utf8')
    if baseline_data != (repo / BASELINE).read_bytes():
        outputs[BASELINE] = baseline_data
    summary = {'project_id': PROJECT, 'files': len(files), 'verified_rows': len(local),
               'changed_translations': len(changed), 'held_rows': len(held),
               'hard_rank_normalizations': normalized, 'output_files': len(outputs),
               'online_writes': 0, 'auto_approvals': 0}
    return outputs, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--snapshot', type=Path, help='Optional private offline test fixture; never committed')
    parser.add_argument('--apply', action='store_true', help='Write the validated plan to this checkout only')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding='utf8')) if args.snapshot else fetch_snapshot(os.environ.get('PARATRANZ_ICB_TOKEN'))
    baseline = json.loads((args.repo / BASELINE).read_text(encoding='utf8'))
    outputs, summary = plan(args.repo, snapshot, baseline)
    if args.apply:
        for relative, data in outputs.items():
            (args.repo / relative).write_bytes(data)
    rendered = '\n'.join(['# 帝都燃烧 ParaTranz 同步', '',
        f"核对 {summary['files']} 个文件、{summary['verified_rows']} 条。",
        f"译文变更 {summary['changed_translations']} 条，硬性军衔规范 {summary['hard_rank_normalizations']} 条，暂缓 {summary['held_rows']} 条。", '',
        '仅修改中文目标列、配套导出校验清单和同步基线；未上传 ParaTranz、自动审核、合并或发布。',
        '原文不进入日志、PR 正文或构建附件。请审核中文差异后再合并。', ''])
    if args.report:
        args.report.write_text(rendered, encoding='utf8')
    print(json.dumps(summary, ensure_ascii=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, urllib.error.URLError) as exc:
        # Exceptions never include fetched content, request headers or secrets.
        print(f'Sync stopped: {exc}', file=sys.stderr)
        sys.exit(1)
