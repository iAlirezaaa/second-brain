"""SuperAGI's execution logic: the AgentExecution state machine and the step loop.

SuperAGI ran agents as executions -- a status, a feed, step handlers dispatched by step
type, an iteration cap. The port keeps the shape and drops the farm: the statuses are
the same state machine (created/running/paused/completed/failed/terminated), the loop
walks declarative steps through a tool registry, and the feed is whatever the caller
appends (the runs ledger appends `12_RUNTIME/agent_runs/<RUN>/steps.jsonl` lines).
Deterministic steps only: an LLM step is a human-gated decision, never engine work.
"""
from .tools_kit import ToolError
from .workflows import (DEFAULT_MAX_STEPS, STEP_DONE, STEP_FAIL, STEP_TOOL_CALL,
                        STEP_TYPES)

# SuperAGI's AgentExecution statuses; "failed" is this repo's honest extra.
STATUSES = ("created", "running", "paused", "completed", "failed", "terminated")
TRANSITIONS = {
    "created": frozenset(("running", "terminated")),
    "running": frozenset(("paused", "completed", "failed", "terminated")),
    "paused": frozenset(("running", "terminated")),
    "completed": frozenset(),
    "failed": frozenset(),
    "terminated": frozenset(),
}


def can_transition(old, new):
    """The only legal way a run's status may move. Everything else is refused."""
    return new in TRANSITIONS.get(old, frozenset())


class Engine:
    """Walk a validated workflow through a registry for one actor context, reporting
    every event to `feed(status, text)` -- status is `ok` or `fail`, the same vocabulary
    the runs ledger accepts."""

    def __init__(self, registry, max_steps=None):
        self.registry = registry
        self.max_steps = max_steps

    def run(self, wf, ctx, feed=None):
        def say(status, text):
            if feed is not None:
                feed(status, text)

        # the workflow owns its cap; an explicit engine cap overrides it
        limit = self.max_steps or wf.get("max_steps", DEFAULT_MAX_STEPS)
        steps = wf.get("steps") or []
        executed = 0
        for i, step in enumerate(steps, 1):
            label = str(step.get("name") or "").strip() or ("step-%d" % i)
            if executed >= limit:
                say("fail", "%s: max_steps (%d) reached -- the workflow stops as failed"
                    % (label, limit))
                return {"status": "failed",
                        "reason": "max_steps (%d) reached before the workflow ended" % limit,
                        "steps": executed}
            stype = step.get("type")
            if stype == STEP_DONE:
                note = str(step.get("note") or "workflow says done")
                say("ok", "%s: done -- %s" % (label, note))
                return {"status": "completed", "reason": note, "steps": executed}
            if stype == STEP_FAIL:
                reason = str(step.get("reason") or "workflow says fail")
                say("fail", "%s: %s" % (label, reason))
                return {"status": "failed", "reason": reason, "steps": executed}
            if stype == STEP_TOOL_CALL:
                qualified = str(step.get("tool") or "").strip()
                try:
                    text = self.registry.execute(ctx, qualified, step.get("args") or {})
                except ToolError as exc:
                    say("fail", "%s -> %s: refused (%s)" % (label, qualified, exc))
                    return {"status": "failed",
                            "reason": "%s: %s" % (qualified, exc), "steps": executed}
                executed += 1
                say("ok", "%s -> %s: %s" % (label, qualified,
                                            " ".join(str(text).split())[:200]))
            else:
                say("fail", "%s: unknown step type %r" % (label, stype))
                return {"status": "failed",
                        "reason": "unknown step type %r (legal: %s)"
                                  % (stype, ", ".join(STEP_TYPES)),
                        "steps": executed}
        return {"status": "completed",
                "reason": "all %d step(s) executed" % executed,
                "steps": executed}
