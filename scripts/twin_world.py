"""Twin World 1a: deterministic in-memory file overlay and diff preview.

No subprocesses, tools, network requests, or filesystem writes. This is not a
container or security sandbox; it is a safe rehearsal of declared file edits.
Only read-approved, size-bounded UTF-8 files can participate.
"""
import difflib
import hashlib
from pathlib import Path

MAX_OPS = 50
MAX_FILE_BYTES = 131072
MAX_TOTAL_BYTES = 1048576
PROTECTED = frozenset((".brain-data", ".kb", ".git", ".secrets", "secrets",
                       "12_RUNTIME", "13_LAB", "14_CANDIDATES", "09_OPERATIONS"))
PROTECTED_PREFIXES = ("15_SYSTEM/generated", "15_SYSTEM/backups", "15_SYSTEM/logs")


def _blocked(path):
    parts = path.parts
    return (any(part in PROTECTED or part.startswith(".env") for part in parts)
            or any(path.as_posix().startswith(prefix + "/") or path.as_posix() == prefix
                   for prefix in PROTECTED_PREFIXES))
OPERATIONS = frozenset(("write", "append", "delete"))


class TwinRefused(ValueError):
    pass


def safe_path(root, path):
    if not isinstance(path, str) or not path.strip() or len(path) > 500:
        raise TwinRefused("file path must be a non-empty relative string")
    candidate = Path(path.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts or "." in candidate.parts:
        raise TwinRefused("absolute/traversal paths are not allowed")
    if _blocked(candidate):
        raise TwinRefused("private or quarantined scope may not be simulated")
    base = Path(root).resolve()
    resolved = (base / candidate).resolve(strict=False)
    if base not in resolved.parents:
        raise TwinRefused("symlink or path escapes the simulation root")
    rel = resolved.relative_to(base)
    if _blocked(rel):
        raise TwinRefused("resolved path enters a private or protected scope")
    if resolved.exists() and not resolved.is_file():
        raise TwinRefused("simulation target is not a regular file")
    return resolved, candidate.as_posix()


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text is not None else None


def _load(root, rel):
    path, label = safe_path(root, rel)
    if path.is_file():
        if path.stat().st_size > MAX_FILE_BYTES:
            raise TwinRefused("source file is too large for Twin World 1a")
        try:
            return path.read_text(encoding="utf-8"), label
        except (OSError, UnicodeDecodeError):
            raise TwinRefused("source file is not a readable UTF-8 text file")
    return None, label


def simulate(root, plan):
    """Returns a reproducible in-memory counterfactual; never writes to root."""
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_OPS:
        raise TwinRefused("plan must contain 1-50 declared file operations")
    originals = {}
    overlay = {}
    transcript = []
    for index, step in enumerate(plan, 1):
        if not isinstance(step, dict) or step.get("op") not in OPERATIONS:
            raise TwinRefused("unsupported operation at step %d" % index)
        op = step["op"]
        path = step.get("path")
        absolute, label = safe_path(root, path)
        if label not in originals:
            originals[label], _ = _load(root, path)
            overlay[label] = originals[label]
        old = overlay[label]
        if op == "delete":
            if old is None:
                raise TwinRefused("cannot delete absent file: %s" % label)
            overlay[label] = None
        else:
            data = step.get("text")
            if not isinstance(data, str):
                raise TwinRefused("%s requires text: %s" % (op, label))
            if op == "append" and old is None:
                raise TwinRefused("cannot append to absent file: %s" % label)
            result = data if op == "write" else old + data
            if len(result.encode("utf-8")) > MAX_FILE_BYTES:
                raise TwinRefused("simulated content is too large: %s" % label)
            overlay[label] = result
        transcript.append({"step": index, "op": op, "path": label})
        current_bytes = sum(len((t or "").encode("utf-8")) for t in overlay.values())
        if current_bytes > MAX_TOTAL_BYTES:
            raise TwinRefused("simulation exceeds 1 MiB total memory budget")
    outputs = []
    for label in sorted(overlay):
        before, after = originals[label], overlay[label]
        if before is None:
            outcome = "added"
        elif after is None:
            outcome = "deleted"
        elif before == after:
            outcome = "unchanged"
        else:
            outcome = "changed"
        lines = list(difflib.unified_diff(
            (before or "").splitlines(keepends=True),
            (after or "").splitlines(keepends=True),
            fromfile="before/" + label, tofile="twin/" + label, n=3))
        preview = "".join(lines)
        outputs.append({"path": label, "outcome": outcome,
                        "before_sha256": _digest(before),
                        "after_sha256": _digest(after),
                        "delta_bytes": len((after or "").encode("utf-8")) -
                                       len((before or "").encode("utf-8")),
                        "diff": preview[:4000], "diff_truncated": len(preview) > 4000})
    return {"world": "Twin World 1a - in-memory file overlay",
            "operations": transcript, "files": outputs,
            "files_written": 0, "tools_executed": 0, "network_requests": 0,
            "note": "Simulation only: no real edits, shell execution or container isolation."}
