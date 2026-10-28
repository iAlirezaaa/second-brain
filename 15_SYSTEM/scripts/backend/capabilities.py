"""Read-only capability inventory and keyword suggestions from the existing registry."""
import re
from pathlib import Path
from .tools_kit import bind_hades, default_registry
import common


def inventory(root, harness_id=''):
    root = Path(root).resolve()
    h = bind_hades(root)
    records = list(h.iter_records(h.config()))
    retired = h.superseded_by(records)
    items = []
    for path, record in records:
        kind = record.get('kind')
        if kind not in ('skill', 'plugin', 'mcp', 'app'):
            continue
        if kind == 'app' and 'extensions' not in path.relative_to(root).parts:
            continue
        identity = str(record.get('id', ''))
        if identity in retired or record.get('status') == 'deprecated':
            continue
        entry = str(record.get('entrypoint') or record.get('body_path') or '')
        description = str(record.get('description') or record.get('notes') or '')
        if kind == 'skill' and entry:
            target = (root / entry).resolve()
            allowed = root / 'skills'
            if allowed in target.parents and target.is_file():
                fm, _ = common.parse_frontmatter(target.read_text(encoding='utf-8', errors='replace'))
                description = str(fm.get('description') or description)
        supported = record.get('approved_for_harness_ids') or []
        if not isinstance(supported, list):
            supported = []
        compatibility = ('approved' if harness_id and harness_id in supported else
                         'not_approved' if harness_id and supported else 'unknown')
        items.append({'id': identity, 'kind': kind, 'name': record.get('name', ''),
                      'description': description, 'status': record.get('status', ''),
                      'origin': path.relative_to(root).as_posix(), 'entrypoint': entry,
                      'harness_compatibility': compatibility,
                      'approved_for_harness_ids': supported,
                      'permissions': record.get('permissions', 'unspecified'),
                      'installed': 'unknown'})
    registry = default_registry()
    for name in registry.names():
        tool = registry.get(name)
        items.append({'id': name, 'kind': 'tool', 'name': name, 'description': tool.description,
                      'status': 'available', 'origin': '15_SYSTEM/scripts/backend/tools_kit.py',
                      'entrypoint': '', 'harness_compatibility': 'unknown',
                      'approved_for_harness_ids': [],
                      'permissions': 'write_requires_approval_and_allowlist' if tool.writes else 'read',
                      'installed': 'built_in'})
    return sorted(items, key=lambda item: (item['kind'], item['id']))


def suggest(root, task, harness_id='', limit=10):
    if not isinstance(task, str) or not task.strip() or not 1 <= limit <= 100:
        raise ValueError('task and limit (1-100) are required')
    words = set(re.findall(r'\w+', task.casefold()))
    result = []
    for item in inventory(root, harness_id):
        hay = set(re.findall(r'\w+', (str(item['name']) + ' ' + item['description']).casefold()))
        overlap = sorted(words & hay)
        if overlap:
            result.append(dict(item, matched_terms=overlap, score=len(overlap)))
    result.sort(key=lambda item: (-item['score'], item['kind'], item['id']))
    return result[:limit]
