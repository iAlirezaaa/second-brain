"""Training data, but only from sources the owner marked shareable. (ROADMAP phase 36)

The promise is narrow on purpose. A fine-tuning pipeline is a claim factory, so the only
honest first step is the one that can be checked without training anything: every example
cites a `source_import` id and a byte range in that record's own `raw.txt`, a source nobody
marked is refused instead of silently included, and the manifest records ids, counts and a
digest so a run can be reproduced from records alone.

Nothing here leaves the machine, and nothing here decides that a model got better -- that
needs the independent eval and the before/after report still listed as planned.
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
