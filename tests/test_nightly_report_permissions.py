"""Regression: nightly report publishing never requires Actions PR-creation permission.

Issue #41: scheduled run 41608309652 pushed loop/nightly successfully but
failed creating a PR (GitHub Actions is not permitted to create pull requests).
The initial review PR is provisioned out of band, without privilege escalation.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "loop.yml"


class TestNightlyReportPublishing(unittest.TestCase):
    def test_reports_never_push_to_protected_main(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("HEAD:refs/heads/loop/nightly", text)
        self.assertNotIn("git push origin main", text)
        self.assertNotIn("HEAD:refs/heads/main", text)
        # Check the actual push command, not comments or later workflow steps.
        pushes = [line.strip() for line in text.splitlines()
                  if line.strip().startswith("git push ")]
        self.assertEqual(["git push origin HEAD:refs/heads/loop/nightly"], pushes)
        self.assertFalse(any("--force" in line or " -f " in line for line in pushes))

    def test_existing_pr_is_reused_without_requesting_pr_creation_privilege(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("gh pr view loop/nightly", text)
        self.assertNotIn("gh pr create", text)
        self.assertIn("Missing review PR", text)
        self.assertIn("exit 1", text)
        self.assertNotIn("permissions: write-all", text)

    def test_nightly_refusal_remains_visible(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Enforce improvement-cycle verdict", text)
        self.assertIn('if [ "$CYCLE_RC" != "0" ]; then', text)
        self.assertIn("exit 1", text)


if __name__ == "__main__":
    unittest.main()
