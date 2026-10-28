"""Reviewable local lessons grounded in explicitly imported sources."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from . import sources

ID = re.compile(r'^[0-9a-f]{64}$')


def _record(root, source_id):
    if not isinstance(source_id, str) or not ID.fullmatch(source_id):
        raise ValueError('invalid source id')
    return sources.validate_record(Path(root) / sources.DATA / 'sources' / source_id)


def _proposal_path(root, proposal_id):
    if not isinstance(proposal_id, str) or not ID.fullmatch(proposal_id):
        raise ValueError('invalid proposal id')
    return Path(root) / sources.DATA / 'learning' / 'proposals' / (proposal_id + '.json')


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def propose(root, source_id, quote, lesson, query):
    """Create a candidate from an agent- or human-supplied interpretation, not an asserted fact."""
    if not all(isinstance(x, str) and x.strip() for x in (quote, lesson, query)):
        raise ValueError('quote, lesson and retrieval query are required')
    meta, _, body = _record(root, source_id)
    if quote not in body:
        raise ValueError('quote is not present in the source text')
    content = {'source_id': source_id, 'source_sha256': meta['sha256'],
               'quote': quote, 'lesson': lesson.strip(), 'query': query.strip()}
    identity = _digest(content)
    path = _proposal_path(root, identity)
    if path.exists():
        existing = _load(root, identity)
        return existing
    row = dict(content, id=identity, status='proposed',
               created_at=datetime.now(timezone.utc).isoformat())
    sources._atomic(path, json.dumps(row, ensure_ascii=False, indent=2) + '\n')
    return row


def _load(root, proposal_id):
    row = json.loads(_proposal_path(root, proposal_id).read_text(encoding='utf-8'))
    content = {name: row[name] for name in ('source_id', 'source_sha256', 'quote', 'lesson', 'query')}
    if row.get('id') != proposal_id or _digest(content) != proposal_id or row.get('status') != 'proposed':
        raise ValueError('proposal was modified or is invalid')
    return row


def evaluate(root, proposal_id):
    """Check provenance and whether the configured query retrieves the source; not truth or quality."""
    row = _load(root, proposal_id)
    meta, _, body = _record(root, row['source_id'])
    evidence_matches = meta['sha256'] == row['source_sha256'] and row['quote'] in body
    results = sources.search(root, row['query'], limit=100)
    retrieved = any(hit['id'] == row['source_id'] for hit in results)
    return {'proposal_id': proposal_id, 'source_id': row['source_id'], 'origin': meta['origin'],
            'evidence_matches': evidence_matches, 'source_retrieved': retrieved,
            'passed': evidence_matches and retrieved,
            'limitation': 'Does not determine whether the lesson is true or improves performance.'}


def approve(root, proposal_id, approved=False):
    if not approved:
        raise ValueError('explicit human approval is required')
    result = evaluate(root, proposal_id)
    if not result['passed']:
        raise ValueError('proposal did not pass evidence and retrieval checks')
    path = Path(root) / sources.DATA / 'learning' / 'approved' / (proposal_id + '.json')
    if path.exists():
        receipt = json.loads(path.read_text(encoding='utf-8'))
        if receipt.get('proposal_id') != proposal_id or receipt.get('decision') != 'approved':
            raise ValueError('approval receipt is invalid')
        return receipt
    receipt = {'proposal_id': proposal_id, 'decision': 'approved',
               'approved_at': datetime.now(timezone.utc).isoformat(), 'evaluation': result}
    sources._atomic(path, json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    return receipt


def recall(root, query, limit=10):
    if not isinstance(query, str) or not query.strip() or not 1 <= limit <= 100:
        raise ValueError('query and limit (1-100) are required')
    base = Path(root) / sources.DATA / 'learning' / 'approved'
    result = []
    for receipt_path in sorted(base.glob('*.json')):
        identity = receipt_path.stem
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        if receipt.get('proposal_id') != identity or receipt.get('decision') != 'approved':
            raise ValueError('approval receipt is invalid')
        row = _load(root, identity)
        meta, _, body = _record(root, row['source_id'])
        if meta['sha256'] != row['source_sha256'] or row['quote'] not in body:
            raise ValueError('approved lesson evidence no longer matches')
        if query.casefold() in (row['lesson'] + ' ' + row['query']).casefold():
            result.append({'id': identity, 'lesson': row['lesson'], 'quote': row['quote'],
                           'source_id': row['source_id'], 'origin': meta['origin'],
                           'approved_at': receipt['approved_at']})
        if len(result) >= limit:
            break
    return result
