"""Offline contract tests for the optional Laya adapter; no weights or PyPI dependency."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
from backend import laya_adapter  # noqa: E402
from backend.tools_kit import Context, ToolError, default_registry  # noqa: E402


QUESTIONS = {"destination": {"type": "choice", "instructions": "Route this request.",
                             "criteria": {"memory": "Search past information",
                                          "human": "Escalate for review"}}}


class FakeRouter:
    def __init__(self, confidence=0.93, answer="memory", bad=False):
        self.confidence, self.answer, self.bad = confidence, answer, bad
        self.calls = []

    def predict(self, state, questions, **kwargs):
        self.calls.append((state, questions, kwargs))
        if self.bad:
            raise RuntimeError("fake model failure")
        return {"answers": {"destination": {"choice": self.answer,
                                             "answer_confidence": self.confidence}},
                "routing": {"model": "multilingual"}}


class LayaAdapterTests(unittest.TestCase):
    def test_opt_in_is_mandatory_and_no_model_is_imported(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(laya_adapter.DecisionRefused, "opt-in"):
                laya_adapter.decide("سلام", QUESTIONS, router=FakeRouter())

    def test_persian_input_and_explicit_model(self):
        router = FakeRouter()
        with patch.dict(os.environ, {"SBO_LAYA_ENABLED": "1"}):
            result = laya_adapter.decide("سلام یادداشت دیروز", QUESTIONS,
                                         model="multilingual", router=router)
        self.assertEqual(result["answers"]["destination"]["value"], "memory")
        self.assertEqual(result["status"], "proposed")
        self.assertFalse(result["actions_executed"])
        self.assertEqual(router.calls[0][2], {"model": "multilingual"})

    def test_low_confidence_asks_for_review(self):
        with patch.dict(os.environ, {"SBO_LAYA_ENABLED": "1"}):
            result = laya_adapter.decide("find note", QUESTIONS, router=FakeRouter(.6))
        self.assertEqual(result["status"], "review_required")

    def test_invalid_choice_abstains_even_with_high_confidence(self):
        with patch.dict(os.environ, {"SBO_LAYA_ENABLED": "1"}):
            result = laya_adapter.decide("find note", QUESTIONS,
                                         router=FakeRouter(.99, "run_shell"))
        self.assertIsNone(result["answers"]["destination"]["value"])
        self.assertEqual(result["status"], "review_required")

    def test_score_needs_ordered_levels(self):
        with patch.dict(os.environ, {"SBO_LAYA_ENABLED": "1"}):
            with self.assertRaisesRegex(laya_adapter.DecisionRefused, "score requires"):
                laya_adapter.decide("x", {"priority": {"type": "score",
                                           "instructions": "How important?"}}, router=FakeRouter())

    def test_invalid_questions_rejected_before_any_model_call(self):
        with patch.dict(os.environ, {"SBO_LAYA_ENABLED": "1"}):
            with self.assertRaisesRegex(laya_adapter.DecisionRefused, "2-20"):
                laya_adapter.decide("x", {"route": {"type": "choice",
                                  "instructions": "choose", "criteria": {"a": "a"}}},
                                  router=FakeRouter())

    def test_model_errors_do_not_execute_or_persist(self):
        with patch.dict(os.environ, {"SBO_LAYA_ENABLED": "1"}):
            with self.assertRaisesRegex(laya_adapter.DecisionRefused, "no decision applied"):
                laya_adapter.decide("find note", QUESTIONS, router=FakeRouter(bad=True))

    def test_tool_appears_without_importing_optional_sdk(self):
        tool = default_registry().get("core.laya_decide")
        self.assertEqual(tool.behavior, "read_only")
        self.assertFalse(tool.writes)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ToolError):
                default_registry().execute(Context(ROOT), "core.laya_decide",
                                           {"state": "hello", "questions": QUESTIONS})

    def test_status_does_not_download_weights(self):
        with patch.dict(os.environ, {}, clear=True):
            result = laya_adapter.status()
        self.assertFalse(result["ready"])
        self.assertEqual(result["model_loaded"], "not_checked")


if __name__ == "__main__":
    unittest.main()
