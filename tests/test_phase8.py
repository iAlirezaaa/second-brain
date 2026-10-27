"""Phase 8 tests: public project standard — community files + HANDOFF standard."""
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COMMUNITY_FILES = [
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/dependabot.yml",
]

HANDOFF_SECTIONS = [
    "## 1. State Snapshot",
    "## 2. In-Flight Work",
    "## 3. Decisions & Rejected Approaches",
    "## 4. Blockers & Open Questions",
    "## 5. Next Actions",
    "## 6. Pointers",
    "## 7. Environment & Verification",
    "## 8. Handoff Rules",
]


class TestCommunityStandard(unittest.TestCase):
    def test_community_files_exist(self):
        for name in COMMUNITY_FILES:
            path = ROOT / name
            self.assertTrue(path.is_file(), f"missing {name}")
            self.assertGreater(len(path.read_text(encoding="utf-8")), 50, f"{name} is a stub")

    def test_changelog_is_keep_a_changelog(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("## [Unreleased]", text)
        self.assertIn("## [0.0.3]", text)

    def test_readmap_has_badges_and_roadmap_link(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("actions/workflows/ci.yml/badge.svg", readme, "CI badge missing")
        self.assertIn("ROADMAP.md", readme)

    def test_roadmap_is_a_public_promise_with_chips(self):
        roadmap = (ROOT / "ROADMAP.md").read_text(encoding="utf-8")
        for chip in ("🟢", "🟡", "🔵"):
            self.assertIn(chip, roadmap, f"status chip {chip} missing")
        self.assertIn("Phase 8", roadmap)


class TestHandoffStandard(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_handoff(self, extra=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "handoff.py"),
             "--root", str(self.tmp)] + (extra or []),
            capture_output=True, text=True)

    def test_scaffold_then_refresh_has_all_sections_and_overrides_head(self):
        result = self.run_handoff()
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.tmp / "HANDOFF.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        for header in HANDOFF_SECTIONS:
            self.assertIn(header, text)

        result = self.run_handoff(["--head", "deadbee"])
        self.assertIn("deadbee", result.stdout)
        text = path.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^repo_head: deadbee$", "repo_head override lost")

    def test_refresh_preserves_model_sections(self):
        self.run_handoff()
        path = self.tmp / "HANDOFF.md"
        text = path.read_text(encoding="utf-8")
        text = text.replace("## 4. Blockers & Open Questions\n",
                            "## 4. Blockers & Open Questions\n\n- blocker A: pypi mirror down\n")
        path.write_text(text, encoding="utf-8")

        self.run_handoff(["--head", "a1b2c3d"])
        after = path.read_text(encoding="utf-8")
        self.assertIn("blocker A: pypi mirror down",
                      after, "model section content was destroyed on refresh")
        # and it was NOT duplicated
        self.assertEqual(after.count("blocker A"), 1)
        # machine section still regenerated with the override head
        self.assertIn("repo_head: a1b2c3d", after)

    def test_frozen_rules_never_change(self):
        self.run_handoff()
        path = self.tmp / "HANDOFF.md"
        before = path.read_text(encoding="utf-8")
        self.run_handoff(["--head", "f00dface"])
        after = path.read_text(encoding="utf-8")
        rules_before = before.split("## 8. Handoff Rules", 1)[1]
        rules_after = after.split("## 8. Handoff Rules", 1)[1]
        self.assertEqual(rules_before, rules_after, "frozen section drifted")

    def test_check_fresh_and_stale(self):
        # stale before anything exists
        self.assertEqual(self.run_handoff(["--check"]).returncode, 2)
        self.run_handoff()
        fresh = self.run_handoff(["--check"])
        self.assertEqual(fresh.returncode, 0, fresh.stdout)
        self.assertIn("FRESH", fresh.stdout)
        # head moved -> stale immediately (head-match beats clock age)
        stale = self.run_handoff(["--check", "--head", "movedon"])
        self.assertEqual(stale.returncode, 2, stale.stdout)
        self.assertIn("STALE", stale.stdout)

    def test_shipped_handoff_shape(self):
        text = (ROOT / "HANDOFF.md").read_text(encoding="utf-8")
        for header in HANDOFF_SECTIONS:
            self.assertIn(header, text)
        self.assertRegex(text, r"(?m)^repo_head: [0-9a-f]{7,}$", "real head recorded")
        self.assertIn("generated:", text)
        # machine-written section is regenerated, so it must contain the live tests verdict
        self.assertIn("tests:", text)


if __name__ == "__main__":
    unittest.main()
