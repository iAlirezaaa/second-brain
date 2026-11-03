"""Regression tests for fail-closed measurements, issue integrity and CI workflows.

All mutable fixtures are isolated temporary directories; no network calls are required.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import doc_report  # noqa: E402
import issues  # noqa: E402
from common import run_utf8  # noqa: E402


class RepoGateHardening(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def command(self, script, *args):
        return run_utf8([sys.executable, str(ROOT / "scripts" / script)] +
                        list(args), cwd=str(ROOT))

    def test_issue_gate_refuses_absent_ledger_in_checkout(self):
        (self.base / "pyproject.toml").write_text("[project]\nname='fixture'\n",
                                                     encoding="utf-8")
        self.assertEqual(1, issues.check(self.base))

    def test_issue_gate_skips_absent_ledger_in_installed_home(self):
        self.assertEqual(0, issues.check(self.base))

    def test_missing_vault_is_never_a_clean_link_gate(self):
        result = self.command("link_check.py", "--vault", str(self.base / "absent"))
        self.assertEqual(1, result.returncode)
        self.assertIn("REFUSED", result.stdout)

    def test_confidence_command_refuses_a_missing_vault(self):
        result = self.command("link_check.py", "--vault", str(self.base / "absent"),
                              "--confidence")
        self.assertEqual(1, result.returncode)

    def test_empty_vault_requires_explicit_minimum_to_be_refused(self):
        self.assertEqual(0, self.command("link_check.py", "--vault",
                                         str(self.base)).returncode)
        result = self.command("link_check.py", "--vault", str(self.base),
                              "--require-notes")
        self.assertEqual(1, result.returncode)
        self.assertIn("no notes", result.stdout)

    def test_confidence_counts_broken_links_and_refuses_them(self):
        (self.base / "source.md").write_text("[[nowhere]]", encoding="utf-8")
        result = self.command("link_check.py", "--vault", str(self.base),
                              "--confidence")
        self.assertEqual(1, result.returncode)
        self.assertIn("1 wikilink(s); 1 broken", result.stdout)

    def test_strict_measurement_cannot_be_an_ordinary_document_row(self):
        with patch.object(doc_report, "measures", side_effect=KeyError("kinds")):
            with self.assertRaises(KeyError):
                doc_report.table(self.base, strict=True)

    def fixture_docs(self, broken=False):
        (self.base / "15_SYSTEM" / "config").mkdir(parents=True)
        cfg = {"zones": [{"dir": "00_START_HERE"}],
               "relations": {"parent_ids": []}}
        if not broken:
            cfg["kinds"] = {"project": {}}
        (self.base / "15_SYSTEM" / "config" / "system.json").write_text(
            json.dumps(cfg), encoding="utf-8")
        (self.base / "scripts").mkdir()
        (self.base / "scripts" / "health.py").write_text("# fixture", encoding="utf-8")
        for rel in doc_report.DOCS:
            path = self.base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# BASE\n", encoding="utf-8")

    def test_failed_measurement_writes_no_document(self):
        self.fixture_docs(broken=True)
        result = self.command("doc_report.py", "--root", str(self.base), "--write")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("REFUSED", result.stdout)
        for rel in doc_report.DOCS:
            self.assertEqual("# BASE\n", (self.base / rel).read_text(encoding="utf-8"))

    def test_duplicate_blocks_refuse_check_and_write(self):
        self.fixture_docs()
        good = self.command("doc_report.py", "--root", str(self.base), "--write")
        self.assertEqual(0, good.returncode, good.stdout)
        path = self.base / "README.md"
        original = path.read_text(encoding="utf-8")
        extra = doc_report.block(self.base, "| measure | now |\n| --- | --- |\n| forged | 999 |")
        path.write_text(original + "\n" + extra + "\n", encoding="utf-8")
        for arg in ("--check", "--write"):
            result = self.command("doc_report.py", "--root", str(self.base), arg)
            self.assertEqual(1, result.returncode, result.stdout)
            self.assertIn("multiple measured blocks", result.stdout)
        self.assertIn("forged", path.read_text(encoding="utf-8"))

    def test_duplicate_doc_markers_return_no_verified_stamp(self):
        path = self.base / "sample.md"
        path.write_text(doc_report.block(self.base, "a") + "\n" +
                        doc_report.block(self.base, "b"), encoding="utf-8")
        self.assertIsNone(doc_report.stamped(path))


class CIGovernanceTests(unittest.TestCase):
    def test_ci_cancels_obsolete_branch_runs_and_scopes_permissions(self):
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("branches: [main]", ci)
        self.assertIn("cancel-in-progress: true", ci)
        self.assertIn("contents: read", ci)
        self.assertIn("HADES plane is honest from a pristine clone", ci)

    def test_nightly_never_pushes_directly_into_protected_main(self):
        wf = (ROOT / ".github/workflows/loop.yml").read_text(encoding="utf-8")
        self.assertIn("refs/heads/loop/nightly", wf)
        self.assertNotIn("continue-on-error: true", wf)
        self.assertIn("gh pr view loop/nightly", wf)
        self.assertNotIn("gh pr create", wf)
        self.assertIn("Missing review PR", wf)
        self.assertIn("if [ \"$CYCLE_RC\" != \"0\" ]", wf)

    def test_nightly_always_runs_tests_and_honors_due_refusal(self):
        wf = (ROOT / ".github/workflows/loop.yml").read_text(encoding="utf-8")
        self.assertNotIn("loop.py --no-tests", wf)
        self.assertIn("3) echo \"run=false\"", wf)
        self.assertIn("exit 1 ;;", wf)

    def test_cron_and_schedule_record_match(self):
        wf = (ROOT / ".github/workflows/loop.yml").read_text(encoding="utf-8")
        schedule = json.loads((ROOT / "11_CONTROL/schedules/SCH-0D1E2F3A-improvement-loop.json")
                              .read_text(encoding="utf-8"))
        hour, minute = map(int, schedule["spec"]["daily_at"].split(":"))
        self.assertIn("cron: \"%d %d * * *\"" % (minute, hour), wf)


if __name__ == "__main__":
    unittest.main()
