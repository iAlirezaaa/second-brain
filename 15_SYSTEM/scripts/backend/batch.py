"""Explicit manifest-based source import with a reviewable content-bound plan."""
import hashlib
import json
from pathlib import Path
from . import sources


def _prepare(manifest):
    manifest = Path(manifest).resolve(strict=True)
    rows = json.loads(manifest.read_text(encoding='utf-8'))
    if not isinstance(rows, list) or not rows:
        raise ValueError('manifest must be a nonempty array')
    plan, snapshots = [], []
    for number, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError('entry %d must be an object' % number)
        file, kind, origin, fmt = row.get('path'), row.get('kind'), row.get('origin'), row.get('format', 'text')
        if not isinstance(file, str) or not file.strip() or not isinstance(origin, str) or not origin.strip():
            raise ValueError('entry %d requires a path and origin' % number)
        if kind not in sources.KINDS or fmt not in sources.FORMATS or (fmt != 'text' and kind != 'conversation'):
            raise ValueError('entry %d has an invalid kind or format' % number)
        path = (manifest.parent / file).resolve(strict=True)
        raw = path.read_bytes()
        if not sources.extract_text(raw, fmt).strip():
            raise ValueError('entry %d is empty' % number)
        digest = hashlib.sha256(raw).hexdigest()
        plan.append({'path': str(path), 'kind': kind, 'origin': origin, 'format': fmt, 'sha256': digest})
        snapshots.append((path.name, raw))
    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return plan, snapshots, hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def run(root, manifest, apply=False, plan_id=''):
    plan, snapshots, identity = _prepare(manifest)
    result = {'plan_id': identity, 'entries': plan, 'applied': False, 'imported': [], 'indexed': None}
    if not apply:
        return result
    if plan_id != identity:
        raise ValueError('plan missing or stale; preview the current manifest again')
    for entry, (filename, raw) in zip(plan, snapshots):
        try:
            meta = sources.ingest_bytes(root, raw, filename, entry['kind'], entry['origin'], entry['format'])
            result['imported'].append(meta['id'])
        except (OSError, ValueError, KeyError) as exc:
            result['error'] = 'import failed after %d entries: %s' % (len(result['imported']), exc)
            return result
    try:
        result['indexed'] = sources.rebuild(root)
    except (OSError, ValueError, KeyError) as exc:
        result['error'] = 'index rebuild failed: %s' % exc
        return result
    result['applied'] = True
    return result
