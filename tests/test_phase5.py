"""Phase 5 tests: promote (quarantine->promote) + composite health check."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CAPTURE = """---
id: cap-2026-01-01-clip
type: capture
title: A clipped idea
status: inbox
owner: agent
topics: [testing]
created: 2026-01-01
updated: 2026-01-01
---
Content of the clip.
"""


def build_minisite(tmp):
    shutil.copytree(ROOT / "rules", tmp / "rules")
    vault = tmp / "vault-template"
    (vault / "00_Inbox").mkdir(parents=True)
    (vault / "20_Notes").mkdir(parents=True)
    (vault / "90_Agent_Output" / "proposals").mkdir(parents=True)
    (vault / "00_Inbox" / "clip.md").write_text(CAPTURE, encoding="utf-8")
    proposals = {"proposals": [
        {"capture": "00_Inbox/clip.md", "target": "20_Notes",
         "destination": "20_Notes/clipped-idea.md", "reason": "test", "approved": True},
    ]}
    path = tmp / "proposals.json"
    path.write_text(__import__("json").dumps(proposals), encoding="utf-8")
    return path


def run_promote(tmp, proposals, item="00_Inbox/clip.md"):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "promote.py"),
         "--proposals", str(proposals), "--item", item, "--root", str(tmp)],
        capture_output=True, text=True)


class TestPromote(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.proposals = build_minisite(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_approved_promotion_moves_and_audits(self):
        result = run_promote(self.tmp, self.proposals)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        dest = self.tmp / "vault-template" / "20_Notes" / "clipped-idea.md"
        self.assertTrue(dest.is_file())
        self.assertFalse((self.tmp / "vault-template" / "00_Inbox" / "clip.md").exists())
        text = dest.read_text(encoding="utf-8")
        self.assertIn("status: raw", text)
        self.assertIn("promoted_by: human", text)
        audit = (self.tmp / "vault-template" / "90_Agent_Output" / "proposals" / "promotions.md")
        self.assertIn("clip.md → 20_Notes/clipped-idea.md", audit.read_text(encoding="utf-8"))


class TestPromoteRefusals(unittest.TestCase):
    def test_promotion_never_overwrites_human_content(self):
        """20_Notes is in agent_edit_never, so a destination that already exists
        there is a rewrite of human content wearing a promotion's clothes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            proposals = build_minisite(tmp)
            vault = tmp / "vault-template"
            (vault / "20_Notes" / "clipped-idea.md").write_text(
                "---\nid: human-note\ntitle: Mine\n---\nThe human wrote this.\n", encoding="utf-8")
            result = run_promote(tmp, proposals)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("agent_edit_never", result.stdout)
            kept = (vault / "20_Notes" / "clipped-idea.md").read_text(encoding="utf-8")
            self.assertIn("The human wrote this.", kept)
            self.assertTrue((vault / "00_Inbox" / "clip.md").is_file(),
                            "the refusal destroyed the capture it refused to move")

    def test_broken_fence_blocks_promotion(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            proposals = build_minisite(tmp)
            import json
            broken = json.loads((tmp / "rules" / "zones.json").read_text(encoding="utf-8"))
            broken["agent_edit_never"] = ["02_Index"]  # phantom zone, human notes unprotected
            (tmp / "rules" / "zones.json").write_text(json.dumps(broken), encoding="utf-8")
            result = run_promote(tmp, proposals)
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("BAD FENCE", result.stdout)

    def test_unapproved_move_refused(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            shutil.copytree(ROOT / "rules", tmp / "rules")
            vault = tmp / "vault-template"
            (vault / "90_Agent_Output").mkdir(parents=True)
            (vault / "00_Inbox").mkdir(parents=True)
            (vault / "00_Inbox" / "clip.md").write_text(CAPTURE, encoding="utf-8")
            proposals = tmp / "p.json"
            import json
            proposals.write_text(json.dumps({"proposals": [
                {"capture": "00_Inbox/clip.md", "target": "20_Notes",
                 "reason": "agent attempted a coup"}]}), encoding="utf-8")
            result = run_promote(tmp, proposals)
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED", result.stdout)

    def test_unknown_item_refused(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            proposals = build_minisite(tmp)
            result = run_promote(tmp, proposals, item="00_Inbox/ghost.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("no proposal", result.stdout)


class TestHealth(unittest.TestCase):
    def test_shipped_template_is_healthy(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "health.py")],
                                capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_health_fails_on_broken_links(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            shutil.copytree(ROOT / "rules", tmp / "rules")
            (tmp / "vault-template").mkdir()
            (tmp / "vault-template" / "broken.md").write_text(
                "links to [[nowhere-man]]", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "health.py"),
                 "--vault", str(tmp / "vault-template")],
                capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, 1)
        self.assertIn("BROKEN", result.stdout)


if __name__ == "__main__":
    unittest.main()
