"""Frontmatter losslessness tests, including the real reviewer instruction contracts."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from common import parse_frontmatter, parse_frontmatter_checked  # noqa: E402
import frontmatter_check  # noqa: E402


class LosslessFrontmatterTests(unittest.TestCase):
    def test_design_reviewer_folded_law_is_complete(self):
        path = ROOT / "11_CONTROL/reviewers/egm-design.md"
        text = path.read_text(encoding="utf-8")
        meta, body, problems = parse_frontmatter_checked(text)
        self.assertEqual([], problems)
        self.assertIn("evidence, human approval before the human plane changes)",
                      meta["vectors"][3])
        self.assertIn("Reviews the", body)

    def test_structural_reviewer_folded_law_is_complete(self):
        text = (ROOT / "11_CONTROL/reviewers/egm-structural.md").read_text(
            encoding="utf-8")
        meta, body, problems = parse_frontmatter_checked(text)
        self.assertEqual([], problems)
        self.assertIn("from a laptop a clone cannot see)", meta["vectors"][4])
        self.assertIn("# egm-structural", body)

    def test_no_closing_fence_never_consumes_the_body(self):
        text = "---\nid: x\nthen prose with a colon: here\n"
        meta, body, problems = parse_frontmatter_checked(text)
        self.assertEqual({}, meta)
        self.assertEqual(text, body)
        self.assertTrue(any("closing fence" in p for p in problems))

    def test_unsupported_heading_does_not_disappear(self):
        text = "---\n# An unsupported heading\nowner: human\n---\nBody"
        meta, body, problems = parse_frontmatter_checked(text)
        self.assertEqual({}, meta)
        self.assertEqual(text, body)
        self.assertTrue(any("unrecognized" in p for p in problems))

    def test_nested_metadata_cannot_be_hoisted_into_permissions(self):
        text = "---\nowner:\n  name: rav\n  role: human\n---\nRest"
        meta, body, problems = parse_frontmatter_checked(text)
        self.assertEqual({}, meta)
        self.assertEqual(text, body)
        self.assertTrue(any("nested" in p for p in problems))

    def test_compatibility_reader_preserves_original_on_invalid_markup(self):
        text = "---\nowner:\n  role: admin\n---\nbody"
        fm, body = parse_frontmatter(text)
        self.assertEqual({}, fm)
        self.assertEqual(text, body)

    def test_scalar_then_list_preserves_both_entries(self):
        text = "---\nid: x\nevidence: a.md\n  - b.md\n---\nbody"
        fm, body, problems = parse_frontmatter_checked(text)
        self.assertEqual([], problems)
        self.assertEqual(["a.md", "b.md"], fm["evidence"])
        self.assertEqual("body", body)

    def test_duplicate_metadata_key_is_refused(self):
        text = "---\nowner: user\nowner: admin\n---\nbody"
        _, body, problems = parse_frontmatter_checked(text)
        self.assertTrue(any("duplicate" in p for p in problems))
        self.assertEqual(text, body)

    def test_frontmatter_gate_reports_unsupported_markup(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.md"
            path.write_text("---\nid: x\n  nested: no\n---\nbody", encoding="utf-8")
            problems = frontmatter_check.validate_file(
                path, {"required_fields": {"id": {"type": "string"}}})
            self.assertTrue(any("nested" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
