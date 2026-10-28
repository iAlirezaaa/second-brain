"""SuperAGI's AgentWorkflow / AgentWorkflowStep model, ported declarative.

A workflow is a plain JSON object:

    {"name": "standup scan", "max_steps": 10, "steps": [
        {"name": "scan",  "type": "tool_call", "tool": "core.vault_search",
         "args": {"query": "loop"}},
        {"name": "stop",  "type": "done", "note": "feed ready for the human"}]}

Step types are SuperAGI's workflow-step vocabulary, cut down to what a deterministic
engine can execute: `tool_call`, `done`, `fail`. A model step is NOT a type here -- in
SuperAGI a step could call the LLM; in this brain a model call is a human-gated decision,
so a workflow ends in `done` (the human reads the feed) or `fail`. `validate` is the
single gate: the engine refuses to walk an invalid workflow.
"""
STEP_TOOL_CALL = "tool_call"
STEP_DONE = "done"
STEP_FAIL = "fail"
STEP_TYPES = (STEP_TOOL_CALL, STEP_DONE, STEP_FAIL)
DEFAULT_MAX_STEPS = 25


def validate(wf):
    """Return a list of problems (empty list = valid). Pure; writes nothing."""
    problems = []
    if not isinstance(wf, dict):
        return ["workflow must be a JSON object"]
    if not str(wf.get("name") or "").strip():
        problems.append("name: required")
    steps = wf.get("steps")
    if not isinstance(steps, list) or not steps:
        problems.append("steps: a non-empty list is required")
    else:
        names = []
        for i, step in enumerate(steps, 1):
            label = ""
            if isinstance(step, dict):
                label = str(step.get("name") or "").strip()
            where = "step %d (%s)" % (i, label or "unnamed")
            if not isinstance(step, dict):
                problems.append("%s: not an object" % where)
                continue
            if step.get("type") not in STEP_TYPES:
                problems.append("%s: type must be one of %s, got %r"
                                % (where, ", ".join(STEP_TYPES), step.get("type")))
            if step.get("type") == STEP_TOOL_CALL and not str(step.get("tool") or "").strip():
                problems.append("%s: tool_call needs a tool (e.g. core.fs_read)" % where)
            if label:
                names.append(label)
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            problems.append("duplicate step names: %s" % ", ".join(dupes))
    max_steps = wf.get("max_steps", DEFAULT_MAX_STEPS)
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        problems.append("max_steps: positive int (default %d)" % DEFAULT_MAX_STEPS)
    return problems
