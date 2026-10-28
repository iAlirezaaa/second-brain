"""Reviewable, explicit copying of an approved local skill to a chosen host directory."""
import hashlib
import json
import re
from pathlib import Path
from . import capabilities

NAME = re.compile(r'^[a-z0-9][a-z0-9-]{0,63}$')
RESERVED = {'con', 'prn', 'aux', 'nul'} | {'com%d' % i for i in range(1, 10)} | {'lpt%d' % i for i in range(1, 10)}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def _snapshot(root, skill_id, harness_id, destination):
    root = Path(root).resolve()
    target = Path(destination).resolve(strict=True)
    if not target.is_dir():
        raise ValueError('destination must be an existing directory')
    matches = [item for item in capabilities.inventory(root, harness_id)
               if item['id'] == skill_id and item['kind'] == 'skill']
    if len(matches) != 1:
        raise ValueError('skill not found or ambiguous')
    item = matches[0]
    if item['status'] != 'approved' or not harness_id or item['harness_compatibility'] != 'approved':
        raise ValueError('skill and selected harness must both be explicitly approved')
    name = item['name']
    if not isinstance(name, str) or not NAME.fullmatch(name) or name in RESERVED:
        raise ValueError('invalid skill directory name')
    entry = root / item['entrypoint']
    if entry.is_symlink() or entry.name != 'SKILL.md':
        raise ValueError('skill entrypoint must be a regular SKILL.md')
    skill_dir = entry.parent.resolve(strict=True)
    skills_root = (root / 'skills').resolve()
    if skill_dir.parent != skills_root or skill_dir.name != name:
        raise ValueError('skill must be in its named directory under skills')
    if not entry.is_file() or target == skill_dir or skill_dir in target.parents:
        raise ValueError('invalid entrypoint or destination')
    if (target / name).exists() or (target / name).is_symlink():
        raise ValueError('destination already exists; no replacement is supported')
    contents = {}
    for path in sorted(skill_dir.rglob('*')):
        if path.is_symlink():
            raise ValueError('skill contains a symbolic link')
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError('skill contains a non-regular file')
        contents[path.relative_to(skill_dir).as_posix()] = path.read_bytes()
    if 'SKILL.md' not in contents:
        raise ValueError('skill has no SKILL.md')
    if '.install-incomplete' in contents:
        raise ValueError('skill conflicts with the installation marker')
    files = {path: hashlib.sha256(data).hexdigest() for path, data in contents.items()}
    payload = {'version': 1, 'skill_id': skill_id, 'harness_id': harness_id,
               'name': name, 'source': str(skill_dir), 'destination': str(target),
               'registry_origin': item['origin'], 'permissions': item['permissions'], 'files': files}
    return payload, contents


def plan(root, skill_id, harness_id, destination):
    payload, _ = _snapshot(root, skill_id, harness_id, destination)
    return dict(payload, plan_id=_digest(payload))


def apply(root, reviewed, approved=False):
    if not approved:
        raise ValueError('explicit approval is required')
    if not isinstance(reviewed, dict):
        raise ValueError('invalid plan')
    payload, contents = _snapshot(root, reviewed.get('skill_id'), reviewed.get('harness_id'),
                                  reviewed.get('destination'))
    if reviewed != dict(payload, plan_id=_digest(payload)):
        raise ValueError('plan is stale or modified; review a new plan')
    target = Path(payload['destination']) / payload['name']
    target.mkdir(exist_ok=False)
    marker = target / '.install-incomplete'
    marker.write_text('Installation is incomplete; inspect this directory before retrying.\n', encoding='utf-8')
    for relative, raw in contents.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(raw)
    marker.unlink()
    return {'installed': str(target), 'plan_id': reviewed['plan_id'], 'files': len(contents)}
