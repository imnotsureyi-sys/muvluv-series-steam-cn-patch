"""Export term-level reference data, never official script examples or local paths."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

TERM_FIELDS = ('jp', 'cn', 'en_label', 'category', 'status', 'context', 'occurrences', 'project_preferred')


def digest(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def public_term(term: dict, sources: dict[str, dict]) -> dict:
    ids = term['source_ids']
    if term['occurrences'] != len(ids) or any(key not in sources for key in ids):
        raise ValueError('invalid occurrence count or source reference')
    result = {key: term[key] for key in TERM_FIELDS if key in term}
    # Only term labels survive. Full sentences remain in the local source baseline.
    for key in ('jp', 'cn', 'en_label'):
        value = result.get(key, '')
        if any(c in value for c in ('\n', '\r', '\x00', '「', '」')):
            raise ValueError(f'non-term text in {key}')
    result['evidence'] = []
    for example in term['examples'][:2]:
        source = sources[example['source_id']]
        result['evidence'].append({
            'source_id': source['id'],
            'record_sha256': source['record_sha256'],
            **{language + '_sha256': digest(source[language]) for language in ('ja', 'en', 'zh')},
        })
    return result


def export(local: Path, output: Path) -> None:
    def read(name: str):
        return json.loads((local / name).read_text(encoding='utf-8'))

    documents = {}
    summary = read('summary.json')
    for game in ('ml', 'al'):
        baseline = read(game + '-source-baseline.json')
        sources = {row['id']: row for row in baseline}
        if len(sources) != len(baseline) or len(baseline) != summary[game]['dialogue_rows']:
            raise ValueError('duplicate source ids or inconsistent baseline count')
        for kind in ('reference-terms', 'speaker-terms'):
            documents[game + '-' + kind + '.json'] = [
                public_term(term, sources) for term in read(game + '-' + kind + '.json')
            ]
    documents['common-reference-terms.json'] = read('common-reference-terms.json')
    documents['summary.json'] = summary
    verified = read('source-verification.json')
    documents['source-verification.json'] = {
        'records': verified['records'], 'language_fields': verified['language_fields'],
        'readback_mismatches': verified['readback_mismatches'],
        'archives': [{
            key: (Path(value).name if key == 'file' else value)
            for key, value in archive.items() if key != 'mtime_ns'
        } for archive in verified['archives']],
    }
    if verified['readback_mismatches']:
        raise ValueError('source verification has mismatches')
    targets = [output / name for name in documents]
    if any(path.exists() for path in targets):
        raise FileExistsError('refusing to overwrite an existing public export')
    output.mkdir(parents=True, exist_ok=True)
    for name, document in documents.items():
        with (output / name).open('x', encoding='utf-8') as stream:
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write('\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--local-results', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export(args.local_results, args.output)
