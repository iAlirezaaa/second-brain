"""Offline contract tests for task-first Second Brain CLI; never touch the owner's vault."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import brain  # noqa: E402


class BrainCLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "skills" / "research").mkdir(parents=True)
        (self.root / "skills" / "research" / "SKILL.md").write_text(
            "---\nname: research\ndescription: find sources and research topics\n---\n",
            encoding="utf-8")
        (self.root / "02_WIKI").mkdir()
        (self.root / "03_PROJECTS").mkdir()
        (self.root / "02_WIKI" / "proof.md").write_text(
            "Forest experiments create creative bridges between notes.", encoding="utf-8")
        (self.root / "03_PROJECTS" / "note.md").write_text(
            "Forest camera experiments suggest creative bridges to new projects.", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def opened(self, goal="research sources"):
        return brain.start(self.root, "human", goal)["session"]

    def complete_all(self, session):
        for task in brain.view(self.root, session)["tasks"]:
            if task["category"] == "handoff":
                brain.handoff(self.root, session, "reviewed", "follow up", "none")
                continue
            brain.finish(self.root, session, task["id"], "02_WIKI/proof.md")

    def test_first_move_creates_todo_and_skill_snapshot(self):
        sid = self.opened()
        state = brain.view(self.root, sid)
        self.assertEqual(5, len(state["tasks"]))
        self.assertEqual("skills", state["tasks"][0]["category"])
        self.assertEqual("todo", state["tasks"][0]["state"])
        self.assertEqual("research", state["skills_at_start"][0]["name"])

    def test_unknown_actor_refused(self):
        with self.assertRaisesRegex(brain.Refused, "registered"):
            brain.start(self.root, "AGT-00000001", "write notes")

    def test_registered_actor_may_start(self):
        path = self.root / "11_CONTROL" / "agents" / "keeper"
        path.mkdir(parents=True)
        (path / "agent.json").write_text(
            json.dumps({"id": "AGT-ABCD1234", "kind": "agent", "status": "draft"}),
            encoding="utf-8")
        row = brain.start(self.root, "AGT-ABCD1234", "keep context")
        self.assertEqual(5, row["todo_created"])

    def test_dynamic_tasks_are_persisted(self):
        sid = self.opened()
        task = brain.add(self.root, sid, "a discovered step")
        self.assertEqual("todo", task["state"])
        self.assertEqual(6, brain.view(self.root, sid)["total"])

    def test_cannot_finish_work_before_skill_review(self):
        sid = self.opened()
        task = brain.add(self.root, sid, "do research")
        with self.assertRaisesRegex(brain.Refused, "discover skills"):
            brain.finish(self.root, sid, task["task_id"], "02_WIKI/proof.md")

    def test_evidence_requires_existing_file(self):
        sid = self.opened()
        with self.assertRaisesRegex(brain.Refused, "does not exist"):
            brain.finish(self.root, sid, brain.view(self.root, sid)["tasks"][0]["id"], "missing.md")

    def test_evidence_rejects_outside_root(self):
        with self.assertRaisesRegex(brain.Refused, "relative path"):
            brain.evidence_path(self.root, "../outside.md")

    def test_handoff_required_to_close_even_when_failed(self):
        sid = self.opened()
        with self.assertRaisesRegex(brain.Refused, "handoff"):
            brain.close(self.root, sid, "failed")

    def test_success_cannot_skip_tasks(self):
        sid = self.opened()
        brain.handoff(self.root, sid, "unfinished", "return", "")
        with self.assertRaisesRegex(brain.Refused, "all tasks"):
            brain.close(self.root, sid, "success", owner_approved=True)

    def test_success_requires_explicit_owner_confirmation(self):
        sid = self.opened()
        self.complete_all(sid)
        with self.assertRaisesRegex(brain.Refused, "human confirmation"):
            brain.close(self.root, sid, "success")

    def test_completed_session_produces_draft_skill_not_installed(self):
        sid = self.opened()
        self.complete_all(sid)
        result = brain.close(self.root, sid, "success", owner_approved=True)
        self.assertFalse(result["skill_installed"])
        self.assertTrue((self.root / result["draft_skill"]).is_file())
        self.assertEqual("closed", brain.view(self.root, sid)["state"])

    def test_partial_session_keeps_pending_tasks_visible(self):
        sid = self.opened()
        brain.handoff(self.root, sid, "unfinished", "resume", "needs more work")
        result = brain.close(self.root, sid, "partial")
        self.assertGreater(result["pending_tasks"], 0)

    def test_closed_session_refuses_new_tasks(self):
        sid = self.opened()
        brain.handoff(self.root, sid, "done", "end", "")
        brain.close(self.root, sid, "partial")
        with self.assertRaisesRegex(brain.Refused, "closed"):
            brain.add(self.root, sid, "late task")

    def test_twin_is_read_only_and_does_not_execute_tools(self):
        sid = self.opened()
        path = brain._storage(self.root)
        original = path.read_bytes()
        result = brain.twin(self.root, sid, [{"op": "add_task", "summary": "try an alternative"}])
        self.assertEqual(0, result["files_written"])
        self.assertEqual(0, result["executed_tools"])
        self.assertEqual(original, path.read_bytes())
        self.assertEqual(5, brain.view(self.root, sid)["total"])

    def test_twin_refuses_bypassing_skill_gate(self):
        sid = self.opened()
        work = brain.view(self.root, sid)["tasks"][2]["id"]
        with self.assertRaisesRegex(brain.Refused, "bypasses"):
            brain.twin(self.root, sid, [{"op": "complete_task", "task_id": work}])

    def test_twin_refuses_arbitrary_commands(self):
        sid = self.opened()
        with self.assertRaisesRegex(brain.Refused, "supports only"):
            brain.twin(self.root, sid, [{"op": "shell", "command": "rm -rf"}])

    def test_adhd_bridges_two_distinct_zones_with_citations(self):
        result = brain.adhd(self.root, "forest experiments")
        self.assertEqual("ADHD", result["name"])
        self.assertTrue(result["bridges"])
        self.assertEqual("hypothesis", result["bridges"][0]["status"])
        self.assertIn("02_WIKI/", result["bridges"][0]["left"])
        self.assertIn("03_PROJECTS/", result["bridges"][0]["right"])

    def test_no_data_is_honest_empty_retrieval(self):
        result = brain.adhd(self.root, "nonsenseunmatchedidentifier")
        self.assertEqual([], result["bridges"])

    def test_handoff_automatically_completes_its_own_task(self):
        sid = self.opened()
        brain.handoff(self.root, sid, "progress report", "keep working", "")
        tasks = brain.view(self.root, sid)["tasks"]
        self.assertEqual("done", tasks[-1]["state"])
        self.assertTrue(brain.view(self.root, sid)["handoff_written"])

    def test_handoff_directory_symlink_refused(self):
        sid = self.opened()
        directory = self.root / ".brain-data" / "operator"
        elsewhere = self.root / "elsewhere"
        elsewhere.mkdir()
        try:
            (directory / "handoffs").symlink_to(elsewhere, target_is_directory=True)
        except OSError:
            self.skipTest("symlink privilege unavailable")
        with self.assertRaisesRegex(brain.Refused, "cannot be a symlink"):
            brain.handoff(self.root, sid, "summary", "next step", "")

    def test_private_storage_symlink_refused(self):
        if not hasattr(Path, "symlink_to"):
            self.skipTest("symlink unavailable")
        outside = self.root / "elsewhere"
        outside.mkdir()
        try:
            (self.root / ".brain-data").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink privilege unavailable")
        with self.assertRaisesRegex(brain.Refused, "symlink"):
            self.opened()


if __name__ == "__main__":
    unittest.main()
