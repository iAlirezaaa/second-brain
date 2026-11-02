"""Optional local Laya System-1 decision adapter.

Laya does not execute actions. The outputs are proposed classifications for a human or
a separately authorised workflow. Importing this module never imports Laya or downloads
weights. Real predictions require SBO_LAYA_ENABLED=1, Python >=3.10, and the optional
Laya package installed in that Python environment.
"""
import importlib
import importlib.util
import json
import math
import os
import sys

MAX_STATE_CHARS = 12000
MAX_QUESTIONS = 8
MAX_OPTIONS = 20
DEFAULT_MIN_CONFIDENCE = 0.85
SUPPORTED_TYPES = frozenset(("choice", "score", "noul"))


class DecisionRefused(ValueError):
    """The caller may not trust or execute this decision."""


def enabled():
    return os.environ.get("SBO_LAYA_ENABLED", "").lower() in ("1", "true", "yes")


def status():
    python_ok = sys.version_info >= (3, 10)
    installed = False
    if python_ok:
        try:
            installed = importlib.util.find_spec("laya") is not None
        except (ImportError, ValueError):
            pass
    return {"enabled": enabled(), "python_compatible": python_ok,
            "package_installed": installed, "ready": enabled() and python_ok and installed,
            "model_loaded": "not_checked",
            "note": "Checkpoints may download on first prediction; not included in the repository."}


def _validate(state, questions, threshold, model):
    if not isinstance(state, (dict, str, list)):
        raise DecisionRefused("state must be a string, object or list")
    try:
        serialized = json.dumps(state, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError):
        raise DecisionRefused("state must be JSON serializable")
    if not serialized or len(serialized) > MAX_STATE_CHARS:
        raise DecisionRefused("state is empty or exceeds the 12000-character local decision budget")
    if not isinstance(questions, dict) or not 1 <= len(questions) <= MAX_QUESTIONS:
        raise DecisionRefused("questions must contain 1 to 8 typed questions")
    if isinstance(threshold, bool) or not isinstance(threshold, (float, int)) or not math.isfinite(threshold) or not 0.0 < threshold <= 1.0:
        raise DecisionRefused("min_confidence must be a number greater than 0 and at most 1")
    if model not in ("auto", "english", "multilingual", "typed-decisions"):
        raise DecisionRefused("model must be auto, english, multilingual or typed-decisions")
    for key, q in questions.items():
        if not isinstance(key, str) or not key.isidentifier() or len(key) > 64:
            raise DecisionRefused("question ids must be identifiers of at most 64 characters")
        if not isinstance(q, dict) or q.get("type") not in SUPPORTED_TYPES:
            raise DecisionRefused("each question must declare choice, score or noul")
        instruction = q.get("instructions")
        if not isinstance(instruction, str) or not 1 <= len(instruction.strip()) <= 512:
            raise DecisionRefused("question instructions must be 1-512 characters")
        if q["type"] == "choice":
            criteria = q.get("criteria")
            if (not isinstance(criteria, dict) or not 2 <= len(criteria) <= MAX_OPTIONS
                    or not all(isinstance(label, str) and label and len(label) <= 64 and
                               isinstance(desc, str) and desc.strip() and len(desc) <= 512
                               for label, desc in criteria.items())):
                raise DecisionRefused("choice requires 2-20 labelled options with descriptions")


def decide(state, questions, min_confidence=DEFAULT_MIN_CONFIDENCE, model="auto", router=None):
    """Ask local Laya for typed decisions, return safe proposals, never an executable action.

    A missing/malformed confidence or an unknown choice is explicitly marked review_required.
    No state, questions or model payloads are logged or persisted by this adapter.
    """
    _validate(state, questions, min_confidence, model)
    if not enabled():
        raise DecisionRefused("Laya is opt-in: set SBO_LAYA_ENABLED=1 on this machine")
    if sys.version_info < (3, 10):
        raise DecisionRefused("Laya requires Python 3.10+; keep the core on Python 3.9 if needed")
    if router is None:
        try:
            library = importlib.import_module("laya")
        except ImportError:
            raise DecisionRefused("Laya not installed: python -m pip install '.[laya]'")
        try:
            router = library.Router()
        except Exception as exc:
            raise DecisionRefused("Laya Router could not initialize: %s" % type(exc).__name__)
    try:
        kwargs = {} if model == "auto" else {"model": model}
        result = router.predict(state, questions, **kwargs)
    except Exception as exc:
        raise DecisionRefused("Laya prediction failed (%s); no decision applied" % type(exc).__name__)
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
        raise DecisionRefused("Laya did not return typed answers")
    rows = {}
    for key, question in questions.items():
        answer = result["answers"].get(key)
        if not isinstance(answer, dict):
            raise DecisionRefused("Laya response is missing answer %s" % key)
        kind = question["type"]
        value = answer.get(kind)
        valid = (value in question["criteria"] if kind == "choice" else
                 isinstance(value, (int, float)) and not isinstance(value, bool) and
                 math.isfinite(value) and (kind == "score" or 0.0 <= value <= 1.0))
        raw_conf = answer.get("answer_confidence", answer.get("confidence"))
        conf = (float(raw_conf) if isinstance(raw_conf, (int, float)) and
                not isinstance(raw_conf, bool) and math.isfinite(raw_conf) and
                0.0 <= raw_conf <= 1.0 else None)
        accepted = bool(valid and conf is not None and conf >= min_confidence
                        and not answer.get("low_confidence", False))
        rows[key] = {"type": kind, "value": value if valid else None,
                     "confidence": conf, "status": "proposed" if accepted else "review_required"}
    routing = result.get("routing")
    if not isinstance(routing, dict):
        routing = {}
    return {"provider": "laya", "actions_executed": False,
            "status": "proposed" if all(v["status"] == "proposed" for v in rows.values()) else "review_required",
            "model": routing.get("model") or model, "answers": rows,
            "note": "Decision proposal only. No file changes, tool calls or automatic actions."}
