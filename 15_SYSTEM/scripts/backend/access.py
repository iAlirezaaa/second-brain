"""Default tool read boundary; this is not an operating-system ACL."""
import os
from pathlib import Path

DENIED = (
    ('12_RUNTIME',), ('13_LAB',), ('14_CANDIDATES',), ('.kb',), ('.brain-data',),
    ('15_SYSTEM', 'generated'), ('15_SYSTEM', 'backups'),
    ('09_OPERATIONS', 'clients_metadata_only'),
)


def _denial(parts):
    """None when the path passes every rule below, else the name of the rule that stopped it.

    This is the whole law in one place. `readable()` is the yes/no a caller asks for; the
    refusals a door prints are built from these names, so a refusal can quote the rule it
    enforced instead of inventing a sentence about it that can drift away from it.
    """
    folded = tuple(part.casefold() for part in parts)
    if not folded:
        return "an empty path"
    if any(part in ('.git', '.secrets', 'secrets') for part in folded):
        return ".git/.secrets"
    name = folded[-1]
    if (name == '.env' or name.startswith('.env.') or name.endswith(('.pem', '.key', '.token'))
            or ('credentials' in name and name.endswith('.json'))):
        return "a secret-bearing filename"
    for prefix in DENIED:
        if folded[:len(prefix)] == tuple(p.casefold() for p in prefix):
            return "/".join(prefix)
    return None


def _allowed(parts):
    return _denial(parts) is None


def readable(root, path):
    """True only when the real target and the requested spelling both stay inside root
    and outside DENIED. On Windows an 8.3 alias (RUNNER~1) and a resolved root name
    (runneradmin) are the same directory; the resolved check is then authoritative."""
    return denial(root, path) is None


def denial(root, path):
    """None when the door may read this path; otherwise the name of the rule that said no.

    `readable()` and `denial()` are one law with two answers, and a caller that refuses is
    expected to quote what this returned rather than write its own sentence about it. A
    refusal that invents its own reason is a second policy: it drifts, and the reader cannot
    tell which rule is actually in force.
    """
    root_real = Path(root).resolve()
    try:
        resolved = Path(path).resolve().relative_to(root_real).parts
    except (ValueError, OSError, RuntimeError):
        return "outside the brain this door serves"
    try:
        lexical = Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(root))).parts
    except ValueError:
        lexical = resolved
    return _denial(lexical) or _denial(resolved)
