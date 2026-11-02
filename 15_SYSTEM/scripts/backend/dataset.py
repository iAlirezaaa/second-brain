"""Training data, but only from sources the owner marked shareable. (ROADMAP phase 36)

The promise is narrow on purpose. A fine-tuning pipeline is a claim factory, so the only
honest first step is the one that can be checked without training anything: every example
cites a `source_import` id and a byte range in that record's own `raw.txt`, a source nobody
marked is refused instead of silently included, and the manifest records ids, counts and a
digest so a run can be reproduced from records alone.

Nothing here leaves the machine. `leak_check` is the eval side of the gate: an independent
evaluation set may not share a single identifier -- case id, source id, origin -- with the
manifest this builder produced, because an eval that shares examples with training measures
memorisation, not retrieval. Whether a change is *better* is still not decided here: that is
`retrieval_eval.claim`, which needs the leak-gated eval, repeats, a margin and a saved base.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import sources

DATA = sources.DATA
SHARES = Path('dataset') / 'shares.json'


def shares_path(root):
    return Path(root) / DATA / SHARES


def read_shares(root):
    """{source_id: receipt} for the records the owner has explicitly marked shareable."""
    path = shares_path(root)
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    return {str(k): v for k, v in (data.get('shareable') or {}).items()}


def mark_shareable(root, source_id, approved=False):
    """Mark one imported record shareable. Without `approved=True` this only previews."""
    if not approved:
        return {'source_id': source_id, 'approved': False,
                'note': 'nothing was written; pass --approve to mark this source shareable'}
    folder = Path(root) / DATA / 'sources' / source_id
    if not folder.is_dir():
        raise ValueError('no source record %s — import it before marking it' % source_id)
    meta, _raw, _body = sources.validate_record(folder)
    path = shares_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    current = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'shareable': {}}
    current.setdefault('shareable', {})[source_id] = {
        'approved_at': datetime.now(timezone.utc).isoformat(),
        'kind': meta['kind'],
        'origin': meta['origin'],
        'sha256': meta['sha256'],
    }
    path.write_text(json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True) + '\n',
                    encoding='utf-8')
    return {'source_id': source_id, 'approved': True, 'kind': meta['kind'],
            'origin': meta['origin']}


def chunk_lines(body, limit=800):
    """(start_byte, end_byte, text) over `body`, grouped by whole lines.

    Byte offsets are into the record's `raw.txt`, because that is the file the record's own
    checksum covers -- an offset into a decoded string would not survive the next reader.
    """
    out = []
    offset = 0
    pending = []
    start = None
    for line in body.splitlines(keepends=True):
        raw_len = len(line.encode('utf-8'))
        if pending and sum(len(piece.encode('utf-8')) for piece in pending) + raw_len > limit:
            text = ''.join(pending)
            out.append((start, offset, text))
            pending, start = [], None
        if start is None:
            start = offset
        pending.append(line)
        offset += raw_len
    if pending:
        out.append((start, offset, ''.join(pending)))
    return out


def build(root, out, approved_ids=None, limit=800):
    """Write examples.jsonl + manifest.json for shareable sources only; refuse anything else."""
    root = Path(root)
    out = Path(out)
    if out.exists():
        raise ValueError('%s already exists — a dataset is written once, to a new folder' % out)
    sources_dir = root / DATA / 'sources'
    folders = sorted(p for p in sources_dir.iterdir() if p.is_dir()) if sources_dir.is_dir() else []
    if not folders:
        raise ValueError('no imported sources — nothing to build a dataset from')
    shares = read_shares(root)
    picked, refused = [], []
    for folder in folders:
        meta, raw, body = sources.validate_record(folder)
        if approved_ids is not None and meta['id'] not in approved_ids:
            continue
        if meta['id'] not in shares:
            refused.append(meta['id'])
            continue
        if shares[meta['id']].get('sha256') != meta['sha256']:
            raise ValueError('source %s changed after it was marked shareable' % meta['id'])
        picked.append((meta, raw, body))
    if refused:
        raise ValueError('refusing %d source(s) nobody marked shareable: %s'
                         % (len(refused), ', '.join(refused)))
    if not picked:
        raise ValueError('every source is marked, but none matched the requested set')
    examples = []
    manifest_sources = []
    for meta, raw, body in picked:
        rows = 0
        for start, end, text in chunk_lines(body, limit):
            if not text.strip():
                continue
            if raw[start:end] != text.encode('utf-8'):
                raise ValueError('byte range %d-%d does not reproduce %s; the chunker is lying'
                                 % (start, end, meta['id']))
            rows += 1
            examples.append({'id': '%s:%d-%d' % (meta['id'], start, end),
                             'source_id': meta['id'], 'kind': meta['kind'],
                             'origin': meta['origin'], 'start': start, 'end': end,
                             'text': text})
        manifest_sources.append({'id': meta['id'], 'kind': meta['kind'],
                                 'origin': meta['origin'], 'sha256': meta['sha256'],
                                 'examples': rows})
    payload = ''.join(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n'
                      for row in examples).encode('utf-8')
    digest = hashlib.sha256(payload).hexdigest()
    manifest = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'digest': digest,
        'counts': {'sources': len(manifest_sources), 'examples': len(examples),
                   'bytes': len(payload)},
        'sources': manifest_sources,
        'refused': [],
        'note': 'shareable sources only; every example cites a source id and a byte range',
    }
    out.mkdir(parents=True, exist_ok=False)
    (out / 'examples.jsonl').write_bytes(payload)
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2,
                                                  sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def verify(out):
    """Re-hash a built dataset and compare it to its manifest -- a clone can check this."""
    out = Path(out)
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    payload = (out / 'examples.jsonl').read_bytes()
    actual = hashlib.sha256(payload).hexdigest()
    rows = [json.loads(line) for line in payload.decode('utf-8').splitlines() if line.strip()]
    problems = []
    if actual != manifest['digest']:
        problems.append('digest %s does not match the manifest %s'
                        % (actual, manifest['digest']))
    if len(rows) != manifest['counts']['examples']:
        problems.append('%d example(s) on disk, manifest counts %d'
                        % (len(rows), manifest['counts']['examples']))
    counted = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get('source_id'):
            problems.append('an example without a source id is not a citation: %r' % (row,))
            continue
        counted[row['source_id']] = counted.get(row['source_id'], 0) + 1
    for entry in manifest['sources']:
        if counted.get(entry['id'], 0) != entry['examples']:
            problems.append('source %s: %d example(s) on disk, manifest counts %d'
                            % (entry['id'], counted.get(entry['id'], 0), entry['examples']))
    return {'ok': not problems, 'problems': problems, 'digest': actual,
            'examples': len(rows)}


def training_index(out):
    """Every identifier a built dataset publishes: source ids, origins and example ids.

    The eval leak gate needs the full set, and it reads it through `verify` first: a
    tampered folder cannot hide a trained id by editing its manifest, because the
    manifest has to agree with the examples before anything is banned from the eval.
    """
    out = Path(out)
    report = verify(out)
    if not report['ok']:
        raise ValueError('dataset %s does not verify against its manifest: %s'
                         % (out, '; '.join(report['problems'])))
    manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
    rows = [json.loads(line) for line
            in (out / 'examples.jsonl').read_bytes().decode('utf-8').splitlines() if line.strip()]
    return {'digest': manifest['digest'],
            'source_ids': {entry['id'] for entry in manifest['sources']},
            'origins': {entry['origin'] for entry in manifest['sources']},
            'example_ids': {row['id'] for row in rows if isinstance(row, dict) and row.get('id')}}


def load_eval_cases(path):
    """(cases, documents) from an eval file: a retrieval-golden-style fixture or a case list."""
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(data, list):
        cases, documents = data, []
    elif isinstance(data, dict) and isinstance(data.get('cases'), list):
        cases, documents = data['cases'], data.get('documents') or []
    else:
        raise ValueError('an eval file is a retrieval-golden-style fixture with cases, '
                         'or a plain list of cases')
    known = {doc.get('name') for doc in documents if isinstance(doc, dict)}
    for index, case in enumerate(cases):
        if not isinstance(case, dict) or not str(case.get('query', '')).strip():
            raise ValueError('eval case %d needs a nonempty query' % index)
        name = case.get('expected')
        if name is not None and name not in known:
            raise ValueError('eval case %s names document %r that the fixture does not define'
                             % (case.get('id') or index, name))
        if name is None and not case.get('expected_ids'):
            raise ValueError('eval case %s needs expected or expected_ids' % (case.get('id') or index))
    return cases, documents


def case_identifiers(case, documents):
    """What one eval case touches: its own id, its expected source ids, its document origin."""
    known = {doc.get('name'): doc for doc in documents if isinstance(doc, dict)}
    identifiers = []
    if case.get('id'):
        identifiers.append(str(case['id']))
    identifiers += [str(item) for item in (case.get('expected_ids') or [])]
    name = case.get('expected')
    if name is not None:
        identifiers.append(str(name))
        origin = (known.get(name) or {}).get('origin')
        if origin:
            identifiers.append(str(origin))
    return [item for item in identifiers if item]


def leak_check(out, cases_path):
    """Refuse an eval set that shares any identifier with a built dataset's training manifest.

    An eval that shares examples with training measures memorisation, not retrieval, so a
    case whose id, expected source id or expected document origin appears in the manifest
    (or in the example ids beside it) is named and refused. This is the same rule the
    roadmap states for the independent eval, made reachable from `sources.py
    dataset-eval-gate DATASET_DIR EVAL_JSON`.
    """
    cases, documents = load_eval_cases(cases_path)
    index = training_index(out)
    banned = index['source_ids'] | index['origins'] | index['example_ids']
    leaks = []
    for case in cases:
        case_id = str(case.get('id') or case['query'])
        for identifier in case_identifiers(case, documents):
            if identifier in banned:
                leaks.append({'case': case_id, 'identifier': identifier,
                              'why': 'appears in the training manifest of dataset %s' % out})
    return {'ok': not leaks, 'leaks': leaks, 'cases': len(cases),
            'dataset_digest': index['digest'],
            'note': 'an eval that shares examples with training measures memorisation, '
                    'not retrieval; every listed identifier is banned'}
