"""Optional fail-closed session contract shared by the orchestrator and toolkit.

No model, network, desktop process, or private data is imported on startup.
Only an explicit session or SBO_REQUIRE_SESSION=1 activates the runtime guard.
The canonical session ledger and policy live in scripts/brain.py.
"""
import importlib.util
import os
from pathlib import Path

_BRAIN = None


def enabled():
    return os.environ.get("SBO_REQUIRE_SESSION", "").lower().strip() in ("1", "true", "yes")


def _module():
    global _BRAIN
    if _BRAIN is None:
        script = Path(__file__).resolve().parents[3] / "scripts" / "brain.py"
        if not script.is_file():
            raise ValueError("Brain session contract is missing: scripts/brain.py")
        spec = importlib.util.spec_from_file_location("second_brain_session_contract", script)
        loaded = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(loaded)
        _BRAIN = loaded
    return _BRAIN


def require(root, session_id="", actor_id="", task_id=None):
    """Verify identity, skills, plan and an open work item before execution."""
    if not session_id:
        if enabled():
            raise ValueError("strict agent session mode requires --session with a preflight to-do")
        return None
    brain = _module()
    try:
        return brain.preflight(Path(root), session_id, actor_id or "human", task_id)
    except brain.Refused as exc:
        raise ValueError("session refused: %s" % exc)


def audit(root, session_id, actor_id, tool, status, payload="", task_id=None):
    """Session-bound metadata only: never persist tool input/output bodies."""
    if not session_id:
        return
    brain = _module()
    try:
        return brain.audit_tool(Path(root), session_id, actor_id or "human",
                                tool, status, payload, task_id)
    except brain.Refused as exc:
        raise ValueError("session audit refused: %s" % exc)
