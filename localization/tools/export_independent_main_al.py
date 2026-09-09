"""Publish independently discovered labels with hashes, never full script examples."""
import argparse
import hashlib
import json
from pathlib import Path


def evidence(item):
    return {'source_id': item['source_id'], **{
        key+'_sha256': hashlib.sha256(item[key].encode('utf-8')).hexdigest()
        for key in ('ja', 'en', 'zh')}}


def export(source, destination):
    freeze = json.loads((source/'independent-freeze.json').read_text(encoding='utf-8'))
    if freeze['project_glossary_inputs'] or freeze['seed_terms']:
        raise ValueError('not an independent discovery freeze')
    documents = {'discovery-freeze.json': freeze}
    for game in ('ml', 'al'):
        for filename in ('independent-baseline.json', 'speaker-baseline.json'):
            raw = (source/game/filename).read_bytes()
            if hashlib.sha256(raw).hexdigest() != freeze['files'][game][filename]:
                raise ValueError('frozen baseline changed')
            rows = json.loads(raw)
            if filename == 'independent-baseline.json':
                public = [{k: r[k] for k in ('term_id', 'jp', 'groups', 'categories', 'automatic_replacement_authorized')} |
                          {'variants': [{'cn': v['cn'], 'evidence': [evidence(e) for e in v['evidence']]}
                                        for v in r['variants']]} for r in rows]
            else:
                public = [{k: r[k] for k in ('jp', 'cn', 'en_variants', 'status', 'occurrences', 'automatic_replacement_authorized')} |
                          {'evidence': [evidence(e) for e in r['examples']]} for r in rows]
            documents[game+'-'+filename] = public
    documents['shared-forms.json'] = json.loads((source/'main-al-shared-reference.json').read_text(encoding='utf-8'))
    if any((destination/name).exists() for name in documents):
        raise FileExistsError('export destination already populated')
    destination.mkdir(parents=True, exist_ok=True)
    for name, data in documents.items():
        (destination/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    export(args.source, args.destination)
