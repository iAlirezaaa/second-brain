"""Default tool read boundary; this is not an operating-system ACL."""
import os
from pathlib import Path

DENIED = (
    ('12_RUNTIME',), ('13_LAB',), ('14_CANDIDATES',), ('.kb',), ('.brain-data',),
    ('15_SYSTEM', 'generated'), ('15_SYSTEM', 'backups'),
    ('09_OPERATIONS', 'clients_metadata_only'),
)


def _allowed(parts):
    folded = tuple(part.casefold() for part in parts)
    if not folded or any(part in ('.git', '.secrets', 'secrets') for part in folded):
        return False
    name = folded[-1]
    if (name == '.env' or name.startswith('.env.') or name.endswith(('.pem', '.key', '.token'))
            or ('credentials' in name and name.endswith('.json'))):
        return False
    return not any(folded[:len(prefix)] == tuple(p.casefold() for p in prefix)
                   for prefix in DENIED)


def readable(root, path):
    root = Path(root).resolve()
    try:
        lexical = Path(os.path.abspath(path)).relative_to(root).parts
        resolved = Path(path).resolve().relative_to(root).parts
    except (ValueError, OSError, RuntimeError):
        return False
    return _allowed(lexical) and _allowed(resolved)
