"""The backend package: SuperAGI's execution logic, ported to the stdlib.

SuperAGI's backend is a server farm (FastAPI + SQLAlchemy + Celery/Redis) whose *logic*
is worth keeping even where its infrastructure is not. This package is that logic:
the execution engine (`engine.py`, the AgentRunner/AgentExecutor step loop and the
AgentExecution state machine), toolkits with per-actor allowlists (`tools_kit.py`,
the BaseTool/AgentConfig.tools pattern), declarative workflows (`workflows.py`, the
AgentWorkflow/AgentWorkflowStep model), schedule math (`schedules.py`, the Schedule
model without the cron daemon), long-term memory over SQLite FTS5 (`ltm.py`, the LTM
store/fetch pattern minus the vectors) and the keyword search (`search.py`).

Laws it keeps:
- deterministic steps only -- an LLM step is a human-gated decision, never engine work;
- writes need an approved context AND the actor's `tool_allowlist`;
- runs live in the disposable plane and their feed is the record of what happened.

Everything here is importable by the thin CLIs (`orchestrator.py`, `mcp_server.py`)
and by the tests; nothing here prints behind a CLI's back.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent            # .../15_SYSTEM/scripts/backend
_SCRIPTS = _HERE.parent                           # .../15_SYSTEM/scripts (hades, runs, mcp_server)
_REPO_SCRIPTS = _SCRIPTS.parents[1] / "scripts"   # .../scripts (common, memory, candidate_check)
for _p in (str(_SCRIPTS), str(_REPO_SCRIPTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
