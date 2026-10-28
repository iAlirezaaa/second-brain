"""Explicit, additive source transfer via a user-selected folder, with conflict preview."""
import json
from pathlib import Path
from . import learning, sources


def _records(base):
    directory = Path(base) / 'sources'
    if directory.is_symlink():
        raise ValueError('source directory cannot be a symbolic link')
    result = {}
    if not directory.is_dir():
        return result
    for folder in sorted(directory.iterdir()):
        if not folder.is_dir() or folder.is_symlink():
            raise ValueError('unexpected item in source directory')
        meta, raw, _ = sources.validate_record(folder)
        result[meta['id']] = (meta, raw)
    return result


def _lessons(base, records):
    folder = Path(base) / 'learning'
    if folder.is_symlink():
        raise ValueError('learning directory cannot be a symbolic link')
    proposals, approvals = {}, {}
    for kind, result in (('proposals', proposals), ('approved', approvals)):
        directory = folder / kind
        if directory.is_symlink():
            raise ValueError('learning record directory cannot be a symbolic link')
        for path in sorted(directory.glob('*.json')):
            if path.is_symlink() or not learning.ID.fullmatch(path.stem):
                raise ValueError('invalid learning record path')
            row = json.loads(path.read_text(encoding='utf-8'))
            if kind == 'proposals':
                fields = {key: row[key] for key in ('source_id', 'source_sha256', 'quote', 'lesson', 'query')}
                if row.get('id') != path.stem or row.get('status') != 'proposed' or learning._digest(fields) != path.stem:
                    raise ValueError('invalid proposal')
                if row['source_id'] not in records:
                    raise ValueError('proposal references a missing source')
                meta, raw = records[row['source_id']]
                body = sources.extract_text(raw, meta.get('format', 'text'))
                if meta['sha256'] != row['source_sha256'] or row['quote'] not in body:
                    raise ValueError('proposal evidence does not match source')
            else:
                evaluation = row.get('evaluation')
                if (row.get('proposal_id') != path.stem or row.get('decision') != 'approved'
                        or not isinstance(row.get('approved_at'), str) or not row['approved_at']
                        or not isinstance(evaluation, dict) or evaluation.get('proposal_id') != path.stem
                        or evaluation.get('passed') is not True or evaluation.get('evidence_matches') is not True
                        or evaluation.get('source_retrieved') is not True):
                    raise ValueError('invalid approval receipt')
            result[path.stem] = row
    if set(approvals) - set(proposals):
        raise ValueError('approval references a missing proposal')
    for identity, receipt in approvals.items():
        if receipt['evaluation'].get('source_id') != proposals[identity]['source_id']:
            raise ValueError('approval references a different source')
    return proposals, approvals


def transfer(source_dir, destination_dir, apply=False, allow_conflicts=False, include_approvals=False):
    source_dir, destination_dir = Path(source_dir).resolve(), Path(destination_dir).resolve()
    if not source_dir.is_dir() or not (source_dir / 'sources').is_dir():
        raise ValueError('source data directory does not contain sources')
    if destination_dir.exists() and not destination_dir.is_dir():
        raise ValueError('destination must be a directory')
    if source_dir == destination_dir or source_dir in destination_dir.parents or destination_dir in source_dir.parents:
        raise ValueError('source and destination must be separate directories')
    incoming, existing = _records(source_dir), _records(destination_dir)
    incoming_proposals, incoming_approvals = _lessons(source_dir, incoming)
    existing_proposals, existing_approvals = _lessons(destination_dir, existing)
    new = sorted(set(incoming) - set(existing))
    new_proposals = sorted(set(incoming_proposals) - set(existing_proposals))
    new_approvals = sorted(set(incoming_approvals) - set(existing_approvals))
    conflicts = []
    for identity in sorted(set(incoming) & set(existing)):
        a, b = incoming[identity][0], existing[identity][0]
        if a.get('format', 'text') != b.get('format', 'text'):
            raise ValueError('same source identity has different extraction formats')
    for identity in new:
        meta = incoming[identity][0]
        others = sorted(i for i, (old, _) in existing.items()
                        if old['kind'] == meta['kind'] and old['origin'] == meta['origin'])
        others += sorted(i for i in new if i != identity and i < identity
                         and incoming[i][0]['kind'] == meta['kind']
                         and incoming[i][0]['origin'] == meta['origin'])
        if others:
            conflicts.append({'incoming': identity, 'existing': others, 'origin': meta['origin']})
    if apply:
        if conflicts and not allow_conflicts:
            raise ValueError('conflicts found; review preview and explicitly allow conflicts')
        for identity in new:
            meta, raw = incoming[identity]
            folder = destination_dir / 'sources' / identity
            folder.mkdir(parents=True, exist_ok=False)
            sources._atomic(folder / 'raw.txt', raw)
            sources._atomic(folder / 'metadata.json', json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
        for identity in new_proposals:
            path = destination_dir / 'learning' / 'proposals' / (identity + '.json')
            sources._atomic(path, json.dumps(incoming_proposals[identity], ensure_ascii=False, indent=2) + '\n')
        if include_approvals:
            for identity in new_approvals:
                path = destination_dir / 'learning' / 'approved' / (identity + '.json')
                sources._atomic(path, json.dumps(incoming_approvals[identity], ensure_ascii=False, indent=2) + '\n')
    return {'new': new, 'already_present': len(set(incoming) & set(existing)),
            'new_proposals': new_proposals, 'new_approvals': new_approvals,
            'approvals_imported': bool(apply and include_approvals),
            'conflicts': conflicts, 'applied': bool(apply)}


def verify_copy(source_dir, destination_dir):
    """Verify all source records and decisions exist unchanged in a copy; extras are allowed."""
    source_dir, destination_dir = Path(source_dir).resolve(), Path(destination_dir).resolve()
    if source_dir == destination_dir or source_dir in destination_dir.parents or destination_dir in source_dir.parents:
        raise ValueError('source and destination must be separate directories')
    if not (source_dir / 'sources').is_dir() or not (destination_dir / 'sources').is_dir():
        raise ValueError('both directories must contain sources')
    original, copy = _records(source_dir), _records(destination_dir)
    proposals, approvals = _lessons(source_dir, original)
    copy_proposals, copy_approvals = _lessons(destination_dir, copy)
    missing, changed = [], []
    for label, left, right in (('source', original, copy), ('proposal', proposals, copy_proposals),
                               ('approval', approvals, copy_approvals)):
        for identity, value in left.items():
            if identity not in right:
                missing.append('%s:%s' % (label, identity))
            elif value != right[identity]:
                changed.append('%s:%s' % (label, identity))
    return {'verified': not missing and not changed, 'missing': sorted(missing),
            'changed': sorted(changed), 'sources_checked': len(original),
            'proposals_checked': len(proposals), 'approvals_checked': len(approvals)}
