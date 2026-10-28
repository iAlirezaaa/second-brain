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
    """True only when the real target and the requested spelling both stay inside root
    and outside DENIED. On Windows an 8.3 alias (RUNNER~1) and a resolved root name
    (runneradmin) are the same directory; the resolved check is then authoritative."""
    root_real = Path(root).resolve()
    try:
        resolved = Path(path).resolve().relative_to(root_real).parts
    except (ValueError, OSError, RuntimeError):
        return False
    try:
        lexical = Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root))).parts
    except ValueError:
        lexical = resolved
    return _allowed(lexical) and _allowed(resolved)
